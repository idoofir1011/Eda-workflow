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


def project_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def resolve_golden_path(config):
    golden_cfg = (config or {}).get("golden", {})
    path = golden_cfg.get("path", "golden/synthesis.json")
    if not os.path.isabs(path):
        path = os.path.join(project_root(), path)
    return path


def load_golden(path):
    if not os.path.isfile(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


def save_golden(metrics, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(metrics, f, indent=2)
        f.write("\n")


def _metric_verdict(current, golden, higher_is_better):
    """Return (verdict, delta) where verdict is better, worse, or same."""
    delta = current - golden
    if abs(delta) < 1e-9:
        return "same", 0.0
    if higher_is_better:
        verdict = "better" if delta > 0 else "worse"
    else:
        verdict = "better" if delta < 0 else "worse"
    return verdict, delta


def _parse_numeric(value):
    if value in (None, "N/A"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compare_to_golden(parsed_log, golden):
    """Compare synthesis metrics to golden baseline. Returns a summary string or None."""
    if golden is None or parsed_log.get("stage", "").upper() != "SYNTHESIS":
        return None

    golden_gates = _parse_numeric(golden.get("gate_count", golden.get("gates")))
    current_gates = _parse_numeric(parsed_log.get("gates"))
    golden_wns = _parse_numeric(golden.get("wns_ns", golden.get("slack")))
    current_wns = _parse_numeric(parsed_log.get("slack"))

    parts = []
    if current_wns is not None and golden_wns is not None:
        verdict, delta = _metric_verdict(current_wns, golden_wns, higher_is_better=True)
        if verdict == "same":
            parts.append("WNS: same")
        else:
            sign = "+" if delta > 0 else ""
            parts.append(f"WNS: {verdict} ({sign}{delta:.3f} ns)")
    if current_gates is not None and golden_gates is not None:
        verdict, delta = _metric_verdict(
            current_gates, golden_gates, higher_is_better=False
        )
        if verdict == "same":
            parts.append("Gates: same")
        else:
            sign = "+" if delta > 0 else ""
            parts.append(f"Gates: {verdict} ({sign}{int(delta)})")

    return ", ".join(parts) if parts else None


def check_golden_regression(parsed_log, golden, config):
    """Return True when synthesis metrics regress beyond configured limits."""
    if golden is None or parsed_log.get("stage", "").upper() != "SYNTHESIS":
        return False

    golden_cfg = (config or {}).get("golden", {})
    wns_limit = golden_cfg.get("wns_regression_max_ns")
    gates_limit = golden_cfg.get("gates_regression_max")

    golden_gates = _parse_numeric(golden.get("gate_count", golden.get("gates")))
    current_gates = _parse_numeric(parsed_log.get("gates"))
    golden_wns = _parse_numeric(golden.get("wns_ns", golden.get("slack")))
    current_wns = _parse_numeric(parsed_log.get("slack"))

    if wns_limit is not None and current_wns is not None and golden_wns is not None:
        try:
            if golden_wns - current_wns > float(wns_limit):
                return True
        except (TypeError, ValueError):
            pass

    if (
        gates_limit is not None
        and current_gates is not None
        and golden_gates is not None
    ):
        try:
            if current_gates - golden_gates > float(gates_limit):
                return True
        except (TypeError, ValueError):
            pass

    return False


def annotate_golden_comparison(report_data, config):
    """Add vs_golden field to synthesis rows and return whether regression exceeded limits."""
    golden_path = resolve_golden_path(config)
    golden = load_golden(golden_path)
    golden_regression = False

    for entry in report_data:
        if entry.get("stage", "").upper() == "SYNTHESIS":
            vs_golden = compare_to_golden(entry, golden)
            entry["vs_golden"] = vs_golden if vs_golden else "N/A (no golden)"
            if check_golden_regression(entry, golden, config):
                golden_regression = True
        else:
            entry["vs_golden"] = "—"

    return golden_regression


def update_golden_from_report(report_data, config):
    """Write synthesis metrics from the latest run into the golden baseline file."""
    golden_path = resolve_golden_path(config)
    for entry in report_data:
        if entry.get("stage", "").upper() != "SYNTHESIS":
            continue
        gates = _parse_numeric(entry.get("gates"))
        wns = _parse_numeric(entry.get("slack"))
        if gates is None or wns is None:
            print("Error: synthesis log missing gate count or WNS; golden not updated.")
            sys.exit(2)
        metrics = {
            "stage": "synthesis",
            "gate_count": int(gates),
            "wns_ns": wns,
        }
        save_golden(metrics, golden_path)
        print(f"Golden baseline updated at: {golden_path}")
        return
    print("Error: no synthesis stage found in logs; golden not updated.")
    sys.exit(2)


def apply_wns_threshold(parsed_log, wns_min_ns):
    """Mark a stage failed when parsed WNS is below the configured minimum."""
    if wns_min_ns is None:
        return parsed_log

    try:
        threshold = float(wns_min_ns)
    except (TypeError, ValueError):
        return parsed_log

    slack = parsed_log.get("slack", "N/A")
    if slack == "N/A":
        return parsed_log

    try:
        wns = float(slack)
    except ValueError:
        return parsed_log

    if wns < threshold:
        updated = dict(parsed_log)
        updated["status"] = "🔴 FAIL"
        if parsed_log.get("status", "").startswith("🟢"):
            updated["details"] = f"WNS {wns} ns below minimum {threshold} ns"
        return updated

    return parsed_log


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
    logs_dir=None,
    config=None,
    output_path=None,
    verbose=False,
    run_dir=None,
    update_golden=False,
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
    wns_min_ns = (config or {}).get("wns_min_ns")

    for file_name in sorted(log_files):
        file_path = os.path.join(logs_dir, file_name)
        if verbose:
            print(f"[DEBUG] Reading log: {file_path}")
        with open(file_path, "r") as f:
            content = f.read()

        parsed_log = apply_wns_threshold(parse_log(content), wns_min_ns)
        report_data.append(parsed_log)
        if "FAIL" in parsed_log["status"]:
            flow_status = "FAILED"

    if update_golden:
        update_golden_from_report(report_data, config)
        return

    golden_regression = annotate_golden_comparison(report_data, config)
    if golden_regression:
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
    parser.add_argument(
        "--update-golden",
        action="store_true",
        help="Save synthesis metrics from this run as the golden baseline",
    )
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
        update_golden=args.update_golden,
    )
