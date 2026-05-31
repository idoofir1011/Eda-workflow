from src.log_analyzer import parse_log

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