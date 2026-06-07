# EDA Flow Simulator

A small personal project that simulates VLSI-like workflows. It demonstrates a config-driven compile → elaboration → synthesis → STA flow for learning and experimentation.

## Project layout

| Path | Purpose |
|------|---------|
| `config/global_cfg.json` | Flow config: stages, MHz, critical flags, error rates |
| `scripts/run_flow.sh` | Runs the simulated flow and writes logs |
| `logs/` | Generated `.log` files (one per stage) |
| `src/log_analyzer.py` | Parses logs and generates summary reports |
| `src/report_generator.py` | Markdown and HTML report formatting |
| `templates/fake_synth.log` | Log template used by the runner |
| `summary_report.md` / `.html` | Reports produced by the analyzer |

## Getting started

From the project root:

```bash
# Activate virtual environment (first time: python3 -m venv .venv)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the simulated flow
./scripts/run_flow.sh

# Analyze logs and generate reports
python3 -m src.log_analyzer --logs-dir logs --output summary_report.md --config config/global_cfg.json
```

Edit `config/global_cfg.json` to change stages, target frequency, per-stage error rates, or which stages halt the flow on failure.

## Tests

```bash
pytest -v
```

## Notes

- This project is intentionally simple and intended for learning purposes.
- See `docs/EDA_PROJECT_PLAN.md` for the phased roadmap.
