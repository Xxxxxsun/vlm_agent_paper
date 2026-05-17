#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR=${PROJECT_DIR:-/root/training-v2}
DEEPEYES_DIR=${DEEPEYES_DIR:-/root/DeepEyes}
VENV_BIN=${VENV_BIN:-/root/.venvs/vtool-r1-v2/bin}
LOG_DIR=${LOG_DIR:-$PROJECT_DIR/logs/qwen25vl7b_agent_eval}
mkdir -p "$LOG_DIR"

MODEL_PATH=${MODEL_PATH:-/root/Qwen2.5-VL-7B-Instruct}
RUN_STAMP=${RUN_STAMP:-$(date +%Y%m%d_%H%M%S)}
BASE_RUN_NAME=${BASE_RUN_NAME:-qwen25vl7b_baseline_${RUN_STAMP}}
TOOL_RUN_NAME=${TOOL_RUN_NAME:-qwen25vl7b_skill_zoom_${RUN_STAMP}}
SELECTIVE_RUN_NAME=${SELECTIVE_RUN_NAME:-qwen25vl7b_selective_skill_zoom_${RUN_STAMP}}
FOCUS_RUN_NAME=${FOCUS_RUN_NAME:-qwen25vl7b_focus_skill_zoom_${RUN_STAMP}}
OUTPUT_DIR=${OUTPUT_DIR:-$PROJECT_DIR/eval/qwen25vl7b_agent_results}
VSTAR_PATH=${VSTAR_PATH:-/root/data/vstar_bench}
HRBENCH_PATH=${HRBENCH_PATH:-/root/data/hr_bench}
CHAT_TEMPLATE_PATH=${CHAT_TEMPLATE_PATH:-$PROJECT_DIR/eval/deepeyes_tool_chat_template.jinja}

SERVED_MODEL_NAME=${SERVED_MODEL_NAME:-qwen25vl7b_agent_eval}
MODEL_PORT=${MODEL_PORT:-18080}
MODEL_API_BASE=${MODEL_API_BASE:-http://127.0.0.1:$MODEL_PORT/v1}
MODEL_TP_SIZE=${MODEL_TP_SIZE:-4}
MODEL_GPU_UTIL=${MODEL_GPU_UTIL:-0.80}
MODEL_MAX_LEN=${MODEL_MAX_LEN:-32768}
EVAL_GPUS=${EVAL_GPUS:-0,1,2,3}
IDLE_FILL_GPUS=${IDLE_FILL_GPUS-4,5,6,7}
NUM_WORKERS=${NUM_WORKERS:-8}
LIMIT=${LIMIT:-}

JUDGE_API_BASE=${JUDGE_API_BASE:-http://33.3.170.35:8000/v1}
JUDGE_MODEL=${JUDGE_MODEL:-}
REFILL_GPU_AFTER=${REFILL_GPU_AFTER:-1}
RUN_BASELINE=${RUN_BASELINE:-1}
RUN_SKILL_TOOL=${RUN_SKILL_TOOL:-1}
RUN_SELECTIVE=${RUN_SELECTIVE:-0}
RUN_FOCUS=${RUN_FOCUS:-0}
RUN_JUDGE=${RUN_JUDGE:-1}
RUN_VSTAR=${RUN_VSTAR:-1}
RUN_HRBENCH=${RUN_HRBENCH:-1}

cd "$PROJECT_DIR"
export PATH="$VENV_BIN:$PATH"
export PYTHONPATH="$DEEPEYES_DIR:$PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=${PYTHONUNBUFFERED:-1}
export VLLM_USE_V1=${VLLM_USE_V1:-1}
export OPENAI_API_KEY="${OPENAI_API_KEY:-EMPTY}"

stop_gpu_fill() {
    if pgrep -f '[/]root/gpu_fill.py' >/dev/null; then
        pkill -TERM -f '[/]root/gpu_fill.py' 2>/dev/null || true
        sleep 2
        pkill -KILL -f '[/]root/gpu_fill.py' 2>/dev/null || true
    fi
}

start_gpu_fill() {
    if [[ "$REFILL_GPU_AFTER" != "1" ]]; then
        return
    fi
    if pgrep -f '[/]root/gpu_fill.py' >/dev/null; then
        return
    fi
    setsid /usr/bin/python /root/gpu_fill.py \
        --devices all \
        --mem-fraction "${GPU_FILL_MEM_FRACTION:-0.70}" \
        --reserve-gb "${GPU_FILL_RESERVE_GB:-10}" \
        --matrix-size "${GPU_FILL_MATRIX_SIZE:-4096}" \
        >/tmp/gpu_fill.log 2>&1 &
    echo $! >/tmp/gpu_fill.pid
}

start_idle_gpu_fill() {
    if [[ -z "$IDLE_FILL_GPUS" ]]; then
        return
    fi
    setsid /usr/bin/python /root/gpu_fill.py \
        --devices "$IDLE_FILL_GPUS" \
        --mem-fraction "${IDLE_GPU_FILL_MEM_FRACTION:-0.70}" \
        --reserve-gb "${IDLE_GPU_FILL_RESERVE_GB:-10}" \
        --matrix-size "${IDLE_GPU_FILL_MATRIX_SIZE:-4096}" \
        >/tmp/gpu_fill_idle.log 2>&1 &
    IDLE_FILL_PID=$!
    echo "$IDLE_FILL_PID" >/tmp/gpu_fill_idle.pid
}

resolve_model() {
    local base_url="$1"
    "$VENV_BIN/python" - "$base_url" <<'PY'
import sys
import requests

session = requests.Session()
session.trust_env = False
response = session.get(sys.argv[1].rstrip("/") + "/models", timeout=10)
response.raise_for_status()
data = response.json().get("data", [])
if not data:
    raise SystemExit("no models returned")
print(data[0]["id"])
PY
}

wait_model_server() {
    local base_url="$1"
    local server_pid="${2:-}"
    for _ in $(seq 1 180); do
        if [[ -n "$server_pid" ]] && ! kill -0 "$server_pid" 2>/dev/null; then
            echo "model server process exited before ready" >&2
            return 1
        fi
        if "$VENV_BIN/python" - "$base_url" <<'PY' >/dev/null 2>&1
import sys
import requests

session = requests.Session()
session.trust_env = False
response = session.get(sys.argv[1].rstrip("/") + "/models", timeout=5)
response.raise_for_status()
PY
        then
            return 0
        fi
        sleep 5
    done
    return 1
}

cleanup() {
    local status=$?
    if [[ -n "${IDLE_FILL_PID:-}" ]]; then
        kill -TERM -- "-$IDLE_FILL_PID" >/dev/null 2>&1 || kill "$IDLE_FILL_PID" >/dev/null 2>&1 || true
        wait "$IDLE_FILL_PID" >/dev/null 2>&1 || true
    fi
    if [[ -n "${VLLM_PID:-}" ]]; then
        kill "$VLLM_PID" >/dev/null 2>&1 || true
        wait "$VLLM_PID" >/dev/null 2>&1 || true
    fi
    stop_gpu_fill
    start_gpu_fill
    exit "$status"
}

trap cleanup EXIT

if [[ ! -d "$MODEL_PATH" ]]; then
    echo "MODEL_PATH does not exist: $MODEL_PATH" >&2
    exit 2
fi
if [[ ! -f "$CHAT_TEMPLATE_PATH" ]]; then
    echo "CHAT_TEMPLATE_PATH does not exist: $CHAT_TEMPLATE_PATH" >&2
    exit 2
fi
if [[ ! -d "$VSTAR_PATH/direct_attributes" || ! -d "$VSTAR_PATH/relative_position" ]]; then
    echo "V* benchmark not found under $VSTAR_PATH" >&2
    exit 2
fi
if [[ ! -f "$HRBENCH_PATH/hr_bench_4k.tsv" ]]; then
    echo "HRBench4K TSV not found: $HRBENCH_PATH/hr_bench_4k.tsv" >&2
    exit 2
fi

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
export NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,0.0.0.0,33.3.170.35}"
export no_proxy="$NO_PROXY"

if [[ "$RUN_JUDGE" == "1" && -z "$JUDGE_MODEL" ]]; then
    JUDGE_MODEL="$(resolve_model "$JUDGE_API_BASE")"
fi

echo "[$(date -Is)] stopping gpu filler before qwen25vl7b eval"
stop_gpu_fill

VLLM_LOG="$LOG_DIR/${RUN_STAMP}_vllm.log"
echo "[$(date -Is)] serving $MODEL_PATH on $MODEL_API_BASE"
(
    export CUDA_VISIBLE_DEVICES="$EVAL_GPUS"
    exec "$VENV_BIN/vllm" serve "$MODEL_PATH" \
        --host 127.0.0.1 \
        --port "$MODEL_PORT" \
        --served-model-name "$SERVED_MODEL_NAME" \
        --tensor-parallel-size "$MODEL_TP_SIZE" \
        --gpu-memory-utilization "$MODEL_GPU_UTIL" \
        --max-model-len "$MODEL_MAX_LEN" \
        --limit-mm-per-prompt '{"image": 32}' \
        --chat-template "$CHAT_TEMPLATE_PATH" \
        --trust-remote-code
) >"$VLLM_LOG" 2>&1 &
VLLM_PID=$!

wait_model_server "$MODEL_API_BASE" "$VLLM_PID"
start_idle_gpu_fill

limit_args=()
if [[ -n "$LIMIT" ]]; then
    limit_args=(--limit "$LIMIT")
fi

run_generation() {
    local mode="$1"
    local run_name="$2"
    if [[ "$RUN_VSTAR" == "1" ]]; then
        echo "[$(date -Is)] running V* generation mode=$mode run=$run_name"
        "$VENV_BIN/python" "$PROJECT_DIR/eval/eval_vstar_hrbench_agent_tool.py" \
            --bench vstar \
            --mode "$mode" \
            --model_name "$run_name" \
            --api_key EMPTY \
            --api_url "$MODEL_API_BASE" \
            --vstar_bench_path "$VSTAR_PATH" \
            --save_path "$OUTPUT_DIR" \
            --eval_model_name "$SERVED_MODEL_NAME" \
            --num_workers "$NUM_WORKERS" \
            "${limit_args[@]}" \
            2>&1 | tee "$LOG_DIR/${run_name}_vstar_generate.log"

        echo "[$(date -Is)] judging V* run=$run_name"
        if [[ "$RUN_JUDGE" == "1" ]]; then
        "$VENV_BIN/python" "$DEEPEYES_DIR/eval/judge_result.py" \
            --model_name "$run_name" \
            --api_key EMPTY \
            --api_url "$JUDGE_API_BASE" \
            --vstar_bench_path "$VSTAR_PATH" \
            --save_path "$OUTPUT_DIR" \
            --eval_model_name "$JUDGE_MODEL" \
            --num_workers "$NUM_WORKERS" \
            2>&1 | tee "$LOG_DIR/${run_name}_vstar_judge.log"
        cp "$OUTPUT_DIR/$run_name/final_acc.json" "$OUTPUT_DIR/$run_name/final_acc_vstar.json"
        else
            echo "[$(date -Is)] skipping V* judge because RUN_JUDGE=0"
        fi
    fi

    if [[ "$RUN_HRBENCH" == "1" ]]; then
        echo "[$(date -Is)] running HRBench4K generation mode=$mode run=$run_name"
        "$VENV_BIN/python" "$PROJECT_DIR/eval/eval_vstar_hrbench_agent_tool.py" \
            --bench hrbench \
            --mode "$mode" \
            --model_name "$run_name" \
            --api_key EMPTY \
            --api_url "$MODEL_API_BASE" \
            --hrbench_path "$HRBENCH_PATH" \
            --save_path "$OUTPUT_DIR" \
            --eval_model_name "$SERVED_MODEL_NAME" \
            --num_workers "$NUM_WORKERS" \
            --test_types hr_bench_4k \
            "${limit_args[@]}" \
            2>&1 | tee "$LOG_DIR/${run_name}_hrbench4k_generate.log"

        echo "[$(date -Is)] judging HRBench4K run=$run_name"
        if [[ "$RUN_JUDGE" == "1" ]]; then
        "$VENV_BIN/python" "$DEEPEYES_DIR/eval/judge_result_hrbench.py" \
            --model_name "$run_name" \
            --api_key EMPTY \
            --api_url "$JUDGE_API_BASE" \
            --hrbench_path "$HRBENCH_PATH" \
            --save_path "$OUTPUT_DIR" \
            --eval_model_name "$JUDGE_MODEL" \
            --num_workers "$NUM_WORKERS" \
            --test_types hr_bench_4k \
            2>&1 | tee "$LOG_DIR/${run_name}_hrbench4k_judge.log"
        cp "$OUTPUT_DIR/$run_name/final_acc.json" "$OUTPUT_DIR/$run_name/final_acc_hrbench4k.json"
        else
            echo "[$(date -Is)] skipping HRBench4K judge because RUN_JUDGE=0"
        fi
    fi
}

if [[ "$RUN_BASELINE" == "1" ]]; then
    run_generation baseline "$BASE_RUN_NAME"
fi
if [[ "$RUN_SKILL_TOOL" == "1" ]]; then
    run_generation skill_tool "$TOOL_RUN_NAME"
fi
if [[ "$RUN_SELECTIVE" == "1" ]]; then
    run_generation selective_skill_tool "$SELECTIVE_RUN_NAME"
fi
if [[ "$RUN_FOCUS" == "1" ]]; then
    run_generation focus_skill_tool "$FOCUS_RUN_NAME"
fi

echo "[$(date -Is)] qwen25vl7b eval finished"
echo "baseline=$OUTPUT_DIR/$BASE_RUN_NAME"
echo "skill_tool=$OUTPUT_DIR/$TOOL_RUN_NAME"
echo "selective_skill_tool=$OUTPUT_DIR/$SELECTIVE_RUN_NAME"
echo "focus_skill_tool=$OUTPUT_DIR/$FOCUS_RUN_NAME"
