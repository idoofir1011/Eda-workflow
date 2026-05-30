import os, re, sys, argparse, json


def load_config(path):
    path = os.path.abspath(path)
    with open(path, "r") as f:
        return json.load(f)



def analyze_logs():
    logs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))
    report_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "summary_report.md")
    )

    if not os.path.exists(logs_dir):
        print(f"Error: Logs directory not found at {logs_dir}")
        sys.exit(1)

    log_files = [f for f in os.listdir(logs_dir) if f.endswith(".log")]

    if not log_files:
        print("No log files found to analyze.")
        sys.exit(0)

    stage_re = re.compile(r"EDA TOOL RUN LOG -- STAGE:\s*(\w+)")
    gate_re = re.compile(r"Total Gate Count =\s*(\d+)")
    slack_re = re.compile(r"Worst Negative Slack \(WNS\) =\s*([-\d.]+)\s*ns")
    status_re = re.compile(r"\[RESULT\]\s*(.*)")

    report_data = []
    flow_status = "PASSED"

    for file_name in sorted(log_files):
        file_path = os.path.join(logs_dir, file_name)
        with open(file_path, "r") as f:
            content = f.read()

        stage_match = stage_re.search(content)
        gate_match = gate_re.search(content)
        slack_match = slack_re.search(content)
        status_match = status_re.search(content)

        if stage_match:
            stage = stage_match.group(1).upper()
            gates = gate_match.group(1) if gate_match else "N/A"
            slack = slack_match.group(1) if slack_match else "N/A"
            result = status_match.group(1).strip() if status_match else "UNKNOWN"

            status_icon = "🟢 PASS"
            if "ERROR" in result or "FAIL" in result:
                status_icon = "🔴 FAIL"
                flow_status = "FAILED"

            report_data.append(
                {
                    "stage": stage,
                    "status": status_icon,
                    "gates": gates,
                    "slack": slack,
                    "details": result,
                }
            )

   


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze EDA flow logs")
    parser.add_argument(
        "--logs-dir", default="logs", help="Directory containing .log files"
    )
    parser.add_argument(
        "--output", default="summary_report.md", help="Output report path"
    )
    parser.add_argument(
        "--config", default="config/global_cfg.json", help="JSON config path"
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    cfg = load_config(args.config)
    analyze_logs(args.logs_dir, cfg, args.output, args.verbose)
