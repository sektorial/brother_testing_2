"""Build question records for abstract, math, and the verbal GOLD text draft.

Figures stay image files. GOLD options that the text layer dropped are filled
later from the page images.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "questions.json"

LIBRARY = "2025"

CHROME_EXACT = {
    "назад",
    "далі",
    "завершити тест",
    "psymetrics",
    "тест",
    "відповісти",
    "пропустити",
}


def load_manifest(source: str) -> dict:
    return json.loads((RAW / source / "manifest.json").read_text(encoding="utf-8"))


def page_text(source: str, page: dict) -> str:
    return (ROOT / page["text"]).read_text(encoding="utf-8")


def lines_of(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def is_chrome_line(line: str) -> bool:
    folded = line.casefold().strip(" :.—-")
    if folded in CHROME_EXACT:
        return True
    if "арк" in folded and "№" in line:
        return True
    if folded.startswith("верб"):
        return True
    if re.fullmatch(r"https?://\S+", line):
        return True
    if re.fullmatch(r"\d{1,2}\.\d{2}\.\d{2},?\s*\d{1,2}:\d{2}", line):
        return True
    if re.fullmatch(r"\d+\s*/\s*\d+", line):
        return True
    if re.fullmatch(r"[\-—–]+", line):
        return True
    return False


def clean_explanation(text: str) -> str:
    kept = []
    for line in lines_of(text):
        if is_chrome_line(line):
            continue
        if line.casefold().startswith("пояснення"):
            continue
        kept.append(line)
    return collapse(" ".join(kept)).lstrip(": ").strip()


def shell(block: str, source: str, number: int, subtype: str, interaction: str) -> dict:
    return {
        "id": f"{LIBRARY}-{source}-{number:04d}",
        "library": LIBRARY,
        "block": block,
        "source": source,
        "number": number,
        "subtype": subtype,
        "prompt": "",
        "interaction": interaction,
        "stimulus_images": [],
        "options": [],
        "correct": [],
        "explanation": "",
        "page_images": [],
        "source_pages": [],
        "confidence": "high",
        "issues": [],
        "duplicate_of": None,
    }


def group_pages(source: str, tolerate_forward_jump: bool = False) -> list[dict]:
    manifest = load_manifest(source)
    groups: list[dict] = []
    current = None
    for page in manifest["pages"]:
        text = page_text(source, page)
        match = re.search(r"Приклад завдання\s+(\d+)", text)
        if match:
            number = int(match.group(1))
            # One abstract sheet repeats the previous task but the text layer
            # jumps to a later number. Keep it with the task it actually shows.
            if tolerate_forward_jump and current is not None and number > current["number"] + 1:
                number = current["number"]
            if current is None or current["number"] != number:
                current = {"number": number, "pages": [], "texts": []}
                groups.append(current)
        elif current is None:
            continue
        if not text.strip() and not page["images"]:
            continue
        current["pages"].append(page)
        current["texts"].append(text)
    return groups


def figure_split(images: list[dict]) -> tuple[list[str], list[str]]:
    stimulus, options = [], []
    for image in images:
        if image["width"] >= 280:
            stimulus.append(image["file"])
        else:
            options.append(image["file"])
    return stimulus, options


def first_figure_page(pages: list[dict]) -> dict | None:
    for page in pages:
        if page["images"]:
            return page
    return None


def abstract_prompt(text: str) -> str:
    flat = collapse(text)
    questions = re.findall(r"[^.?]{8,}\?", flat)
    for question in questions:
        if "фігур" in question.casefold() or question.strip().startswith("Як "):
            return question.strip()
    return questions[-1].strip() if questions else ""


def abstract_subtype(text: str) -> str:
    flat = collapse(text.split("Пояснення", 1)[0]).casefold()
    if "трансформац" in flat:
        return "transformation"
    if "послідовн" in flat:
        return "sequence"
    return "odd-one-out"


def abstract_pdf() -> Path:
    matches = [
        path
        for path in (ROOT / "materials").glob("*.pdf")
        if "GOLD" not in path.name and "STANDART" not in path.name and "PSYMETRICS" not in path.name
    ]
    return matches[0]


def crop_abstract_figures(doc: pymupdf.Document, page_number: int, question_number: int) -> tuple[list[str], list[str]]:
    page = doc[page_number - 1]
    boxes = []
    for info in page.get_image_info(xrefs=True):
        bbox = tuple(round(value, 1) for value in info["bbox"])
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        if width < 60 or height < 60:
            continue
        if bbox not in boxes:
            boxes.append(bbox)
    boxes.sort(key=lambda box: (round(box[1], 0), box[0]))
    stimulus, options = [], []
    folder = RAW / "abstract" / "figures"
    folder.mkdir(parents=True, exist_ok=True)
    option_index = 0
    for bbox in boxes:
        wide = (bbox[2] - bbox[0]) > (bbox[3] - bbox[1]) * 1.45
        if wide:
            dest = folder / f"q{question_number:03d}-stimulus-{len(stimulus) + 1}.png"
            kind = "stimulus"
        else:
            option_index += 1
            dest = folder / f"q{question_number:03d}-{option_index}.png"
            kind = "option"
        if not dest.exists():
            pix = page.get_pixmap(dpi=140, clip=pymupdf.Rect(*bbox))
            pix.save(dest)
        rel = dest.relative_to(ROOT).as_posix()
        if kind == "stimulus":
            stimulus.append(rel)
        else:
            options.append(rel)
    return stimulus, options


def parse_abstract() -> list[dict]:
    records = []
    doc = pymupdf.open(abstract_pdf())
    for group in group_pages("abstract", tolerate_forward_jump=True):
        joined = "\n".join(group["texts"])
        record = shell("abstract", "abstract", group["number"], abstract_subtype(joined), "single")
        record["prompt"] = abstract_prompt(joined)
        record["explanation"] = clean_explanation(joined.split("Пояснення", 1)[-1] if "Пояснення" in joined else joined)
        record["source_pages"] = [page["page"] for page in group["pages"]]
        record["page_images"] = [page["page_image"] for page in group["pages"]]
        figure_page = first_figure_page(group["pages"])
        if figure_page:
            stimulus, options = crop_abstract_figures(doc, figure_page["page"], group["number"])
            record["stimulus_images"] = stimulus
            record["options"] = [
                {"id": str(index), "text": None, "image": path}
                for index, path in enumerate(options, start=1)
            ]
        answers = re.findall(
            r"(?:фігур\w*|об['’]єкт)\s*№\s*(\d+)",
            joined,
            flags=re.IGNORECASE,
        )
        if answers:
            record["correct"] = [answers[-1]]
        if not record["prompt"]:
            record["issues"].append("missing-prompt")
        if not record["options"]:
            record["issues"].append("missing-figures")
        if not record["correct"]:
            record["issues"].append("missing-answer")
        elif record["options"] and record["correct"][0] not in {option["id"] for option in record["options"]}:
            record["issues"].append("answer-out-of-range")
        if record["issues"]:
            record["confidence"] = "low"
        records.append(record)
    doc.close()
    return records


def math_subtype(text: str) -> str:
    flat = collapse(text.split("Пояснення", 1)[0]).casefold()
    if "арифметич" in flat or "числовий вираз" in flat:
        return "operators"
    if "рівнян" in flat:
        return "equation"
    if "сектор" in flat or "клітин" in flat:
        return "number-grid"
    return "number-sequence"


def math_answer(text: str) -> str:
    found = re.findall(
        r"(?:Правильна відповідь|Відповідь)\s*:\s*([^\n.]+)",
        text,
        flags=re.IGNORECASE,
    )
    if not found:
        return ""
    return collapse(found[-1]).rstrip(".")


def math_prompt(text: str, subtype: str) -> str:
    main = text.split("Пояснення", 1)[0]
    flat = collapse(main)
    match = re.search(r"(?:рівняння\.|послідовність\.|послідовність:)\s*(.*)$", flat, flags=re.IGNORECASE)
    body = match.group(1).strip() if match else flat
    body = re.sub(
        r"^(?:Доповніть числову послідовність:|Підставте потрібне число у порожній сектор:)\s*",
        "",
        body,
        flags=re.IGNORECASE,
    ).strip()
    shown = re.search(r"(?:^|\s)(-?\d+(?:[.,]\d+)?)\s*$", body)
    if shown:
        body = body[: shown.start()].strip()
    if subtype == "operators":
        return operator_prompt(text)
    if subtype == "number-sequence":
        return "Доповніть числову послідовність: " + body
    if subtype == "number-grid":
        asked = re.search(r"Підставте потрібне число у [^:]+:", flat, flags=re.IGNORECASE)
        return asked.group(0) if asked else "Підставте потрібне число."
    return body


def operator_prompt(text: str) -> str:
    main = text.split("Пояснення", 1)[0]
    capture = False
    tokens = []
    for line in lines_of(main):
        folded = line.casefold()
        if "арифметичн" in folded and line.endswith(":"):
            capture = True
            continue
        if not capture:
            continue
        if re.fullmatch(r"-?\d+(?:[.,]\d+)?", line) or line == "=":
            tokens.append(line)
    if "=" in tokens:
        split_at = tokens.index("=")
        left = " □ ".join(tokens[:split_at])
        right = " ".join(tokens[split_at + 1 :])
        skeleton = f"{left} = {right}".strip()
    else:
        skeleton = " □ ".join(tokens)
    return "Підставте у числовий вираз потрібні арифметичні операції: " + skeleton


def parse_math() -> list[dict]:
    records = []
    for group in group_pages("math"):
        joined = "\n".join(group["texts"])
        subtype = math_subtype(joined)
        interaction = "expression" if subtype == "operators" else "numeric"
        record = shell("math", "math", group["number"], subtype, interaction)
        record["prompt"] = math_prompt(joined, subtype)
        record["correct"] = [math_answer(joined)] if math_answer(joined) else []
        record["explanation"] = clean_explanation(joined.split("Пояснення", 1)[-1] if "Пояснення" in joined else "")
        record["source_pages"] = [page["page"] for page in group["pages"]]
        record["page_images"] = [page["page_image"] for page in group["pages"]]
        record["stimulus_images"] = [
            image["file"] for page in group["pages"] for image in page["images"]
        ]
        if not record["prompt"]:
            record["issues"].append("missing-prompt")
        if not record["correct"]:
            record["issues"].append("missing-answer")
        if subtype == "number-grid" and not record["stimulus_images"]:
            record["issues"].append("missing-diagram")
        if subtype == "operators" and "□" not in record["prompt"]:
            record["issues"].append("missing-expression")
        if record["issues"]:
            record["confidence"] = "low"
        records.append(record)
    return records


def gold_number(text: str, page_number: int) -> int:
    match = re.search(r"арк\.?\s*№\s*(\d+)", text)
    return int(match.group(1)) if match else page_number


def gold_kind(text: str) -> tuple[str, str]:
    if "одного порядку" in text.casefold():
        return "pair", "pair"
    stem = ""
    for line in lines_of(text):
        if line.startswith("Визначте слово"):
            stem = line
            break
    upper = stem.upper()
    if "ПРОТИЛЕЖ" in upper:
        return "antonym", "single"
    if "БЛИЗЬ" in upper:
        return "synonym", "single"
    return "analogy", "single"


def gold_stem_and_options(text: str) -> tuple[str, list[str]]:
    pre = text.split("Пояснення", 1)[0]
    raw = [line.strip() for line in pre.splitlines() if line.strip() and not is_chrome_line(line)]
    stem_at = None
    for index, line in enumerate(raw):
        if line.startswith("Визначте") or line.startswith("Серед"):
            stem_at = index
            break
        if ":" in line and ("?" in line or "=" in line):
            stem_at = index
            break
    if stem_at is None:
        return "", []
    stem_lines = [raw[stem_at]]
    cursor = stem_at + 1
    while cursor < len(raw) and not looks_like_option(raw[cursor]) and len(stem_lines) < 3:
        if raw[cursor].startswith("Приклад") or raw[cursor].startswith("В завданнях"):
            break
        stem_lines.append(raw[cursor])
        cursor += 1
    options = []
    for line in raw[cursor:]:
        if is_chrome_line(line) or line.startswith("Приклад") or line.startswith("В завданнях"):
            continue
        if looks_like_option(line):
            options.append(line)
    return collapse(" ".join(stem_lines)), options


def looks_like_option(line: str) -> bool:
    if len(line) > 40:
        return False
    if line.endswith("?"):
        return False
    if line.startswith("Визначте") or line.startswith("Серед") or line.startswith("В завданнях"):
        return False
    return True


def words_in(text: str) -> list[str]:
    return re.findall(r"[А-ЯІЇЄҐа-яіїєґ'’A-Za-z-]{3,}", text)


_ENDINGS = (
    "ість", "ості", "ення", "ання", "ями", "ами", "ого", "ому",
    "ів", "ей", "ом", "ем", "ою", "ею", "ій", "ий", "ах", "ях", "ам", "ям",
    "а", "я", "у", "ю", "і", "и", "о", "е", "ї",
)


def stem_key(word: str) -> str:
    folded = word.casefold().replace("’", "'")
    for ending in _ENDINGS:
        if folded.endswith(ending) and len(folded) - len(ending) >= 4:
            return folded[: -len(ending)]
    return folded


def keys_match(left: str, right: str) -> bool:
    a, b = stem_key(left), stem_key(right)
    if a == b:
        return True
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= 5 and long.startswith(short)


def match_option(token: str, options: list[str]) -> str | None:
    folded = token.casefold().replace("’", "'")
    for option in options:
        if option.casefold().replace("’", "'") == folded:
            return option
    token_words = words_in(token)
    for option in options:
        if keys_match(token, option):
            return option
        option_words = words_in(option)
        if (
            token_words
            and len(token_words) == len(option_words)
            and all(keys_match(left, right) for left, right in zip(token_words, option_words))
        ):
            return option
    return None


def option_in_text(option: str, text: str, banned: list[str]) -> bool:
    if any(keys_match(option, word) for word in banned):
        return False
    return any(keys_match(option, word) for word in words_in(text))


def gold_correct(kind: str, explanation: str, options: list[str], stem: str) -> list[str]:
    stem_words = words_in(stem)
    if kind == "pair":
        match = re.search(
            r"є\s+([А-ЯІЇЄҐ'’A-Z][А-ЯІЇЄҐ'’A-Z \-]{2,}?)\s+та\s+([А-ЯІЇЄҐ'’A-Z][А-ЯІЇЄҐ'’A-Z \-]{2,}?)(?:\.|,|\s)",
            explanation,
        )
        if not match:
            return []
        found = []
        for token in match.groups():
            found.append(match_option(token.strip(), options) or token.strip().capitalize())
        return found
    quotes = re.findall(r"«([^»]+)»", explanation)
    answer_quotes = [quote for quote in quotes if quote.upper() == quote and len(quote) >= 3]
    if answer_quotes:
        token = answer_quotes[0]
        return [match_option(token, options) or token.capitalize()]
    mentioned = [option for option in options if option_in_text(option, explanation, stem_words)]
    if len(mentioned) == 1:
        return mentioned
    match = re.search(r"аналогі\w*,\s*([А-ЯІЇЄҐ][а-яіїєґ'’]+)", explanation)
    if match and not any(keys_match(match.group(1), word) for word in stem_words):
        return [match_option(match.group(1), options) or match.group(1)]
    return []


def parse_gold() -> list[dict]:
    manifest = load_manifest("verbal-gold")
    records = []
    for page in manifest["pages"]:
        text = page_text("verbal-gold", page)
        number = gold_number(text, page["page"])
        kind, interaction = gold_kind(text)
        stem, options = gold_stem_and_options(text)
        explanation = clean_explanation(text.split("Пояснення", 1)[-1] if "Пояснення" in text else "")
        record = shell("verbal", "verbal-gold", number, kind, interaction)
        record["prompt"] = stem
        record["explanation"] = explanation
        record["options"] = [{"id": option, "text": option, "image": None} for option in options]
        record["correct"] = gold_correct(kind, explanation, options, stem)
        record["page_images"] = [page["page_image"]]
        record["source_pages"] = [page["page"]]
        expected = 6 if kind == "pair" else 5
        option_ids = {option["id"] for option in record["options"]}
        if not record["prompt"]:
            record["issues"].append("missing-prompt")
        if len(options) != expected:
            record["issues"].append("options-incomplete")
        if kind == "pair" and len(record["correct"]) != 2:
            record["issues"].append("pair-answer-incomplete")
        if kind != "pair" and len(record["correct"]) != 1:
            record["issues"].append("missing-answer")
        if record["correct"] and not all(answer in option_ids or match_option(answer, options) for answer in record["correct"]):
            # correct may be the capitalized form of a missing option
            if not all(match_option(answer, options) for answer in record["correct"]):
                record["issues"].append("answer-not-in-options")
        if record["issues"]:
            record["confidence"] = "low"
        records.append(record)
    return records


def summarize(records: list[dict], label: str) -> None:
    issues: dict[str, int] = {}
    for record in records:
        for issue in record["issues"]:
            issues[issue] = issues.get(issue, 0) + 1
    numbers = [record["number"] for record in records]
    print(
        f"{label}: {len(records)} numbers {min(numbers) if numbers else '-'}..{max(numbers) if numbers else '-'} "
        f"unique {len(set(numbers))} low {sum(1 for record in records if record['confidence'] != 'high')} issues {issues}"
    )


def main() -> None:
    records = parse_abstract() + parse_math() + parse_gold()
    records.sort(key=lambda record: (record["block"], record["source"], record["number"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    summarize([r for r in records if r["source"] == "abstract"], "abstract")
    summarize([r for r in records if r["source"] == "math"], "math")
    summarize([r for r in records if r["source"] == "verbal-gold"], "verbal-gold")
    print(f"wrote {OUT} ({len(records)} records)")


if __name__ == "__main__":
    main()
