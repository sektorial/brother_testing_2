"""Replace GOLD options with the words read from the button images."""

from __future__ import annotations

import json
from pathlib import Path

from parse_bank import gold_correct

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "questions.json"
FIXES = ROOT / "data" / "gold_option_fixes.json"


def refresh(record: dict) -> None:
    options = [option["text"] for option in record["options"]]
    record["correct"] = gold_correct(record["subtype"], record["explanation"], options, record["prompt"])
    issues = []
    if not record["prompt"]:
        issues.append("missing-prompt")
    expected = 6 if record["subtype"] == "pair" else 5
    if len(options) != expected:
        issues.append("options-incomplete")
    if record["subtype"] == "pair" and len(record["correct"]) != 2:
        issues.append("pair-answer-incomplete")
    if record["subtype"] != "pair" and len(record["correct"]) != 1:
        issues.append("missing-answer")
    option_ids = set(options)
    if record["correct"] and not all(answer in option_ids for answer in record["correct"]):
        issues.append("answer-not-in-options")
    record["issues"] = issues
    record["confidence"] = "low" if issues else "high"


def main() -> None:
    records = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    fixes = {int(key): value for key, value in json.loads(FIXES.read_text(encoding="utf-8")).items()}
    for record in records:
        if record["source"] != "verbal-gold":
            continue
        if record["number"] in fixes:
            record["options"] = [
                {"id": word, "text": word, "image": None} for word in fixes[record["number"]]
            ]
        refresh(record)
    QUESTIONS.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    gold = [record for record in records if record["source"] == "verbal-gold"]
    low = [record for record in gold if record["confidence"] != "high"]
    print(f"low {len(low)} / {len(gold)}")
    for record in low:
        print(record["number"], record["subtype"], record["issues"], record["correct"], [o["text"] for o in record["options"]])


if __name__ == "__main__":
    main()
