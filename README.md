# EDA Flow Simulator

A small personal project that simulates VLSI-like workflows. It demonstrates a simple, reproducible flow for learning and experimentation.

Project overview
- config.json: flow configuration
- run_flow.sh: runs the simulated flow and generates logs
- fake_logs/: directory containing generated log files
- log_analyzer.py: analyzes logs and extracts metrics
- summary_report: final report produced by the analyzer

Getting started
1. Update config.json with desired settings.
2. Run the flow:

```bash
./run_flow.sh
```

3. Analyze logs (if not run automatically):

```bash
python3 log_analyzer.py
```

Notes
- This project is intentionally simple and intended for learning purposes.
- Contributions and improvements are welcome.

