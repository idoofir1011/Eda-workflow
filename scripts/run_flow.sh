#!/bin/bash

cd "$(dirname "$0")/.." || exit

CONFIG_FILE="config/global_cfg.json"
export CONFIG_FILE
TEMPLATE_FILE="templates/fake_synth.log"
LOGS_DIR="logs"

mkdir -p "$LOGS_DIR"

echo "========================================"
echo " Starting Mini EDA Flow Simulator "
echo "========================================"

mapfile -t STAGES < <(python3 - <<'PY'
import json

with open("config/global_cfg.json", encoding="utf-8") as f:
    config = json.load(f)

for stage in config["stages"]:
    print(stage["name"])
PY
)
FREQ=$(python3 - <<'PY'
import json

with open("config/global_cfg.json", encoding="utf-8") as f:
    config = json.load(f)

print(config["target_frequency_mhz"])
PY
)

for STAGE in "${STAGES[@]}"; do
    echo -n "Running stage: [${STAGE^^}] ... "
    sleep 0.5
    
    GATE_COUNT=$(( ( RANDOM % 100000 ) + 5000 ))
    SLACK_INT=$(( ( RANDOM % 20 ) - 10 ))
    
    if [ $SLACK_INT -lt 0 ]; then
        ABS_SLACK=$(( -SLACK_INT ))
        SLACK="-0.$ABS_SLACK"
        STATUS_RESULT="ERROR: Timing violations detected! WNS is negative."
    else
        SLACK="0.$SLACK_INT"
        STATUS_RESULT="SUCCESS"
    fi

    OUTPUT_LOG="$LOGS_DIR/$STAGE.log"
    
    cat "$TEMPLATE_FILE" | \
        sed "s/{STAGE_NAME}/$STAGE/g" | \
        sed "s/{FREQ}/$FREQ/g" | \
        sed "s/{GATE_COUNT}/$GATE_COUNT/g" | \
        sed "s/{SLACK}/$SLACK/g" | \
        sed "s/{STATUS_RESULT}/$STATUS_RESULT/g" > "$OUTPUT_LOG"

    if [[ "$STATUS_RESULT" == *"ERROR"* ]]; then
        echo "FAILED ❌"
        if [[ "$STAGE" == "compile" || "$STAGE" == "elaboration" || "$STAGE" == "synthesis" ]]; then
            echo "----------------------------------------"
            echo "Critical stage [$STAGE] failed. Halting EDA Flow."
            echo "----------------------------------------"
            exit 1
        fi
    else
        echo "PASSED  "
    fi
done

echo "========================================"
echo "EDA Flow Finished. Logs are ready!"
echo "========================================"