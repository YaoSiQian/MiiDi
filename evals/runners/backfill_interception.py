"""为既有 evals/results/results.csv 回填「拦截层标签」列（纯后处理，零 API）。

用法：python -m evals.runners.backfill_interception --results evals/results
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from evals.runners.interception import classify_interception


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=Path("evals/results"))
    args = parser.parse_args()

    csv_path = args.results / "results.csv"
    with open(csv_path, newline="") as fh:
        rows = list(csv.DictReader(fh))
        fieldnames = list(rows[0].keys())

    if "intercepted_by" not in fieldnames:
        fieldnames.append("intercepted_by")

    counts: dict[str, int] = {}
    for row in rows:
        if row.get("intercepted_by"):
            continue
        if row.get("error"):
            label = "generation_error"
        else:
            sid = row["sample_id"]
            report_path = args.results / sid / "rule_report.json"
            if not report_path.exists():
                report_path = args.results / f"rerun_{sid}" / "rule_report.json"
            if report_path.exists():
                data = json.loads(report_path.read_text())
                label = classify_interception_type(data)
            else:
                label = "unknown"
        row["intercepted_by"] = label
        counts[label] = counts.get(label, 0) + 1

    with open(csv_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"backfilled {len(rows)} rows: {counts}")


def classify_interception_type(data: dict) -> str:
    """对 rule_report.json 的 dict 形态做与 classify_interception 一致的分层。"""

    class _R:
        invalid = data.get("invalid", False)
        gates = data.get("gates", {})
        R_rule = data.get("R_rule", 0.0)

    return classify_interception(_R())


if __name__ == "__main__":
    main()
