"""Mark likely repeats between verbal GOLD and STANDART without merging them."""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "questions.json"


def key(record: dict) -> str:
    options = " ".join(option.get("text") or "" for option in record.get("options") or [])
    text = f"{record.get('prompt') or ''} {options}"
    text = text.casefold().replace("’", "'")
    text = re.sub(r"[^a-zа-яіїєґ0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def main() -> None:
    records = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    gold = [record for record in records if record["source"] == "verbal-gold"]
    standart = [record for record in records if record["source"] == "verbal-standart"]
    gold_keys = [(record, key(record)) for record in gold if record["prompt"]]
    marked = 0
    for record in standart:
        prompt = key(record)
        if len(prompt) < 12:
            continue
        best = None
        best_score = 0.0
        for other, other_key in gold_keys:
            if not other_key:
                continue
            score = SequenceMatcher(None, prompt, other_key).ratio()
            if score > best_score:
                best, best_score = other, score
        if best is not None and best_score >= 0.86:
            record["duplicate_of"] = best["id"]
            if "possible-duplicate" not in record["issues"]:
                record["issues"].append("possible-duplicate")
            if best["duplicate_of"] is None:
                best["duplicate_of"] = record["id"]
            if "possible-duplicate" not in best["issues"]:
                best["issues"].append("possible-duplicate")
            marked += 1
    QUESTIONS.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"possible duplicates {marked}")


if __name__ == "__main__":
    main()
