import html
from typing import List, Dict


def generate_md_report(data, out, flow_status):
    with open(data, "w") as r:
        r.write("# EDA Flow Execution Summary Report\n\n")
        r.write(f"**Overall Flow Status:** {flow_status}\n\n")
        r.write("## Stages Metrics Table\n\n")
        r.write("| Stage Name | Status | Gate Count | WNS (ns) | Details |\n")
        r.write("|------------|--------|------------|----------|---------|\n")

        for stage in data:
            r.write(
                f"| {stage['stage']} | {stage['status']} | {stage['gates']} | {stage['slack']} | {stage['details']} |\n"
            )

    print(f"Analysis complete. Report generated at: {out}")


def generate_markdown_report(
    report_data: List[Dict], output_path: str, overall_status: str
) -> None:
    with open(output_path, "w", encoding="utf-8") as r:
        r.write("# EDA Flow Execution Summary Report\n\n")
        r.write(f"**Overall Flow Status:** {overall_status}\n\n")
        r.write("## Stages Metrics Table\n\n")
        r.write("| Stage Name | Status | Gate Count | WNS (ns) | Details |\n")
        r.write("|------------|--------|------------|----------|---------|\n")
        for d in report_data:
            details = d.get("details", "").replace("|", "\\|")
            r.write(
                f"| {d.get('stage','')} | {d.get('status','')} | {d.get('gates','')} | {d.get('slack','')} | {details} |\n"
            )


def generate_html_report(
    report_data: List[Dict], output_path: str, overall_status: str
) -> None:
    rows = []
    for d in report_data:
        stage = html.escape(d.get("stage", ""))
        status = html.escape(d.get("status", ""))
        gates = html.escape(str(d.get("gates", "")))
        slack = html.escape(str(d.get("slack", "")))
        details = html.escape(d.get("details", ""))
        rows.append(
            f"<tr><td>{stage}</td><td>{status}</td><td>{gates}</td><td>{slack}</td><td>{details}</td></tr>"
        )

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>EDA Flow Execution Summary</title>
<style>
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: 6px; text-align: left; }}
  th {{ background: #eee; }}
</style>
</head>
<body>
  <h1>EDA Flow Execution Summary</h1>
  <p><strong>Overall Flow Status:</strong> {html.escape(overall_status)}</p>
  <table>
    <thead><tr><th>Stage Name</th><th>Status</th><th>Gate Count</th><th>WNS (ns)</th><th>Details</th></tr></thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
