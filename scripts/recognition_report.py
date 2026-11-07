"""Check the question bank against the recognition invariants."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "questions.json"
REPORT = ROOT / "data" / "recognition_report.json"


def numbers(records: list[dict]) -> list[int]:
    return [record["number"] for record in records]


def holes(found: list[int]) -> list[int]:
    return [n for n in range(1, 157) if n not in set(found)]


def main() -> None:
    records = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    by_source: dict[str, list[dict]] = {}
    for record in records:
        by_source.setdefault(record["source"], []).append(record)

    report: dict = {"sources": {}, "ok": True}
    for source in ("abstract", "math", "verbal-gold"):
        group = by_source.get(source, [])
        missing = holes(numbers(group))
        entry = {
            "count": len(group),
            "unique_numbers": len(set(numbers(group))),
            "missing_numbers": missing,
            "low_confidence": sum(1 for record in group if record["confidence"] != "high"),
        }
        if len(group) != 156 or missing:
            report["ok"] = False
        report["sources"][source] = entry

    abstract_bad = []
    for record in by_source.get("abstract", []):
        ids = {option["id"] for option in record["options"]}
        if not record["options"] or not record["correct"] or record["correct"][0] not in ids:
            abstract_bad.append(record["number"])
    report["abstract_figure_problems"] = abstract_bad
    if abstract_bad:
        report["ok"] = False

    diagram_missing = [
        record["number"]
        for record in by_source.get("math", [])
        if record["subtype"] == "number-grid" and not record["stimulus_images"]
    ]
    report["math_grids_missing_image"] = diagram_missing
    if diagram_missing:
        report["ok"] = False

    pair_bad = []
    for record in records:
        if record["source"] not in ("verbal-gold", "verbal-standart") or record["subtype"] != "pair":
            continue
        options = [option["text"] for option in record["options"]]
        if len(options) != 6 or len(record["correct"]) != 2 or not set(record["correct"]).issubset(options):
            pair_bad.append(record["id"])
    report["verbal_pair_problems"] = pair_bad

    standart = by_source.get("verbal-standart", [])
    report["sources"]["verbal-standart"] = {
        "count": len(standart),
        "unique_numbers": len(set(numbers(standart))) if standart else 0,
        "missing_numbers": holes(numbers(standart)) if standart else list(range(1, 157)),
        "low_confidence": sum(1 for record in standart if record["confidence"] != "high"),
    }
    report["duplicates"] = sum(1 for record in records if record.get("duplicate_of"))
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["sources"], ensure_ascii=False, indent=2))
    print("ok", report["ok"], "pairs", len(pair_bad), "duplicates", report["duplicates"])


if __name__ == "__main__":
    main()
