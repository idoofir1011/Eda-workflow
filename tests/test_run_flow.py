import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUN_FLOW = ROOT / "scripts" / "run_flow.sh"


def _base_config(stages):
    return {
        "project_name": "Test_Flow",
        "target_frequency_mhz": 800,
        "stages": stages,
    }


def _run_flow(config, logs_dir, tmp_path):
    cfg_path = tmp_path / "flow_cfg.json"
    cfg_path.write_text(json.dumps(config), encoding="utf-8")

    env = os.environ.copy()
    env["CONFIG_FILE"] = str(cfg_path)
    env["LOGS_DIR"] = str(logs_dir)
    env["FLOW_SLEEP"] = "0"

    return subprocess.run(
        ["bash", str(RUN_FLOW)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_run_flow_clears_stale_logs(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "stale.log").write_text("old run leftover", encoding="utf-8")

    config = _base_config(
        [
            {"name": "compile", "critical": True, "error_chance_percentage": 0},
        ]
    )
    result = _run_flow(config, logs_dir, tmp_path)

    assert result.returncode == 0
    assert not (logs_dir / "stale.log").exists()
    assert (logs_dir / "compile.log").exists()


def test_run_flow_halts_on_critical_failure(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    config = _base_config(
        [
            {"name": "compile", "critical": True, "error_chance_percentage": 100},
            {"name": "elaboration", "critical": True, "error_chance_percentage": 0},
        ]
    )
    result = _run_flow(config, logs_dir, tmp_path)

    assert result.returncode == 1
    assert "Critical stage [compile] failed" in result.stdout
    assert (logs_dir / "compile.log").exists()
    assert not (logs_dir / "elaboration.log").exists()


def test_run_flow_non_critical_failure_exits_nonzero(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    config = _base_config(
        [
            {"name": "compile", "critical": True, "error_chance_percentage": 0},
            {"name": "sta", "critical": False, "error_chance_percentage": 100},
        ]
    )
    result = _run_flow(config, logs_dir, tmp_path)

    assert result.returncode == 1
    assert "EDA Flow Finished with failures" in result.stdout
    assert (logs_dir / "compile.log").exists()
    assert (logs_dir / "sta.log").exists()
