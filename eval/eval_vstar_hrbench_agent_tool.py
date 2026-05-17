from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
import time
from typing import Any

import pandas as pd
from PIL import Image, ImageDraw
import requests
from tqdm import tqdm


IMAGE_FACTOR = 28
MIN_PIXELS = 4 * 28 * 28
MAX_PIXELS = 16384 * 28 * 28

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "image_zoom_in_tool",
        "description": (
            "Zoom in on a specific region of an image by cropping it based on a bounding box "
            "(bbox). The tool returns an annotated overview, a wider context crop, and a "
            "magnified detail crop so the model can keep both context and local details."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "bbox_2d": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 4,
                    "maxItems": 4,
                    "description": (
                        "The bounding box of the region to zoom in, as [x1, y1, x2, y2], "
                        "where (x1, y1) is the top-left corner and (x2, y2) is the bottom-right corner."
                    ),
                },
                "coordinate_space": {
                    "type": "string",
                    "enum": ["pixel", "normalized_1000", "normalized_1"],
                    "description": (
                        "Coordinate system used by bbox_2d. Use pixel for image pixel coordinates. "
                        "Use normalized_1000 for 0-1000 normalized coordinates, or normalized_1 for 0-1 coordinates."
                    ),
                },
                "label": {
                    "type": "string",
                    "description": "The name or label of the object in the specified bounding box.",
                },
            },
            "required": ["bbox_2d"],
        },
    },
}

SYSTEM_WITH_TOOLS = (
    "You are a helpful assistant. You can call functions to assist with the user query. "
    "Important: You must call only one function at a time. After each function call, "
    "wait for the execution result before making the next function call if needed."
)

BASELINE_SUFFIX = (
    "\nThink first, then answer. Format strictly as: "
    "<think>...</think> <answer>the final option letter or option text</answer>"
)

SKILL_SUFFIX = (
    "\nThink first. If the answer depends on small text, tiny objects, relative position, "
    "or a crowded/low-resolution area, call image_zoom_in_tool with bbox_2d for the most "
    "relevant region in the provided image coordinates. After the tool result, inspect the "
    "zoomed image and answer. Format strictly as: "
    "<think>...</think> <tool_call>...</tool_call> if needed, then <answer>...</answer>"
)

FOCUS_SKILL_SUFFIX = (
    "\nFocus zoom skill. This first step is only for localization, not answering. You must "
    "use image_zoom_in_tool before answering. First assistant turn: output exactly one "
    "<tool_call>...</tool_call> and nothing else. Do not output <think>, <answer>, an option "
    "letter, or prose. Use the image size above and pixel coordinates unless you explicitly "
    "set coordinate_space. For direct-attribute questions, draw a broad bbox around the target "
    "object, including enough nearby context. For relative-position questions, the tool call "
    "must cover both named targets. Prefer a JSON list with one bbox per target, or draw one "
    "broad bbox that contains both referenced objects; if they are far apart, span the region "
    "between them. A crop around only one object is not enough for a relative-position question. "
    "Do not use the whole image unless the target occupies most of it. If unsure, choose a broad "
    "likely region and call the tool; never answer before the tool result. The multiple-choice "
    "options will be provided after the zoom result."
)

TOOL_RESPONSE_TEXT = (
    "Use these tool images to finish the same multiple-choice question. Image 1 is an overview "
    "with the requested region marked. Image 2 is a wider context crop. Image 3 is the magnified "
    "detail crop. Answer only with one of the original options; do not switch to a different object."
)

TOOL_MODES = {"skill_tool", "focus_skill_tool"}

UNCERTAIN_RE = re.compile(
    r"\b(no|not|cannot|can't|unable|insufficient|unclear|not enough|not visible|"
    r"not possible|none of|cannot be determined|question cannot|there is no)\b",
    re.IGNORECASE,
)
TEXT_DETAIL_RE = re.compile(
    r"\b(text|written|number|license|sign|word|letter|logo|clock|time|sum|average|map|highlighted)\b",
    re.IGNORECASE,
)


def build_tool_system_prompt() -> str:
    return (
        f"{SYSTEM_WITH_TOOLS}\n\n"
        "# Tools\n\n"
        "You may call one or more functions to assist with the user query.\n\n"
        "You are provided with function signatures within <tools></tools> XML tags:\n"
        "<tools>\n"
        f"{json.dumps(TOOL_SCHEMA, ensure_ascii=False)}\n"
        "</tools>\n\n"
        "For each function call, return a json object with function name and arguments within "
        "<tool_call></tool_call> XML tags:\n"
        "<tool_call>\n"
        "{\"name\": <function-name>, \"arguments\": <args-json-object>}\n"
        "</tool_call>"
    )


@dataclass(frozen=True)
class VStarItem:
    test_type: str
    image_name: str
    image_path: Path
    question: str
    options: list[str]
    answer: str
    target_objects: list[str]


@dataclass(frozen=True)
class HRBenchItem:
    test_type: str
    index: int
    question: str
    options: dict[str, str]
    answer: str
    category: str
    image_b64: str


def round_by_factor(number: float, factor: int) -> int:
    return round(number / factor) * factor


def ceil_by_factor(number: float, factor: int) -> int:
    return math.ceil(number / factor) * factor


def floor_by_factor(number: float, factor: int) -> int:
    return math.floor(number / factor) * factor


def smart_resize(
    height: int,
    width: int,
    factor: int = IMAGE_FACTOR,
    min_pixels: int = MIN_PIXELS,
    max_pixels: int = MAX_PIXELS,
) -> tuple[int, int]:
    h_bar = max(factor, round_by_factor(height, factor))
    w_bar = max(factor, round_by_factor(width, factor))
    if h_bar * w_bar > max_pixels:
        beta = math.sqrt((height * width) / max_pixels)
        h_bar = floor_by_factor(height / beta, factor)
        w_bar = floor_by_factor(width / beta, factor)
    elif h_bar * w_bar < min_pixels:
        beta = math.sqrt(min_pixels / max(1, height * width))
        h_bar = ceil_by_factor(height * beta, factor)
        w_bar = ceil_by_factor(width * beta, factor)
    return max(factor, h_bar), max(factor, w_bar)


def encode_pil_image_to_base64(image: Image.Image) -> str:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def decode_base64_to_image(base64_string: str) -> Image.Image:
    image = Image.open(BytesIO(base64.b64decode(base64_string))).convert("RGB")
    return image


def image_to_content(image: Image.Image) -> dict[str, Any]:
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encode_pil_image_to_base64(image)}"}}


def redacted_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    redacted: list[dict[str, Any]] = []
    for message in messages:
        out = {k: v for k, v in message.items() if k not in {"content", "tool_calls"}}
        content = message.get("content")
        if isinstance(content, list):
            clean_content = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "image_url":
                    clean_item = dict(item)
                    clean_item["image_url"] = {"url": "data:image/png;base64,"}
                    clean_content.append(clean_item)
                else:
                    clean_content.append(item)
            out["content"] = clean_content
        else:
            out["content"] = content
        if message.get("tool_calls"):
            out["tool_calls"] = message["tool_calls"]
        redacted.append(out)
    return redacted


def call_chat_completion(
    *,
    api_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    temperature: float,
    max_tokens: int,
    timeout: float,
    retries: int,
) -> dict[str, Any]:
    url = api_url.rstrip("/") + "/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices") or []
            if not choices:
                raise RuntimeError(f"chat/completions returned no choices: {data}")
            return choices[0].get("message") or {}
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(min(2**attempt, 8))
    raise RuntimeError(f"chat/completions failed after {retries + 1} attempts: {last_error}")


def resolve_served_model(api_url: str, explicit_model: str | None, timeout: float = 20.0) -> str:
    if explicit_model:
        return explicit_model
    response = requests.get(api_url.rstrip("/") + "/models", timeout=timeout)
    response.raise_for_status()
    models = response.json().get("data") or []
    if not models:
        raise RuntimeError(f"No models returned by {api_url}/models")
    return models[0]["id"]


def build_options_text(options: list[str] | dict[str, str]) -> str:
    if isinstance(options, dict):
        letters = ["A", "B", "C", "D", "E", "F"]
        return "\n".join(f"{letter}. {options[letter]}" for letter in letters if letter in options)
    letters = ["A", "B", "C", "D", "E", "F"]
    return "\n".join(f"{letters[i]}. {option}" for i, option in enumerate(options))


def extract_answer(text: str) -> str:
    text = (text or "").replace("<|im_end|>", "").strip()
    match = re.search(r"<answer>(.*?)</answer>", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"answer\s*[:：]\s*([A-F](?:\.\s*)?.*)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()


def extract_explicit_answer(text: str) -> str | None:
    text = (text or "").replace("<|im_end|>", "").strip()
    match = re.search(r"<answer>(.*?)</answer>", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        answer = match.group(1).strip()
        return answer or None
    match = re.search(r"answer\s*[:：]\s*([A-F](?:\.\s*)?.*)", text, flags=re.IGNORECASE)
    if match:
        answer = match.group(1).strip()
        return answer or None
    return None


def parse_tool_call(message: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    tool_calls = message.get("tool_calls") or []
    if tool_calls:
        call = tool_calls[0]
        function = call.get("function") or {}
        name = function.get("name")
        raw_args = function.get("arguments") or "{}"
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except json.JSONDecodeError:
            args = {}
        if name:
            return str(name), dict(args or {})

    content = message.get("content") or ""
    match = re.search(r"<tool_call>\s*(.*?)\s*</tool_call>", content, flags=re.DOTALL)
    if match:
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            payload = None
        tool_call = payload_to_tool_call(payload)
        if tool_call is not None:
            return tool_call

    xml_call = parse_xml_zoom_call(content)
    if xml_call is not None:
        return xml_call

    json_call = parse_loose_json_zoom_call(content)
    if json_call is not None:
        return json_call

    bracket_call = parse_bracket_bbox_zoom_call(content)
    if bracket_call is not None:
        return bracket_call

    return None


def merge_bbox_args(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    boxes: list[list[float]] = []
    labels: list[str] = []
    normalized_items: list[dict[str, Any]] = []
    for item in items:
        bbox = item.get("bbox_2d")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        try:
            parsed_bbox = [float(v) for v in bbox]
        except (TypeError, ValueError):
            continue
        boxes.append(parsed_bbox)
        label = str(item.get("label") or "").strip()
        if label:
            labels.append(label)
        normalized_items.append({"bbox_2d": parsed_bbox, "label": label})
    if not boxes:
        return None
    merged = [
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    ]
    return {"bbox_2d": merged, "label": " and ".join(labels) if labels else "", "_objects": normalized_items}


def payload_to_tool_call(payload: Any) -> tuple[str, dict[str, Any]] | None:
    if isinstance(payload, dict):
        if "name" in payload and "arguments" in payload:
            return str(payload.get("name") or "image_zoom_in_tool"), dict(payload.get("arguments") or {})
        if "action" in payload or "tool" in payload or "function" in payload:
            name = str(payload.get("action") or payload.get("tool") or payload.get("function") or "")
            if name == "image_zoom_in_tool":
                args = dict(payload.get("arguments") or payload)
                args.pop("action", None)
                args.pop("tool", None)
                args.pop("function", None)
                return "image_zoom_in_tool", args
        if "bbox_2d" in payload:
            return "image_zoom_in_tool", dict(payload)
        if any(key in payload for key in ("coordinate", "center", "center_2d", "point")):
            return "image_zoom_in_tool", dict(payload)
    if isinstance(payload, list):
        if len(payload) == 4:
            try:
                bbox = [float(value) for value in payload]
            except (TypeError, ValueError):
                bbox = []
            if len(bbox) == 4:
                return "image_zoom_in_tool", {"bbox_2d": bbox}
        merged = merge_bbox_args([item for item in payload if isinstance(item, dict)])
        if merged is not None:
            return "image_zoom_in_tool", merged
    return None


def parse_bracket_bbox_zoom_call(content: str) -> tuple[str, dict[str, Any]] | None:
    number = r"-?\d+(?:\.\d+)?"
    pattern = re.compile(
        rf"\[\s*({number})\s*,\s*({number})\s*,\s*({number})\s*,\s*({number})\s*\]"
    )
    for match in pattern.finditer(content):
        bbox = [float(value) for value in match.groups()]
        if max(abs(value) for value in bbox) <= 1.5:
            return "image_zoom_in_tool", {"bbox_2d": bbox, "coordinate_space": "normalized_1"}
        if max(abs(value) for value in bbox) <= 1000 and re.search(
            r"normal(?:ized)?|0\s*[-~to]+\s*1000", content, flags=re.IGNORECASE
        ):
            return "image_zoom_in_tool", {"bbox_2d": bbox, "coordinate_space": "normalized_1000"}
        return "image_zoom_in_tool", {"bbox_2d": bbox}
    return None


def parse_loose_json_zoom_call(content: str) -> tuple[str, dict[str, Any]] | None:
    candidates: list[str] = []
    candidates.extend(re.findall(r"```(?:json)?\s*(.*?)```", content, flags=re.DOTALL | re.IGNORECASE))
    candidates.append(content)
    decoder = json.JSONDecoder()
    for candidate in candidates:
        text = candidate.strip()
        if not text:
            continue
        for start, char in enumerate(text):
            if char not in "[{":
                continue
            try:
                payload, _ = decoder.raw_decode(text[start:])
            except json.JSONDecodeError:
                continue
            tool_call = payload_to_tool_call(payload)
            if tool_call is not None:
                return tool_call
    return None


def parse_xml_zoom_call(content: str) -> tuple[str, dict[str, Any]] | None:
    match = re.search(r"<image_zoom_in_tool\b([^>]*)>", content, flags=re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    attrs = {
        key.lower(): value
        for key, value in re.findall(r"([a-zA-Z_][\w-]*)\s*=\s*['\"]([^'\"]+)['\"]", match.group(1))
    }
    label_match = re.search(r"<image_zoom_in_tool\b[^>]*>(.*?)</image_zoom_in_tool>", content, flags=re.DOTALL | re.IGNORECASE)
    label = str(attrs.get("label") or attrs.get("alt") or (label_match.group(1).strip() if label_match else "")).strip()
    try:
        x_values = [float(value) for key, value in attrs.items() if re.fullmatch(r"x\d+", key)]
        y_values = [float(value) for key, value in attrs.items() if re.fullmatch(r"y\d+", key)]
        if "width" in attrs and "height" in attrs and "x1" in attrs and "y1" in attrs:
            x1 = float(attrs["x1"])
            y1 = float(attrs["y1"])
            bbox = [x1, y1, x1 + float(attrs["width"]), y1 + float(attrs["height"])]
        elif x_values and y_values:
            pad = 80.0
            bbox = [min(x_values) - pad, min(y_values) - pad, max(x_values) + pad, max(y_values) + pad]
        else:
            label_call = parse_bracket_bbox_zoom_call(label)
            if label_call is not None:
                return label_call
            return None
    except (TypeError, ValueError):
        return None
    return "image_zoom_in_tool", {"bbox_2d": bbox, "label": label}


def bbox_from_center_args(image: Image.Image, tool_args: dict[str, Any]) -> list[float] | None:
    center = (
        tool_args.get("center_2d")
        or tool_args.get("coordinate")
        or tool_args.get("center")
        or tool_args.get("point")
    )
    if isinstance(center, dict):
        center = [center.get("x"), center.get("y")]
    if not isinstance(center, list) or len(center) < 2:
        return None
    try:
        x = float(center[0])
        y = float(center[1])
    except (TypeError, ValueError):
        return None

    width, height = image.size
    space = str(tool_args.get("coordinate_space") or "").strip().lower()
    max_coord = max(abs(x), abs(y))
    if space == "normalized_1" or (not space and max_coord <= 1.5):
        x *= width
        y *= height
    elif space == "normalized_1000":
        x = x / 1000.0 * width
        y = y / 1000.0 * height

    try:
        scale = float(tool_args.get("scale", 0.25))
    except (TypeError, ValueError):
        scale = 0.25
    box_w = tool_args.get("width") or tool_args.get("w")
    box_h = tool_args.get("height") or tool_args.get("h")
    try:
        side_w = float(box_w) if box_w is not None else 0.0
        side_h = float(box_h) if box_h is not None else 0.0
    except (TypeError, ValueError):
        side_w = side_h = 0.0
    if side_w <= 0 or side_h <= 0:
        if scale <= 1.5:
            side = max(224.0, min(width, height) * max(0.08, min(scale, 0.8)))
        else:
            side = scale
        side_w = side_h = side
    return [x - side_w / 2.0, y - side_h / 2.0, x + side_w / 2.0, y + side_h / 2.0]


def normalize_bbox(image: Image.Image, bbox: Any, coordinate_space: str | None = None) -> list[float]:
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise ValueError("bbox_2d must be a list of four numbers")
    left, top, right, bottom = [float(v) for v in bbox]
    width, height = image.size

    space = (coordinate_space or "pixel").strip().lower()
    max_coord = max(abs(left), abs(top), abs(right), abs(bottom))
    if space == "normalized_1" or max_coord <= 1.5:
        left, right = left * width, right * width
        top, bottom = top * height, bottom * height
    elif space == "normalized_1000":
        left, right = left / 1000.0 * width, right / 1000.0 * width
        top, bottom = top / 1000.0 * height, bottom / 1000.0 * height

    # Some models accidentally output [x, y, width, height]. Recover that shape.
    if right <= left or bottom <= top:
        if right > 0 and bottom > 0:
            right = left + right
            bottom = top + bottom

    left = max(0.0, min(float(width - 1), left))
    top = max(0.0, min(float(height - 1), top))
    right = max(1.0, min(float(width), right))
    bottom = max(1.0, min(float(height), bottom))
    if right <= left or bottom <= top:
        raise ValueError(f"invalid bbox after normalization: {[left, top, right, bottom]}")
    return [left, top, right, bottom]


def expand_bbox(image: Image.Image, bbox: list[float], *, scale: float, min_side: int) -> list[float]:
    width, height = image.size
    left, top, right, bottom = bbox
    box_w = right - left
    box_h = bottom - top
    target_w = max(box_w * scale, float(min_side))
    target_h = max(box_h * scale, float(min_side))
    target_w = min(target_w, float(width))
    target_h = min(target_h, float(height))
    cx = (left + right) / 2.0
    cy = (top + bottom) / 2.0
    new_left = min(max(0.0, cx - target_w / 2.0), max(0.0, width - target_w))
    new_top = min(max(0.0, cy - target_h / 2.0), max(0.0, height - target_h))
    return [new_left, new_top, new_left + target_w, new_top + target_h]


def resize_for_model(image: Image.Image, *, min_side: int, max_side: int) -> Image.Image:
    crop_w, crop_h = image.size
    scale = max(1.0, float(min_side) / max(1, min(crop_w, crop_h)))
    if max(crop_w, crop_h) * scale > max_side:
        scale = float(max_side) / max(crop_w, crop_h)
    new_w = max(IMAGE_FACTOR, round_by_factor(crop_w * scale, IMAGE_FACTOR))
    new_h = max(IMAGE_FACTOR, round_by_factor(crop_h * scale, IMAGE_FACTOR))
    if new_w != crop_w or new_h != crop_h:
        image = image.resize((new_w, new_h), Image.Resampling.BICUBIC)
    return image


def crop_and_zoom(image: Image.Image, bbox: list[float], *, min_side: int, max_side: int) -> Image.Image:
    left, top, right, bottom = bbox
    crop = image.crop((int(math.floor(left)), int(math.floor(top)), int(math.ceil(right)), int(math.ceil(bottom))))
    return resize_for_model(crop, min_side=min_side, max_side=max_side)


def draw_bbox_overview(image: Image.Image, bbox: list[float], *, max_side: int = 1344) -> Image.Image:
    overview = image.copy()
    width, height = overview.size
    scale = min(1.0, float(max_side) / max(width, height))
    if scale < 1.0:
        overview = overview.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.Resampling.BICUBIC)
    draw = ImageDraw.Draw(overview)
    left, top, right, bottom = [v * scale for v in bbox]
    line_width = max(4, int(round(max(overview.size) / 240)))
    for inset in range(line_width):
        draw.rectangle((left - inset, top - inset, right + inset, bottom + inset), outline=(255, 0, 0))
    return overview


def build_zoom_tool_content(
    image: Image.Image,
    tool_args: dict[str, Any],
    *,
    min_side: int,
    max_side: int,
    preliminary_answer: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    if "bbox_2d" not in tool_args:
        inferred_bbox = bbox_from_center_args(image, tool_args)
        if inferred_bbox is not None:
            tool_args = dict(tool_args)
            tool_args["bbox_2d"] = inferred_bbox
    bbox = normalize_bbox(image, tool_args.get("bbox_2d"), tool_args.get("coordinate_space"))
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    if min(width, height) < 8 or max(width, height) / max(1.0, min(width, height)) > 100:
        raise ValueError(f"bbox is too small or too thin after normalization: {bbox}")

    context_bbox = expand_bbox(image, bbox, scale=2.8, min_side=336)
    detail_bbox = expand_bbox(image, bbox, scale=1.35, min_side=112)
    overview = draw_bbox_overview(image, bbox)
    context = crop_and_zoom(image, context_bbox, min_side=min_side, max_side=max_side)
    detail = crop_and_zoom(image, detail_bbox, min_side=min_side, max_side=max_side)

    label = str(tool_args.get("label") or "").strip()
    coord_text = (
        f"Requested bbox: {[round(v, 1) for v in bbox]}. "
        f"Context bbox: {[round(v, 1) for v in context_bbox]}. "
        f"Detail bbox: {[round(v, 1) for v in detail_bbox]}."
    )
    objects = tool_args.get("_objects")
    if isinstance(objects, list) and len(objects) >= 2:
        object_infos = []
        for item in objects:
            if not isinstance(item, dict):
                continue
            try:
                obj_bbox = normalize_bbox(image, item.get("bbox_2d"), tool_args.get("coordinate_space"))
            except Exception:  # noqa: BLE001
                continue
            obj_label = str(item.get("label") or f"object {len(object_infos) + 1}").strip()
            cx = (obj_bbox[0] + obj_bbox[2]) / 2.0
            cy = (obj_bbox[1] + obj_bbox[3]) / 2.0
            object_infos.append((obj_label, obj_bbox, cx, cy))
        if len(object_infos) >= 2:
            first, second = object_infos[0], object_infos[1]
            horizontal = "left of" if first[2] < second[2] else "right of"
            vertical = "above" if first[3] < second[3] else "below"
            coord_text += " Provided object centers: " + "; ".join(
                f"{label} center=({round(cx, 1)}, {round(cy, 1)})"
                for label, _, cx, cy in object_infos
            )
            coord_text += f". Based on these provided boxes, {first[0]} is {horizontal} and {vertical} {second[0]}."
    if label:
        coord_text += f" Region label: {label}."
    if preliminary_answer:
        coord_text += (
            f" Preliminary answer from the previous assistant turn: {preliminary_answer}. "
            "Keep it unless the tool images clearly contradict it."
        )
    content = [
        {"type": "text", "text": "<tool_response>\nImage 1: overview with requested region marked in red.\n"},
        image_to_content(overview),
        {"type": "text", "text": "\nImage 2: wider context crop around the requested region.\n"},
        image_to_content(context),
        {"type": "text", "text": "\nImage 3: magnified detail crop around the requested region.\n"},
        image_to_content(detail),
        {"type": "text", "text": f"\n{coord_text}\n{TOOL_RESPONSE_TEXT}\n</tool_response>"},
    ]
    return content, coord_text


def bbox_to_crop(image: Image.Image, bbox: Any, *, min_side: int, max_side: int) -> Image.Image:
    normalized = normalize_bbox(image, bbox)
    crop = image.crop(
        (
            int(math.floor(normalized[0])),
            int(math.floor(normalized[1])),
            int(math.ceil(normalized[2])),
            int(math.ceil(normalized[3])),
        )
    )
    crop_w, crop_h = crop.size
    scale = max(1.0, float(min_side) / max(1, min(crop_w, crop_h)))
    if max(crop_w, crop_h) * scale > max_side:
        scale = float(max_side) / max(crop_w, crop_h)
    new_w = max(IMAGE_FACTOR, round_by_factor(crop_w * scale, IMAGE_FACTOR))
    new_h = max(IMAGE_FACTOR, round_by_factor(crop_h * scale, IMAGE_FACTOR))
    if new_w != crop_w or new_h != crop_h:
        crop = crop.resize((new_w, new_h), Image.Resampling.BICUBIC)
    return crop


def build_initial_messages(
    mode: str,
    image: Image.Image,
    question: str,
    options_text: str,
    target_hint: str | None = None,
) -> list[dict[str, Any]]:
    if mode == "focus_skill_tool":
        suffix = FOCUS_SKILL_SUFFIX
    elif mode == "skill_tool":
        suffix = SKILL_SUFFIX
    else:
        suffix = BASELINE_SUFFIX
    system = build_tool_system_prompt() if mode in TOOL_MODES else "You are a helpful assistant."
    image_size = f"Image size: width={image.width}, height={image.height}. Pixel coordinates use [x1, y1, x2, y2] from the top-left corner."
    target_line = f"\nTargets to localize: {target_hint}" if target_hint else ""
    prompt = f"{image_size}{target_line}\nQuestion: {question}\nOptions:\n{options_text}\n{suffix}"
    if mode == "focus_skill_tool":
        prompt = f"{image_size}{target_line}\nLocalization question: {question}\n{suffix}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": [image_to_content(image), {"type": "text", "text": prompt}]},
    ]


def run_agent(
    *,
    mode: str,
    image: Image.Image,
    question: str,
    options_text: str,
    api_url: str,
    api_key: str,
    model: str,
    max_tokens: int,
    max_tool_rounds: int,
    timeout: float,
    retries: int,
    zoom_min_side: int,
    zoom_max_side: int,
    target_hint: str | None = None,
) -> tuple[str, list[dict[str, Any]], str]:
    messages = build_initial_messages(mode, image, question, options_text, target_hint)
    # The training loop renders tools into the chat template before generation. vLLM's
    # OpenAI endpoint may reject the OpenAI `tools` field for this model/template, so
    # the equivalent tool schema is injected in the system prompt above.
    tools = None
    status = "success"
    final_text = ""
    used_tool = False
    candidate_answers: list[tuple[bool, str]] = []

    for turn_idx in range(max_tool_rounds + 1):
        message = call_chat_completion(
            api_url=api_url,
            api_key=api_key,
            model=model,
            messages=messages,
            tools=tools,
            temperature=0.0,
            max_tokens=max_tokens,
            timeout=timeout,
            retries=retries,
        )
        content = message.get("content") or ""
        final_text = content
        explicit_answer = extract_explicit_answer(content)
        if explicit_answer:
            candidate_answers.append((used_tool, explicit_answer))

        if mode not in TOOL_MODES:
            messages.append({"role": "assistant", "content": content})
            break

        tool_call = parse_tool_call(message)
        if tool_call is None or turn_idx >= max_tool_rounds:
            messages.append({"role": "assistant", "content": content})
            if mode == "focus_skill_tool" and not used_tool and turn_idx < max_tool_rounds:
                status = "tool_retry"
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "This is still the localization step. Do not answer the question. Output exactly one "
                            "<tool_call>{\"name\":\"image_zoom_in_tool\",\"arguments\":{\"bbox_2d\":[x1,y1,x2,y2],"
                            "\"label\":\"target\"}}</tool_call> with a broad pixel bbox around the target region, "
                            "and no other text. For relative-position questions, include both named objects in the "
                            "bbox or provide a JSON list with one bbox per object."
                        ),
                    }
                )
                continue
            break

        tool_name, tool_args = tool_call
        messages.append({"role": "assistant", "content": content})

        if tool_name != "image_zoom_in_tool":
            status = "tool_error"
            messages.append(
                {
                    "role": "user",
                    "content": f"<tool_response>\nError: unknown tool {tool_name}. Please answer without more tools.\n</tool_response>",
                }
            )
            continue

        try:
            preliminary_answer = explicit_answer
            tool_content, _ = build_zoom_tool_content(
                image,
                tool_args,
                min_side=zoom_min_side,
                max_side=zoom_max_side,
                preliminary_answer=preliminary_answer,
            )
            used_tool = True
            if mode == "focus_skill_tool":
                tool_content.append(
                    {
                        "type": "text",
                        "text": (
                            f"\nOriginal question: {question}\nOptions:\n{options_text}\n"
                            "Now inspect the original image and all zoom images, then answer strictly as: "
                            "<think>...</think> <answer>the final option letter or option text</answer>"
                        ),
                    }
                )
            messages.append(
                {
                    "role": "user",
                    "content": tool_content,
                }
            )
        except Exception as exc:  # noqa: BLE001
            status = "tool_error"
            messages.append(
                {
                    "role": "user",
                    "content": f"<tool_response>\nError: image_zoom_in_tool failed: {exc}. Please answer without more tools.\n</tool_response>",
                }
            )

    if mode == "focus_skill_tool" and candidate_answers:
        after_tool_answers = [answer for is_after_tool, answer in candidate_answers if is_after_tool]
        selected_answer = after_tool_answers[-1] if after_tool_answers else candidate_answers[0][1]
    else:
        selected_answer = extract_answer(final_text)
    return selected_answer, redacted_messages(messages), status


def should_retry_single_with_zoom(question: str, pred_ans: str) -> bool:
    return bool(TEXT_DETAIL_RE.search(question or "") and UNCERTAIN_RE.search(pred_ans or ""))


def run_selective_agent(
    *,
    bench: str,
    category: str | None,
    image: Image.Image,
    question: str,
    options_text: str,
    api_url: str,
    api_key: str,
    model: str,
    max_tokens: int,
    max_tool_rounds: int,
    timeout: float,
    retries: int,
    zoom_min_side: int,
    zoom_max_side: int,
) -> tuple[str, list[dict[str, Any]], str]:
    if bench == "hrbench" and category == "cross":
        return run_agent(
            mode="skill_tool",
            image=image,
            question=question,
            options_text=options_text,
            api_url=api_url,
            api_key=api_key,
            model=model,
            max_tokens=max_tokens,
            max_tool_rounds=max_tool_rounds,
            timeout=timeout,
            retries=retries,
            zoom_min_side=zoom_min_side,
            zoom_max_side=zoom_max_side,
        )

    pred_ans, pred_output, status = run_agent(
        mode="baseline",
        image=image,
        question=question,
        options_text=options_text,
        api_url=api_url,
        api_key=api_key,
        model=model,
        max_tokens=max_tokens,
        max_tool_rounds=max_tool_rounds,
        timeout=timeout,
        retries=retries,
        zoom_min_side=zoom_min_side,
        zoom_max_side=zoom_max_side,
    )

    if bench == "hrbench" and category == "single" and should_retry_single_with_zoom(question, pred_ans):
        return run_agent(
            mode="skill_tool",
            image=image,
            question=question,
            options_text=options_text,
            api_url=api_url,
            api_key=api_key,
            model=model,
            max_tokens=max_tokens,
            max_tool_rounds=max_tool_rounds,
            timeout=timeout,
            retries=retries,
            zoom_min_side=zoom_min_side,
            zoom_max_side=zoom_max_side,
        )

    return pred_ans, pred_output, status


def load_vstar_items(vstar_path: Path, test_type: str, limit: int | None) -> list[VStarItem]:
    test_dir = vstar_path / test_type
    image_files = sorted(path for path in test_dir.iterdir() if path.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if limit is not None:
        image_files = image_files[:limit]
    items: list[VStarItem] = []
    for image_path in image_files:
        anno_path = image_path.with_suffix(".json")
        anno = json.loads(anno_path.read_text(encoding="utf-8"))
        items.append(
            VStarItem(
                test_type=test_type,
                image_name=image_path.name,
                image_path=image_path,
                question=anno["question"],
                options=list(anno["options"]),
                answer=anno["options"][0],
                target_objects=[str(item) for item in anno.get("target_object", [])],
            )
        )
    return items


def load_hrbench_items(hrbench_path: Path, test_type: str, limit: int | None) -> list[HRBenchItem]:
    df = pd.read_csv(hrbench_path / f"{test_type}.tsv", sep="\t")
    if limit is not None:
        df = df.head(limit)
    items: list[HRBenchItem] = []
    for idx, row in df.iterrows():
        items.append(
            HRBenchItem(
                test_type=test_type,
                index=int(row.get("index", idx)),
                question=str(row["question"]),
                options={letter: str(row[letter]) for letter in ["A", "B", "C", "D"]},
                answer=str(row["answer"]),
                category=str(row["category"]),
                image_b64=str(row["image"]),
            )
        )
    return items


def process_vstar_item(item: VStarItem, args: argparse.Namespace, model: str) -> dict[str, Any]:
    image = Image.open(item.image_path).convert("RGB")
    try:
        agent_mode = "baseline" if args.mode == "selective_skill_tool" else args.mode
        pred_ans, pred_output, status = run_agent(
            mode=agent_mode,
            image=image,
            question=item.question,
            options_text=build_options_text(item.options),
            api_url=args.api_url,
            api_key=args.api_key,
            model=model,
            max_tokens=args.max_tokens,
            max_tool_rounds=args.max_tool_rounds,
            timeout=args.request_timeout,
            retries=args.retries,
            zoom_min_side=args.zoom_min_side,
            zoom_max_side=args.zoom_max_side,
            target_hint=", ".join(item.target_objects),
        )
    except Exception as exc:  # noqa: BLE001
        pred_ans, pred_output, status = f"ERROR: {exc}", [], "error"
    return {
        "image": item.image_name,
        "question": item.question,
        "answer": item.answer,
        "pred_ans": pred_ans,
        "pred_output": pred_output,
        "status": status,
    }


def process_hrbench_item(item: HRBenchItem, args: argparse.Namespace, model: str) -> dict[str, Any]:
    image = decode_base64_to_image(item.image_b64)
    resize_h, resize_w = smart_resize(image.height, image.width)
    if (resize_w, resize_h) != image.size:
        image = image.resize((resize_w, resize_h), Image.Resampling.BICUBIC)
    try:
        if args.mode == "selective_skill_tool":
            pred_ans, pred_output, status = run_selective_agent(
                bench="hrbench",
                category=item.category,
                image=image,
                question=item.question,
                options_text=build_options_text(item.options),
                api_url=args.api_url,
                api_key=args.api_key,
                model=model,
                max_tokens=args.max_tokens,
                max_tool_rounds=args.max_tool_rounds,
                timeout=args.request_timeout,
                retries=args.retries,
                zoom_min_side=args.zoom_min_side,
                zoom_max_side=args.zoom_max_side,
            )
        else:
            pred_ans, pred_output, status = run_agent(
                mode=args.mode,
                image=image,
                question=item.question,
                options_text=build_options_text(item.options),
                api_url=args.api_url,
                api_key=args.api_key,
                model=model,
                max_tokens=args.max_tokens,
                max_tool_rounds=args.max_tool_rounds,
                timeout=args.request_timeout,
                retries=args.retries,
                zoom_min_side=args.zoom_min_side,
                zoom_max_side=args.zoom_max_side,
            )
    except Exception as exc:  # noqa: BLE001
        pred_ans, pred_output, status = f"ERROR: {exc}", [], "error"
    return {
        "question": item.question,
        "answer": item.answer,
        "answer_str": item.options[item.answer],
        "pred_ans": pred_ans,
        "pred_output": pred_output,
        "category": item.category,
        "status": status,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_items(items: list[Any], fn: Any, args: argparse.Namespace, model: str, desc: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.num_workers)) as executor:
        futures = [executor.submit(fn, item, args, model) for item in items]
        with tqdm(total=len(futures), desc=desc) as pbar:
            for future in as_completed(futures):
                try:
                    rows.append(future.result())
                except Exception as exc:  # noqa: BLE001
                    rows.append({"pred_ans": f"ERROR: {exc}", "pred_output": [], "status": "error"})
                pbar.update(1)
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Qwen2.5-VL on VStar/HRBench with baseline or agent-loop tool mode.")
    parser.add_argument("--bench", choices=["vstar", "hrbench"], required=True)
    parser.add_argument("--mode", choices=["baseline", "skill_tool", "selective_skill_tool", "focus_skill_tool"], required=True)
    parser.add_argument("--model_name", required=True)
    parser.add_argument("--api_key", default="EMPTY")
    parser.add_argument("--api_url", default="http://127.0.0.1:18080/v1")
    parser.add_argument("--eval_model_name", default=None)
    parser.add_argument("--vstar_bench_path", default="/root/data/vstar_bench")
    parser.add_argument("--hrbench_path", default="/root/data/hr_bench")
    parser.add_argument("--save_path", required=True)
    parser.add_argument("--test_types", default=None)
    parser.add_argument("--num_workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max_tokens", type=int, default=2048)
    parser.add_argument("--max_tool_rounds", type=int, default=2)
    parser.add_argument("--zoom_min_side", type=int, default=672)
    parser.add_argument("--zoom_max_side", type=int, default=2048)
    parser.add_argument("--request_timeout", type=float, default=600.0)
    parser.add_argument("--retries", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    unset = ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"]
    for key in unset:
        os.environ.pop(key, None)

    model = resolve_served_model(args.api_url, args.eval_model_name)
    output_root = Path(args.save_path) / args.model_name
    output_root.mkdir(parents=True, exist_ok=True)

    if args.bench == "vstar":
        test_types = [item.strip() for item in (args.test_types or "direct_attributes,relative_position").split(",") if item.strip()]
        for test_type in test_types:
            items = load_vstar_items(Path(args.vstar_bench_path), test_type, args.limit)
            rows = run_items(items, process_vstar_item, args, model, f"Processing V* {test_type} {args.mode}")
            write_jsonl(output_root / f"result_{test_type}_{args.model_name}.jsonl", rows)
    else:
        test_types = [item.strip() for item in (args.test_types or "hr_bench_4k").split(",") if item.strip()]
        for test_type in test_types:
            items = load_hrbench_items(Path(args.hrbench_path), test_type, args.limit)
            rows = run_items(items, process_hrbench_item, args, model, f"Processing HRBench {test_type} {args.mode}")
            write_jsonl(output_root / f"result_{test_type}_{args.model_name}.jsonl", rows)


if __name__ == "__main__":
    main()
