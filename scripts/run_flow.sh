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

FREQ=$(python3 - <<'PY'
import json

with open("config/global_cfg.json", encoding="utf-8") as f:
    config = json.load(f)

print(config["target_frequency_mhz"])
PY
)

while IFS=$'\t' read -r STAGE CRITICAL ERROR_CHANCE; do
    echo -n "Running stage: [${STAGE^^}] ... "
    sleep 0.5

    GATE_COUNT=$(( ( RANDOM % 100000 ) + 5000 ))
    ROLL=$(( RANDOM % 100 ))

    if [ "$ROLL" -lt "$ERROR_CHANCE" ]; then
        SLACK_INT=$(( ( RANDOM % 10 ) + 1 ))
        SLACK="-0.$SLACK_INT"
        STATUS_RESULT="ERROR: Timing violations detected! WNS is negative."
    else
        SLACK_INT=$(( RANDOM % 20 ))
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
        if [[ "$CRITICAL" == "True" ]]; then
            echo "----------------------------------------"
            echo "Critical stage [$STAGE] failed. Halting EDA Flow."
            echo "----------------------------------------"
            exit 1
        fi
    else
        echo "PASSED  "
    fi
done < <(python3 - <<'PY'
import json

with open("config/global_cfg.json", encoding="utf-8") as f:
    config = json.load(f)

for stage in config["stages"]:
    print(f"{stage['name']}\t{stage['critical']}\t{stage['error_chance_percentage']}")
PY
)

echo "========================================"
echo "EDA Flow Finished. Logs are ready!"
echo "========================================"
