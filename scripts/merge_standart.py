"""Merge transcribed STANDART questions into the bank."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "questions.json"
PARTS = [
    ROOT / "data" / "standart_partial.json",
    ROOT / "data" / "standart_06_40.json",
    ROOT / "data" / "standart_41_75.json",
    ROOT / "data" / "standart_76_110.json",
    ROOT / "data" / "standart_111_139.json",
]


def as_record(item: dict) -> dict:
    number = int(item["number"])
    options = item.get("options") or []
    correct = item.get("correct") or []
    issues = list(item.get("issues") or [])
    subtype = item.get("subtype") or "analogy"
    interaction = item.get("interaction") or ("pair" if subtype == "pair" else "single")
    expected = 6 if subtype == "pair" else 5
    if not item.get("prompt"):
        issues.append("missing-prompt")
    if len(options) != expected:
        issues.append("options-incomplete")
    if subtype == "pair" and len(correct) != 2:
        issues.append("pair-answer-incomplete")
    if subtype != "pair" and len(correct) != 1:
        issues.append("missing-answer")
    if correct and not all(answer in options for answer in correct):
        issues.append("answer-not-in-options")
    page = int(item["page"])
    return {
        "id": f"2025-verbal-standart-{number:04d}",
        "library": "2025",
        "block": "verbal",
        "source": "verbal-standart",
        "number": number,
        "subtype": subtype,
        "prompt": item.get("prompt") or "",
        "interaction": interaction,
        "stimulus_images": [],
        "options": [{"id": word, "text": word, "image": None} for word in options],
        "correct": correct,
        "explanation": item.get("explanation") or "",
        "page_images": [f"data/raw/verbal-standart/page-{page:03d}.jpg"],
        "source_pages": [page],
        "confidence": "low" if issues else "high",
        "issues": issues,
        "duplicate_of": None,
    }


def main() -> None:
    incoming = []
    for path in PARTS:
        if not path.exists():
            print("missing", path.name)
            continue
        incoming.extend(json.loads(path.read_text(encoding="utf-8")))
    by_number: dict[int, dict] = {}
    for item in incoming:
        record = as_record(item)
        previous = by_number.get(record["number"])
        if previous is None or len(record["options"]) > len(previous["options"]):
            by_number[record["number"]] = record
    records = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    records = [record for record in records if record["source"] != "verbal-standart"]
    records.extend(by_number[number] for number in sorted(by_number))
    records.sort(key=lambda record: (record["block"], record["source"], record["number"]))
    QUESTIONS.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    numbers = sorted(by_number)
    missing = [n for n in range(1, 157) if n not in by_number]
    print(f"standart {len(by_number)} missing {missing[:30]} count {len(missing)}")


if __name__ == "__main__":
    main()
