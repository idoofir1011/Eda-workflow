import os
import re
import sys
import argparse
import json
from src.report_generator import generate_markdown_report, generate_html_report


def load_config(path):
    path = os.path.abspath(path)
    with open(path, "r") as f:
        return json.load(f)


def parse_log(content):
    stage_re = re.compile(r"EDA TOOL RUN LOG -- STAGE:\s*(\w+)", re.IGNORECASE)
    gate_re = re.compile(r"Total Gate Count =\s*(\d+)")
    slack_re = re.compile(r"Worst Negative Slack \(WNS\) =\s*([-\d.]+)\s*ns")
    status_re = re.compile(r"\[RESULT\]\s*(.*)")

    stage_match = stage_re.search(content)
    if not stage_match:
        return {
            "stage": "UNKNOWN",
            "gates": "N/A",
            "slack": "N/A",
            "details": "NO_STAGE",
            "status": "🔴 FAIL",
        }

    stage = stage_match.group(1).upper()
    gates = gate_re.search(content)
    slack = slack_re.search(content)
    status = status_re.search(content)

    gates_val = gates.group(1) if gates else "N/A"
    slack_val = slack.group(1) if slack else "N/A"
    details = status.group(1).strip() if status else "UNKNOWN"

    status_icon = "🟢 PASS"
    if "ERROR" in details or "FAIL" in details:
        status_icon = "🔴 FAIL"

    return {
        "stage": stage,
        "gates": gates_val,
        "slack": slack_val,
        "details": details,
        "status": status_icon,
    }


def find_latest_run_dir(runs_root=None):
    """Return the newest runs/<timestamp>/ folder that contains a logs/ subdir."""
    if runs_root is None:
        runs_root = os.path.join(os.path.dirname(__file__), "..", "runs")
    runs_root = os.path.abspath(runs_root)
    if not os.path.isdir(runs_root):
        return None

    candidates = []
    for name in os.listdir(runs_root):
        run_path = os.path.join(runs_root, name)
        if os.path.isdir(run_path) and os.path.isdir(os.path.join(run_path, "logs")):
            candidates.append(run_path)

    if not candidates:
        return None

    return max(candidates, key=lambda path: os.path.basename(path))


def resolve_run_paths(run_dir=None, logs_dir=None, output_path=None):
    """Map a run directory (or explicit paths) to logs and report locations."""
    if run_dir:
        run_dir = os.path.abspath(run_dir)
        logs_dir = os.path.join(run_dir, "logs")
        report_path = os.path.join(run_dir, "summary_report.md")
        if output_path:
            report_path = os.path.abspath(output_path)
        return logs_dir, report_path

    if logs_dir:
        logs_dir = os.path.abspath(logs_dir)
    else:
        logs_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "logs")
        )

    if output_path:
        report_path = os.path.abspath(output_path)
    else:
        report_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "summary_report.md")
        )
    return logs_dir, report_path


def analyze_logs(
    logs_dir=None, config=None, output_path=None, verbose=False, run_dir=None
):
    logs_dir, report_path = resolve_run_paths(run_dir, logs_dir, output_path)

    if not os.path.exists(logs_dir):
        print(f"Error: Logs directory not found at {logs_dir}")
        sys.exit(2)

    log_files = [f for f in os.listdir(logs_dir) if f.endswith(".log")]

    if not log_files:
        print("No log files found to analyze.")
        sys.exit(0)

    report_data = []
    flow_status = "PASSED"
    project_name = (config or {}).get("project_name", "EDA Flow")

    for file_name in sorted(log_files):
        file_path = os.path.join(logs_dir, file_name)
        if verbose:
            print(f"[DEBUG] Reading log: {file_path}")
        with open(file_path, "r") as f:
            content = f.read()

        parsed_log = parse_log(content)
        report_data.append(parsed_log)
        if "FAIL" in parsed_log["status"]:
            flow_status = "FAILED"

    generate_markdown_report(report_data, report_path, flow_status, project_name)
    if report_path.lower().endswith(".md"):
        html_path = report_path[:-3] + ".html"
    else:
        html_path = report_path + ".html"
    generate_html_report(report_data, html_path, flow_status, project_name)

    print(f"Analysis complete. Reports generated at: {report_path} and {html_path}")

    if flow_status == "FAILED":
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze EDA flow logs")
    parser.add_argument(
        "--run-dir",
        default=None,
        help="Run folder (reads logs/ and writes summary_report.md inside it)",
    )
    parser.add_argument(
        "--logs-dir",
        default=None,
        help="Directory containing .log files (ignored when --run-dir is set)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output report path (default: summary_report.md in run dir or project root)",
    )
    parser.add_argument(
        "--config", default="config/global_cfg.json", help="JSON config path"
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    run_dir = args.run_dir
    if run_dir is None and args.logs_dir is None:
        run_dir = find_latest_run_dir()
        if run_dir and args.verbose:
            print(f"[DEBUG] Using latest run directory: {run_dir}")

    cfg = load_config(args.config)
    analyze_logs(
        logs_dir=args.logs_dir,
        config=cfg,
        output_path=args.output,
        verbose=args.verbose,
        run_dir=run_dir,
    )
