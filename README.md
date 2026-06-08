# EDA Flow Simulator

A small personal project that simulates VLSI-like workflows. It demonstrates a config-driven compile → elaboration → synthesis → STA flow for learning and experimentation.

## Project layout

| Path | Purpose |
|------|---------|
| `config/global_cfg.json` | Flow config: stages, MHz, critical flags, error rates |
| `scripts/run_flow.sh` | Runs the simulated flow and archives each run |
| `runs/<timestamp>/` | One folder per flow run (logs, manifest, reports) |
| `runs/<timestamp>/logs/` | Generated `.log` files (one per stage) |
| `runs/<timestamp>/manifest.json` | Run metadata: pass/fail, config snapshot, stage counts |
| `src/log_analyzer.py` | Parses logs and generates summary reports |
| `src/report_generator.py` | Markdown and HTML report formatting |
| `templates/fake_synth.log` | Log template used by the runner |

## Getting started

From the project root:

```bash
# Activate virtual environment (first time: python3 -m venv .venv)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the simulated flow (creates runs/<timestamp>/)
./scripts/run_flow.sh

# Analyze the latest run and write reports inside that folder
python3 -m src.log_analyzer --config config/global_cfg.json

# Or target a specific run explicitly
python3 -m src.log_analyzer --run-dir runs/20260608_111154 --config config/global_cfg.json
```

Edit `config/global_cfg.json` to change stages, target frequency, per-stage error rates, or which stages halt the flow on failure.

## Exit codes

| Code | Component | Meaning |
|------|-----------|---------|
| `0` | `run_flow.sh` / `log_analyzer` | All stages passed; analysis completed with no failures. |
| `1` | `run_flow.sh` / `log_analyzer` | Stage failure (critical halt or any failed stage, including non-critical STA). |
| `2` | `log_analyzer` | Analysis error (e.g. logs directory not found). |

Each run gets its own `runs/<timestamp>/` folder so consecutive runs can be compared side by side. Set `LOGS_DIR` to override the output location (used by tests).

## Tests

```bash
pytest -v
```

## Notes

- This project is intentionally simple and intended for learning purposes.
- See `docs/EDA_PROJECT_PLAN.md` for the phased roadmap.
