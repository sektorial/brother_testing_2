"""Recover GOLD answer options from the page image, where the text layer drops words."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf
import winocr
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "questions.json"
BANDS = ROOT / "data" / "raw" / "verbal-gold" / "bands"

WORD = re.compile(r"^[А-ЯІЇЄҐа-яіїєґ'’-]{3,}$")


def gold_pdf() -> Path:
    return next(path for path in (ROOT / "materials").glob("*.pdf") if "GOLD" in path.name)


def clean_word(value: str) -> str | None:
    value = value.strip(" .,;:«»\"")
    if not WORD.fullmatch(value):
        return None
    if re.search(r"[A-Za-z0-9]", value):
        return None
    return value


def same(left: str, right: str) -> bool:
    return left.casefold().replace("’", "'") == right.casefold().replace("’", "'")


def band_image(page: pymupdf.Page) -> Image.Image | None:
    question_bottom = None
    explanation_top = None
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            text = "".join(span["text"] for span in line["spans"]).strip()
            if text.startswith("Пояснення"):
                explanation_top = line["bbox"][1]
            if (
                text.startswith("Визначте")
                or text.startswith("Серед")
                or (":" in text and ("?" in text or "=" in text))
            ):
                question_bottom = line["bbox"][3]
    if question_bottom is None or explanation_top is None or explanation_top - question_bottom < 20:
        return None
    clip = pymupdf.Rect(36, question_bottom + 4, page.rect.width - 36, explanation_top - 4)
    pix = page.get_pixmap(dpi=160, clip=clip)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def ocr_words(image: Image.Image) -> list[str]:
    result = winocr.recognize_pil_sync(image, lang="ru")
    words = []
    for line in result.get("lines") or []:
        for piece in re.split(r"\s+", line.get("text") or ""):
            word = clean_word(piece)
            if word and not any(same(word, existing) for existing in words):
                words.append(word)
    return words


def main() -> None:
    records = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    by_number = {record["number"]: record for record in records if record["source"] == "verbal-gold"}
    doc = pymupdf.open(gold_pdf())
    BANDS.mkdir(parents=True, exist_ok=True)
    recovered = 0
    for index, page in enumerate(doc):
        number = index + 1
        record = by_number[number]
        image = band_image(page)
        if image is None:
            record["issues"].append("band-not-found")
            record["confidence"] = "low"
            continue
        dest = BANDS / f"p{number:03d}.jpg"
        image.save(dest, quality=85)
        found = ocr_words(image)
        current = [option["text"] for option in record["options"]]
        for word in found:
            if not any(same(word, option) for option in current):
                current.append(word)
        record["options"] = [{"id": word, "text": word, "image": None} for word in current]
        record["band_image"] = dest.relative_to(ROOT).as_posix()
        expected = 6 if record["subtype"] == "pair" else 5
        record["issues"] = [issue for issue in record["issues"] if issue != "options-incomplete"]
        option_ids = {option["text"] for option in record["options"]}
        if len(record["options"]) != expected:
            record["issues"].append("options-incomplete")
        else:
            recovered += 1
        if record["correct"] and not all(
            any(same(answer, option) for option in option_ids) for answer in record["correct"]
        ):
            if "answer-not-in-options" not in record["issues"]:
                record["issues"].append("answer-not-in-options")
        else:
            record["issues"] = [issue for issue in record["issues"] if issue != "answer-not-in-options"]
        record["confidence"] = "low" if record["issues"] else "high"
        if number % 20 == 0:
            print(f"gold bands {number}/156", flush=True)
    doc.close()
    QUESTIONS.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    low = [record for record in by_number.values() if record["confidence"] != "high"]
    print(f"complete options {recovered}/156, still low {len(low)}")
    from collections import Counter
    print(Counter(issue for record in low for issue in record["issues"]))


if __name__ == "__main__":
    main()
