from src.log_analyzer import (
    parse_log,
    load_config,
    analyze_logs,
    find_latest_run_dir,
    apply_wns_threshold,
    compare_to_golden,
    check_golden_regression,
    annotate_golden_comparison,
    save_golden,
    load_golden,
)
import json
import pytest
import os


def test_parse_log_success():
    sample = (
        "==================================================================\n"
        "EDA TOOL RUN LOG -- STAGE: synthesis\n"
        "==================================================================\n"
        "[DATA] Total Gate Count = 12345\n"
        "[DATA] Worst Negative Slack (WNS) = 0.12 ns\n"
        "\n"
        "--- RUN STATUS ---\n"
        "[RESULT] SUCCESS\n"
        "==================================================================\n"
    )
    parsed = parse_log(sample)
    assert parsed["stage"] == "SYNTHESIS"
    assert parsed["gates"] == "12345"
    assert parsed["slack"] == "0.12"
    assert "SUCCESS" in parsed["details"]
    assert parsed["status"].startswith("🟢")


def test_parse_log_error():
    sample = (
        "EDA TOOL RUN LOG -- STAGE: compile\n"
        "[DATA] Total Gate Count = 54321\n"
        "[DATA] Worst Negative Slack (WNS) = -0.25 ns\n"
        "[RESULT] ERROR: Timing violations detected! WNS is negative.\n"
    )
    parsed = parse_log(sample)
    assert parsed["stage"] == "COMPILE"
    assert parsed["gates"] == "54321"
    assert parsed["slack"] == "-0.25"
    assert "ERROR" in parsed["details"]
    assert parsed["status"].startswith("🔴")


def test_parse_log_missing_stage():
    sample = (
        "[DATA] Total Gate Count = 1000\n"
        "[DATA] Worst Negative Slack (WNS) = 1.00 ns\n"
        "[RESULT] NO STAGE HEADER PRESENT\n"
    )
    parsed = parse_log(sample)
    assert parsed["stage"] == "UNKNOWN"
    assert parsed["gates"] == "N/A"
    assert parsed["slack"] == "N/A"
    assert parsed["details"] == "NO_STAGE"
    assert parsed["status"].startswith("🔴")


def test_load_config(tmp_path):
    cfg = {"flow": "test", "option": 1}
    cfg_file = tmp_path / "cfg.json"
    cfg_file.write_text(json.dumps(cfg))
    loaded = load_config(str(cfg_file))
    assert loaded == cfg


def test_analyze_logs_no_logs(tmp_path):
    logs_dir = tmp_path / "logs_empty"
    logs_dir.mkdir()
    with pytest.raises(SystemExit) as exc:
        analyze_logs(
            str(logs_dir),
            config=None,
            output_path=str(tmp_path / "out.md"),
            verbose=False,
        )
    assert exc.value.code == 0


def test_analyze_logs_creates_reports(tmp_path, monkeypatch):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    synth = (
        "EDA TOOL RUN LOG -- STAGE: synthesis\n"
        "[DATA] Total Gate Count = 111\n"
        "[DATA] Worst Negative Slack (WNS) = 0.50 ns\n"
        "[RESULT] SUCCESS\n"
    )
    compile_err = (
        "EDA TOOL RUN LOG -- STAGE: compile\n"
        "[DATA] Total Gate Count = 222\n"
        "[DATA] Worst Negative Slack (WNS) = -0.75 ns\n"
        "[RESULT] ERROR: timing\n"
    )

    (logs_dir / "01-synthesis.log").write_text(synth)
    (logs_dir / "02-compile.log").write_text(compile_err)

    calls = {"md": [], "html": []}

    def fake_md(report_data, report_path, flow_status, project_name="EDA Flow"):
        calls["md"].append((list(report_data), report_path, flow_status, project_name))

    def fake_html(report_data, report_path, flow_status, project_name="EDA Flow"):
        calls["html"].append((list(report_data), report_path, flow_status, project_name))

    monkeypatch.setattr("src.log_analyzer.generate_markdown_report", fake_md)
    monkeypatch.setattr("src.log_analyzer.generate_html_report", fake_html)

    out_md = tmp_path / "summary_report.md"
    with pytest.raises(SystemExit) as exc:
        analyze_logs(str(logs_dir), config=None, output_path=str(out_md), verbose=False)
    assert exc.value.code == 1

    # markdown and html reports are written once after all logs are processed
    assert len(calls["md"]) == 1
    assert len(calls["html"]) == 1

    report_data, _, html_status, _ = calls["html"][0]
    stages = {entry["stage"] for entry in report_data}
    assert stages == {"SYNTHESIS", "COMPILE"}
    assert html_status == "FAILED"


def test_analyze_logs_uses_project_name_from_config(tmp_path, monkeypatch):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "synthesis.log").write_text(
        "EDA TOOL RUN LOG -- STAGE: synthesis\n"
        "[DATA] Total Gate Count = 100\n"
        "[DATA] Worst Negative Slack (WNS) = 0.10 ns\n"
        "[RESULT] SUCCESS\n"
    )

    captured = {}

    def fake_md(report_data, report_path, flow_status, project_name="EDA Flow"):
        captured["project_name"] = project_name

    def fake_html(report_data, report_path, flow_status, project_name="EDA Flow"):
        pass

    monkeypatch.setattr("src.log_analyzer.generate_markdown_report", fake_md)
    monkeypatch.setattr("src.log_analyzer.generate_html_report", fake_html)

    cfg = {"project_name": "Mini_EDA_Processor"}
    analyze_logs(
        str(logs_dir),
        config=cfg,
        output_path=str(tmp_path / "out.md"),
        verbose=False,
    )
    assert captured["project_name"] == "Mini_EDA_Processor"


def test_find_latest_run_dir_picks_newest_timestamp(tmp_path):
    runs_root = tmp_path / "runs"
    older = runs_root / "20260101_120000"
    newer = runs_root / "20260102_120000"
    (older / "logs").mkdir(parents=True)
    (newer / "logs").mkdir(parents=True)

    latest = find_latest_run_dir(str(runs_root))
    assert latest == str(newer)


def test_find_latest_run_dir_returns_none_when_missing(tmp_path):
    assert find_latest_run_dir(str(tmp_path / "runs")) is None


def test_analyze_logs_with_run_dir_writes_reports_inside_run(tmp_path, monkeypatch):
    run_dir = tmp_path / "runs" / "20260101_120000"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True)
    (logs_dir / "synthesis.log").write_text(
        "EDA TOOL RUN LOG -- STAGE: synthesis\n"
        "[DATA] Total Gate Count = 100\n"
        "[DATA] Worst Negative Slack (WNS) = 0.10 ns\n"
        "[RESULT] SUCCESS\n"
    )

    captured = {}

    def fake_md(report_data, report_path, flow_status, project_name="EDA Flow"):
        captured["report_path"] = report_path

    def fake_html(report_data, report_path, flow_status, project_name="EDA Flow"):
        pass

    monkeypatch.setattr("src.log_analyzer.generate_markdown_report", fake_md)
    monkeypatch.setattr("src.log_analyzer.generate_html_report", fake_html)

    analyze_logs(run_dir=str(run_dir), config=None, verbose=False)
    assert captured["report_path"] == str(run_dir / "summary_report.md")


def test_apply_wns_threshold_fails_when_below_minimum():
    parsed = {
        "stage": "SYNTHESIS",
        "gates": "1000",
        "slack": "-0.10",
        "details": "SUCCESS",
        "status": "🟢 PASS",
    }
    result = apply_wns_threshold(parsed, 0.0)
    assert result["status"].startswith("🔴")
    assert "below minimum" in result["details"]


def test_apply_wns_threshold_passes_when_at_or_above_minimum():
    parsed = {
        "stage": "SYNTHESIS",
        "gates": "1000",
        "slack": "0.05",
        "details": "SUCCESS",
        "status": "🟢 PASS",
    }
    assert apply_wns_threshold(parsed, 0.05) == parsed
    assert apply_wns_threshold(parsed, 0.0)["status"].startswith("🟢")


def test_apply_wns_threshold_skipped_when_not_configured():
    parsed = {
        "stage": "SYNTHESIS",
        "gates": "1000",
        "slack": "-0.50",
        "details": "SUCCESS",
        "status": "🟢 PASS",
    }
    assert apply_wns_threshold(parsed, None) == parsed


def test_apply_wns_threshold_coerces_string_threshold():
    parsed = {
        "stage": "SYNTHESIS",
        "gates": "1000",
        "slack": "-0.10",
        "details": "SUCCESS",
        "status": "🟢 PASS",
    }
    result = apply_wns_threshold(parsed, "0.0")
    assert result["status"].startswith("🔴")


def test_apply_wns_threshold_skipped_when_threshold_invalid():
    parsed = {
        "stage": "SYNTHESIS",
        "gates": "1000",
        "slack": "-0.10",
        "details": "SUCCESS",
        "status": "🟢 PASS",
    }
    assert apply_wns_threshold(parsed, "not-a-number") == parsed


def test_apply_wns_threshold_preserves_existing_error_details():
    parsed = {
        "stage": "STA",
        "gates": "1000",
        "slack": "-0.90",
        "details": "ERROR: Timing violations detected! WNS is negative.",
        "status": "🔴 FAIL",
    }
    result = apply_wns_threshold(parsed, 0.0)
    assert result["status"].startswith("🔴")
    assert "ERROR" in result["details"]


def test_analyze_logs_wns_threshold_marks_flow_failed(tmp_path, monkeypatch):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "synthesis.log").write_text(
        "EDA TOOL RUN LOG -- STAGE: synthesis\n"
        "[DATA] Total Gate Count = 100\n"
        "[DATA] Worst Negative Slack (WNS) = -0.05 ns\n"
        "[RESULT] SUCCESS\n"
    )

    captured = {}

    def fake_md(report_data, report_path, flow_status, project_name="EDA Flow"):
        captured["report_data"] = list(report_data)
        captured["flow_status"] = flow_status

    def fake_html(report_data, report_path, flow_status, project_name="EDA Flow"):
        pass

    monkeypatch.setattr("src.log_analyzer.generate_markdown_report", fake_md)
    monkeypatch.setattr("src.log_analyzer.generate_html_report", fake_html)

    with pytest.raises(SystemExit) as exc:
        analyze_logs(
            str(logs_dir),
            config={"wns_min_ns": 0.0},
            output_path=str(tmp_path / "out.md"),
            verbose=False,
        )
    assert exc.value.code == 1
    assert captured["flow_status"] == "FAILED"
    assert captured["report_data"][0]["status"].startswith("🔴")


def test_analyze_logs_missing_logs_dir_exits_with_code_2(tmp_path):
    with pytest.raises(SystemExit) as exc:
        analyze_logs(
            logs_dir=str(tmp_path / "missing_logs"),
            config=None,
            output_path=str(tmp_path / "out.md"),
            verbose=False,
        )
    assert exc.value.code == 2


def test_compare_to_golden_better_worse_same():
    golden = {"gate_count": 10000, "wns_ns": 0.10}
    better = {
        "stage": "SYNTHESIS",
        "gates": "9000",
        "slack": "0.20",
    }
    worse = {
        "stage": "SYNTHESIS",
        "gates": "12000",
        "slack": "0.05",
    }
    same = {
        "stage": "SYNTHESIS",
        "gates": "10000",
        "slack": "0.10",
    }

    assert "WNS: better" in compare_to_golden(better, golden)
    assert "Gates: better" in compare_to_golden(better, golden)
    assert "WNS: worse" in compare_to_golden(worse, golden)
    assert "Gates: worse" in compare_to_golden(worse, golden)
    assert compare_to_golden(same, golden) == "WNS: same, Gates: same"


def test_compare_to_golden_skips_non_synthesis():
    golden = {"gate_count": 10000, "wns_ns": 0.10}
    parsed = {"stage": "STA", "gates": "10000", "slack": "0.10"}
    assert compare_to_golden(parsed, golden) is None


def test_check_golden_regression_wns_and_gates(tmp_path):
    golden = {"gate_count": 10000, "wns_ns": 0.20}
    config = {
        "golden": {
            "path": str(tmp_path / "golden.json"),
            "wns_regression_max_ns": 0.05,
            "gates_regression_max": 500,
        }
    }
    wns_regressed = {
        "stage": "SYNTHESIS",
        "gates": "10000",
        "slack": "0.10",
    }
    gates_regressed = {
        "stage": "SYNTHESIS",
        "gates": "11000",
        "slack": "0.20",
    }
    within_limits = {
        "stage": "SYNTHESIS",
        "gates": "10400",
        "slack": "0.18",
    }

    assert check_golden_regression(wns_regressed, golden, config) is True
    assert check_golden_regression(gates_regressed, golden, config) is True
    assert check_golden_regression(within_limits, golden, config) is False


def test_annotate_golden_comparison_adds_vs_golden_column(tmp_path):
    golden_path = tmp_path / "golden" / "synthesis.json"
    golden_path.parent.mkdir(parents=True)
    save_golden({"stage": "synthesis", "gate_count": 1000, "wns_ns": 0.10}, str(golden_path))

    report_data = [
        {
            "stage": "COMPILE",
            "gates": "500",
            "slack": "0.50",
            "status": "🟢 PASS",
            "details": "SUCCESS",
        },
        {
            "stage": "SYNTHESIS",
            "gates": "900",
            "slack": "0.15",
            "status": "🟢 PASS",
            "details": "SUCCESS",
        },
    ]
    config = {"golden": {"path": str(golden_path)}}
    assert annotate_golden_comparison(report_data, config) is False
    assert report_data[0]["vs_golden"] == "—"
    assert "WNS: better" in report_data[1]["vs_golden"]
    assert "Gates: better" in report_data[1]["vs_golden"]


def test_analyze_logs_golden_regression_fails_flow(tmp_path, monkeypatch):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    golden_path = tmp_path / "golden" / "synthesis.json"
    golden_path.parent.mkdir(parents=True)
    save_golden({"stage": "synthesis", "gate_count": 1000, "wns_ns": 0.20}, str(golden_path))
    (logs_dir / "synthesis.log").write_text(
        "EDA TOOL RUN LOG -- STAGE: synthesis\n"
        "[DATA] Total Gate Count = 1000\n"
        "[DATA] Worst Negative Slack (WNS) = 0.10 ns\n"
        "[RESULT] SUCCESS\n"
    )

    captured = {}

    def fake_md(report_data, report_path, flow_status, project_name="EDA Flow"):
        captured["report_data"] = list(report_data)
        captured["flow_status"] = flow_status

    def fake_html(report_data, report_path, flow_status, project_name="EDA Flow"):
        pass

    monkeypatch.setattr("src.log_analyzer.generate_markdown_report", fake_md)
    monkeypatch.setattr("src.log_analyzer.generate_html_report", fake_html)

    config = {
        "golden": {
            "path": str(golden_path),
            "wns_regression_max_ns": 0.05,
        }
    }
    with pytest.raises(SystemExit) as exc:
        analyze_logs(
            str(logs_dir),
            config=config,
            output_path=str(tmp_path / "out.md"),
            verbose=False,
        )
    assert exc.value.code == 1
    assert captured["flow_status"] == "FAILED"
    assert "WNS: worse" in captured["report_data"][0]["vs_golden"]


def test_update_golden_writes_baseline(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    golden_path = tmp_path / "golden" / "synthesis.json"
    (logs_dir / "synthesis.log").write_text(
        "EDA TOOL RUN LOG -- STAGE: synthesis\n"
        "[DATA] Total Gate Count = 5432\n"
        "[DATA] Worst Negative Slack (WNS) = 0.33 ns\n"
        "[RESULT] SUCCESS\n"
    )

    config = {"golden": {"path": str(golden_path)}}
    analyze_logs(
        str(logs_dir),
        config=config,
        output_path=str(tmp_path / "out.md"),
        verbose=False,
        update_golden=True,
    )

    saved = load_golden(str(golden_path))
    assert saved["gate_count"] == 5432
    assert saved["wns_ns"] == 0.33


def test_report_generator_includes_vs_golden_column(tmp_path):
    from src.report_generator import generate_markdown_report

    report_data = [
        {
            "stage": "SYNTHESIS",
            "status": "🟢 PASS",
            "gates": "1000",
            "slack": "0.10",
            "vs_golden": "WNS: same, Gates: better (-100)",
            "details": "SUCCESS",
        }
    ]
    out = tmp_path / "report.md"
    generate_markdown_report(report_data, str(out), "PASSED", "Test Project")
    content = out.read_text()
    assert "vs Golden" in content
    assert "WNS: same, Gates: better (-100)" in content
    assert "## Golden Regression (Synthesis)" in content
