#!/bin/bash
cd ..
RUN_NAME="gpt-neo-125m"
MODEL_PATH="EleutherAI/gpt-neo-125m" 
DEBUG_MODE="" # "--debug_mode"
CURRENT_DATETIME=$(date "+%Y-%m-%d_%H:%M:%S")

benchmarks_req_open_ai_keys=("self_check_consistency")
if [ -z "${OPENAI_API_KEY}" ] | [ -z "${OPENAI_ORG}" ]; then
  echo -e "[COMPL-AI] Warning: 'OPENAI_API_KEY' and 'OPENAI_ORG' variables are not set."
  echo -e "[COMPL-AI] Please set them to avoid skipping the following benchmarks that use it:"

  # Loop through the list and print each string
  for item in "${benchmarks_req_open_ai_keys[@]}"; do
    echo "[COMPL-AI]   - $item"
  done
fi

run_job () {
  batch_size=${2:-10}
  model_config=${3:-"configs/models/default_model.yaml"}
  answers_file=${4:-""}
        poetry run python3 run.py $DEBUG_MODE \
        --model_config=$model_config \
        --model=$MODEL_PATH \
        --batch_size=$batch_size \
        --results_folder="runs/$RUN_NAME/$CURRENT_DATETIME" \
        --answers_file=$answers_file \
        $1 \
	> "runs/$RUN_NAME/$CURRENT_DATETIME/$(echo $1 | sed 's#/#_#g').log" \
	2> "runs/$RUN_NAME/$CURRENT_DATETIME/$(echo $1 | sed 's#/#_#g').errors"
}


mkdir -p runs/$RUN_NAME/$CURRENT_DATETIME


run_job configs/consistency/self_check_consistency.yaml

poetry run python3 helper_tools/results_processor.py --parent_dir=runs/$RUN_NAME/$CURRENT_DATETIME --model_name=$MODEL_PATH
