from src.log_analyzer import parse_log, load_config, analyze_logs
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
