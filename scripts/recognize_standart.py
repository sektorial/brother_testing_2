"""Read verbal STANDART questions from the page scans.

Each embedded image is a screenshot. Some screenshots repeat one task
(the question, then the explanation); some stack two different tasks.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import winocr
from PIL import Image

from parse_bank import gold_correct, gold_kind, gold_stem_and_options, shell

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "questions.json"
MANIFEST = ROOT / "data" / "raw" / "verbal-standart" / "manifest.json"

LATIN = str.maketrans(
    {
        "a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "x": "х", "y": "у", "i": "і",
        "A": "А", "B": "В", "C": "С", "E": "Е", "H": "Н", "I": "І", "K": "К", "M": "М",
        "O": "О", "P": "Р", "T": "Т", "X": "Х", "Y": "У",
    }
)


def repair(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if re.search(r"[А-Яа-яІіЇїЄєҐґ]", line) and re.search(r"[A-Za-z]", line):
            line = line.translate(LATIN)
        lines.append(line)
    return "\n".join(lines)


def ocr_image(path: Path) -> str:
    image = Image.open(path).convert("RGB")
    if max(image.size) > 1800:
        scale = 1800 / max(image.size)
        image = image.resize((round(image.width * scale), round(image.height * scale)))
    result = winocr.recognize_pil_sync(image, lang="ru")
    return "\n".join(line.get("text") or "" for line in (result.get("lines") or []))


def task_number(text: str) -> int | None:
    match = re.search(r"завдання\s+([0-9ЗзОо]+)", text, flags=re.IGNORECASE)
    if not match:
        return None
    raw = match.group(1).replace("З", "3").replace("з", "3").replace("О", "0").replace("о", "0")
    return int(raw) if raw.isdigit() else None


def chunks(text: str) -> list[str]:
    parts = re.split(r"(?=Приклад завдання)", text)
    parts = [part.strip() for part in parts if "завдання" in part.casefold()]
    return parts or ([text] if text.strip() else [])


def build_record(text: str, image: str, page: int, fallback_number: int) -> dict:
    text = repair(text)
    number = task_number(text) or fallback_number
    kind, interaction = gold_kind(text)
    if "одного порядку" not in text.casefold() and "Визначте" not in text and "=" not in text:
        kind, interaction = "analogy", "single"
    stem, options = gold_stem_and_options(text)
    explanation = ""
    if "Пояснення" in text:
        explanation = text.split("Пояснення", 1)[1]
        explanation = re.sub(r"\s+", " ", explanation).strip(" :.")
    record = shell("verbal", "verbal-standart", number, kind, interaction)
    record["prompt"] = stem
    record["explanation"] = explanation
    record["options"] = [{"id": option, "text": option, "image": None} for option in options]
    record["correct"] = gold_correct(kind, explanation, options, stem)
    record["page_images"] = [image]
    record["source_pages"] = [page]
    issues = []
    if task_number(text) is None:
        issues.append("number-unreadable")
    if not stem:
        issues.append("missing-prompt")
    expected = 6 if kind == "pair" else 5
    if len(options) != expected:
        issues.append("options-incomplete")
    if kind == "pair" and len(record["correct"]) != 2:
        issues.append("pair-answer-incomplete")
    if kind != "pair" and len(record["correct"]) != 1:
        issues.append("missing-answer")
    if record["correct"] and not all(answer in options for answer in record["correct"]):
        issues.append("answer-not-in-options")
    record["issues"] = issues
    record["confidence"] = "low" if issues else "medium"
    record["_score"] = len(explanation) + (20 if record["correct"] else 0)
    return record


def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    drafted = []
    seen = 0
    for page in manifest["pages"]:
        for image in page["images"]:
            seen += 1
            if limit and seen > limit:
                break
            text = ocr_image(ROOT / image["file"])
            for part in chunks(text):
                drafted.append(build_record(part, image["file"], page["page"], seen))
            if seen % 20 == 0:
                print(f"standart images {seen}", flush=True)
        if limit and seen > limit:
            break

    chosen = []
    index_by_number: dict[int, int] = {}
    for record in drafted:
        number = record["number"]
        previous = index_by_number.get(number)
        if previous is None or record["_score"] > chosen[previous]["_score"]:
            if previous is None:
                index_by_number[number] = len(chosen)
                chosen.append(record)
            else:
                chosen[previous] = record
    for record in chosen:
        record.pop("_score", None)

    if limit:
        for record in chosen:
            print(record["number"], record["subtype"], record["confidence"], record["prompt"][:80])
            print(" ", [option["text"] for option in record["options"]], record["correct"], record["issues"])
        print("cards", len(chosen))
        return

    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    questions = [record for record in questions if record["source"] != "verbal-standart"]
    questions.extend(chosen)
    questions.sort(key=lambda record: (record["block"], record["source"], record["number"], record["source_pages"][0]))
    QUESTIONS.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
    low = sum(1 for record in chosen if record["confidence"] != "high")
    print(f"standart {len(chosen)} low-or-medium {low} numbers {min(r['number'] for r in chosen)}..{max(r['number'] for r in chosen)}")


if __name__ == "__main__":
    main()
