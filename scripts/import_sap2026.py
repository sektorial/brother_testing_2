"""Import the SAP 2026 screenshot PDFs into the question bank.

The PDFs have no text layer. Orange outlines are the official key.
Figure crops go to data/raw/sap2026/. Review renders and the text
overrides live under data/_sap2026/, which git ignores.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

import cv2
import numpy as np
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
MATERIALS = ROOT / "materials" / "new"
QUESTIONS = ROOT / "data" / "questions.json"
REPORT = ROOT / "data" / "sap2026_report.json"
RAW = ROOT / "data" / "raw" / "sap2026"
SCRATCH = ROOT / "data" / "_sap2026"
DPI = 150

LIBRARY = "2026"
SOURCES = {
    "verbal": {"title": "Вербальний", "block": "verbal", "order": 1},
    "abstract": {"title": "Абстрактно-логічний", "block": "abstract", "order": 2},
    "math": {"title": "Математичний", "block": "math", "order": 3},
}


def pdf_path(prefix: str) -> Path:
    matches = [path for path in MATERIALS.glob("*.pdf") if path.name.startswith(prefix)]
    if len(matches) != 1:
        raise SystemExit(f"expected one PDF starting with {prefix!r}, got {matches}")
    return matches[0]


def render(page: pymupdf.Page) -> np.ndarray:
    pix = page.get_pixmap(dpi=DPI)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        return cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


def card_spans(img: np.ndarray) -> list[tuple[int, int]]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    row = (gray < 253).sum(axis=1) > img.shape[1] * 0.25
    runs: list[tuple[int, int]] = []
    start = None
    for y, on in enumerate(row):
        if on and start is None:
            start = y
        elif not on and start is not None:
            runs.append((start, y - 1))
            start = None
    if start is not None:
        runs.append((start, len(row) - 1))
    merged: list[tuple[int, int]] = []
    for top, bottom in runs:
        if merged and top - merged[-1][1] < 14:
            merged[-1] = (merged[-1][0], bottom)
        else:
            merged.append((top, bottom))
    return [(top, bottom) for top, bottom in merged if bottom - top > 40]


def orange_mask(img: np.ndarray) -> np.ndarray:
    blue, green, red = cv2.split(img)
    return (
        (red > 175)
        & (green > 40)
        & (green < 190)
        & (blue < 120)
        & (red.astype(np.int16) > green.astype(np.int16) + 28)
        & (red.astype(np.int16) > blue.astype(np.int16) + 28)
    )


def orange_boxes(img: np.ndarray) -> list[tuple[int, int, int, int]]:
    mask = orange_mask(img).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w > 16 and h > 12 and h < 180 and w < img.shape[1] * 0.8:
            boxes.append((x, y, w, h))
    boxes.sort(key=lambda box: (box[1], box[0]))
    return boxes


def deorange(img: np.ndarray) -> np.ndarray:
    out = img.copy()
    out[orange_mask(img)] = (250, 250, 250)
    return out


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def save_png(img: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img)


def content_rows(gray: np.ndarray, ink_below: int = 180) -> list[tuple[int, int]]:
    ink = (gray < ink_below).sum(axis=1) > 8
    runs: list[tuple[int, int]] = []
    start = None
    for y, on in enumerate(ink):
        if on and start is None:
            start = y
        elif not on and start is not None:
            if y - start > 6:
                runs.append((start, y - 1))
            start = None
    if start is not None and len(gray) - start > 6:
        runs.append((start, len(gray) - 1))
    return runs


def split_button(card: np.ndarray, box: tuple[int, int, int, int]) -> list[tuple[int, int, int, int]]:
    x, y, w, h = box
    gray = cv2.cvtColor(card, cv2.COLOR_BGR2GRAY)
    band = gray[y + 3 : y + h - 3, x : x + w]
    if band.size == 0 or h < 10:
        return [box]
    ink = (band < 150).sum(axis=0)
    gaps: list[tuple[int, int]] = []
    start = None
    for index, value in enumerate(ink):
        if value == 0 and start is None:
            start = index
        elif value > 0 and start is not None:
            if index - start >= 16 and start > 6 and index < w - 6:
                gaps.append((start, index - 1))
            start = None
    if not gaps:
        return [box]
    cuts = [0]
    for left, right in gaps:
        cuts.append((left + right) // 2)
    cuts.append(w)
    parts = []
    for left, right in zip(cuts, cuts[1:]):
        if right - left > 22:
            parts.append((x + left, y, right - left, h))
    return parts or [box]


def verbal_buttons(card: np.ndarray) -> list[tuple[int, int, int, int]]:
    gray = cv2.cvtColor(card, cv2.COLOR_BGR2GRAY)
    height = gray.shape[0]
    y0 = int(height * 0.40)
    zone = gray[y0:]
    edges = cv2.Canny(zone, 40, 120)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (16, 3))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if 34 < w < 460 and 16 < h < 90:
            boxes.append((x, y0 + y, w, h))
    boxes.sort()
    flat: list[tuple[int, int, int, int]] = []
    for box in boxes:
        flat.extend(split_button(card, box))
    flat.sort()
    return flat


def hits_for(oranges: list[tuple[int, int, int, int]], buttons: list[tuple[int, int, int, int]]) -> list[int]:
    found = []
    for ox, oy, ow, oh in oranges:
        cx, cy = ox + ow / 2, oy + oh / 2
        best = None
        best_d = 1e9
        for index, (x, y, w, h) in enumerate(buttons):
            if x - 10 <= cx <= x + w + 10 and y - 10 <= cy <= y + h + 10:
                distance = abs(cx - (x + w / 2)) + abs(cy - (y + h / 2))
                if distance < best_d:
                    best, best_d = index, distance
        if best is not None and best not in found:
            found.append(best)
    return found


def abstract_options(card: np.ndarray, orange: tuple[int, int, int, int]) -> list[tuple[int, int, int, int]]:
    ox, oy, ow, oh = orange
    gray = cv2.cvtColor(card, cv2.COLOR_BGR2GRAY)
    y0 = max(0, oy - 12)
    y1 = min(gray.shape[0], oy + oh + 12)
    band = gray[y0:y1].copy()
    band[orange_mask(card)[y0:y1]] = 255
    ink = (band < 165).astype(np.uint8) * 255
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 23)))
    contours, _ = cv2.findContours(ink, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    blobs = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w * h < 80 or h < 10 or w < 8:
            continue
        blobs.append((x, y0 + y, w, h))
    blobs.sort()
    if not blobs:
        return []
    gap_limit = max(22, int(ow * 0.42))
    groups: list[list[tuple[int, int, int, int]]] = [[blobs[0]]]
    for blob in blobs[1:]:
        prev = groups[-1][-1]
        gap = blob[0] - (prev[0] + prev[2])
        if gap < gap_limit:
            groups[-1].append(blob)
        else:
            groups.append([blob])
    boxes = []
    for group in groups:
        x0 = min(item[0] for item in group)
        y0b = min(item[1] for item in group)
        x1 = max(item[0] + item[2] for item in group)
        y1b = max(item[1] + item[3] for item in group)
        boxes.append((x0, y0b, x1 - x0, y1b - y0b))
    return boxes


def option_hit(orange: tuple[int, int, int, int], boxes: list[tuple[int, int, int, int]]) -> int | None:
    cx, cy = orange[0] + orange[2] / 2, orange[1] + orange[3] / 2
    for index, (x, y, w, h) in enumerate(boxes):
        if x - 8 <= cx <= x + w + 8 and y - 8 <= cy <= y + h + 8:
            return index
    return None


def crop_box(img: np.ndarray, box: tuple[int, int, int, int], pad: int = 6) -> np.ndarray:
    x, y, w, h = box
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(img.shape[1], x + w + pad)
    y1 = min(img.shape[0], y + h + pad)
    return img[y0:y1, x0:x1]


def mostly_black(card: np.ndarray) -> bool:
    gray = cv2.cvtColor(card, cv2.COLOR_BGR2GRAY)
    return float(gray.mean()) < 80


class Reader:
    def __init__(self) -> None:
        from winrt.windows.globalization import Language
        from winrt.windows.media.ocr import OcrEngine

        self.engine = OcrEngine.try_create_from_language(Language("ru"))
        if self.engine is None:
            raise SystemExit("Russian Windows OCR is not available")

    async def read(self, img: np.ndarray) -> str:
        from winrt.windows.graphics.imaging import BitmapDecoder
        from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

        if img.size == 0:
            return ""
        view = cv2.copyMakeBorder(img, 18, 18, 18, 18, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        scale = 2 if view.shape[1] < 700 else 1
        if scale != 1:
            view = cv2.resize(view, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        ok, encoded = cv2.imencode(".png", view)
        if not ok:
            return ""
        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream)
        writer.write_bytes(bytes(encoded))
        await writer.store_async()
        stream.seek(0)
        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        result = await self.engine.recognize_async(bitmap)
        return " ".join(word.text for line in result.lines for word in line.words).strip()


def prompt_and_stimulus(card: np.ndarray, option_top: int) -> tuple[np.ndarray | None, np.ndarray | None]:
    above = card[: max(0, option_top - 8)]
    if above.size == 0:
        return None, None
    gray = cv2.cvtColor(above, cv2.COLOR_BGR2GRAY)
    rows = content_rows(gray)
    if not rows:
        return None, None
    prompt = None
    body_rows = rows
    if rows[0][1] - rows[0][0] < 48:
        prompt = above[max(0, rows[0][0] - 4) : rows[0][1] + 6]
        body_rows = rows[1:]
    if not body_rows:
        return prompt, None
    top = max(0, body_rows[0][0] - 6)
    bottom = min(above.shape[0], body_rows[-1][1] + 8)
    stimulus = above[top:bottom]
    if stimulus.shape[0] < 36:
        return prompt, None
    return prompt, stimulus


def tight(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ink = np.where(gray < 210)
    if ink[0].size == 0:
        return img
    y0, y1 = int(ink[0].min()), int(ink[0].max())
    x0, x1 = int(ink[1].min()), int(ink[1].max())
    pad = 8
    y0 = max(0, y0 - pad)
    x0 = max(0, x0 - pad)
    y1 = min(img.shape[0], y1 + pad + 1)
    x1 = min(img.shape[1], x1 + pad + 1)
    return img[y0:y1, x0:x1]


async def extract() -> None:
    reader = Reader()
    SCRATCH.mkdir(parents=True, exist_ok=True)
    (SCRATCH / "pages").mkdir(exist_ok=True)
    draft: dict[str, list] = {"verbal": [], "abstract": [], "math": []}
    warnings: list[str] = []

    verbal_doc = pymupdf.open(pdf_path("Вер"))
    number = 0
    for page_index in range(verbal_doc.page_count):
        img = render(verbal_doc[page_index])
        cv2.imwrite(str(SCRATCH / "pages" / f"verbal-{page_index + 1:02d}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 82])
        for card_index, (top, bottom) in enumerate(card_spans(img)):
            card = img[top : bottom + 1]
            if mostly_black(card):
                warnings.append(f"verbal p{page_index + 1} card {card_index} skipped (black)")
                continue
            oranges = orange_boxes(card)
            buttons = verbal_buttons(card)
            picked = hits_for(oranges, buttons)
            if not oranges or not buttons or len(picked) != len(oranges):
                warnings.append(
                    f"verbal p{page_index + 1} c{card_index} buttons={len(buttons)} orange={len(oranges)} hits={picked}"
                )
                continue
            number += 1
            ocr_options = []
            for box in buttons:
                ocr_options.append(await reader.read(crop_box(card, box, pad=2)))
            upper = card[: int(card.shape[0] * 0.62)]
            ocr_prompt = await reader.read(upper)
            draft["verbal"].append(
                {
                    "number": number,
                    "page": page_index + 1,
                    "buttons": len(buttons),
                    "correct_indexes": picked,
                    "ocr_options": ocr_options,
                    "ocr_prompt": ocr_prompt,
                }
            )
    verbal_doc.close()

    abstract_doc = pymupdf.open(pdf_path("Аб"))
    number = 0
    for page_index in range(abstract_doc.page_count):
        img = render(abstract_doc[page_index])
        cv2.imwrite(str(SCRATCH / "pages" / f"abstract-{page_index + 1:02d}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 82])
        for card_index, (top, bottom) in enumerate(card_spans(img)):
            card = img[top : bottom + 1]
            if mostly_black(card):
                continue
            oranges = orange_boxes(card)
            if len(oranges) != 1:
                warnings.append(f"abstract p{page_index + 1} c{card_index} orange={len(oranges)}")
                continue
            options = abstract_options(card, oranges[0])
            hit = option_hit(oranges[0], options)
            if hit is None or not 4 <= len(options) <= 6:
                warnings.append(
                    f"abstract p{page_index + 1} c{card_index} options={len(options)} hit={hit}"
                )
                continue
            number += 1
            option_top = min(box[1] for box in options)
            prompt_img, stimulus_img = prompt_and_stimulus(card, option_top)
            folder = RAW / "abstract"
            option_files = []
            for index, box in enumerate(options, start=1):
                crop = deorange(crop_box(card, box, pad=4))
                path = folder / f"q{number:04d}-{index}.png"
                save_png(crop, path)
                option_files.append(rel(path))
            stimulus_file = None
            if stimulus_img is not None:
                path = folder / f"q{number:04d}-stimulus.png"
                save_png(deorange(tight(stimulus_img)), path)
                stimulus_file = rel(path)
            ocr_prompt = await reader.read(prompt_img) if prompt_img is not None else ""
            draft["abstract"].append(
                {
                    "number": number,
                    "page": page_index + 1,
                    "correct_index": hit,
                    "options": option_files,
                    "stimulus": stimulus_file,
                    "ocr_prompt": ocr_prompt,
                }
            )
    abstract_doc.close()

    math_doc = pymupdf.open(pdf_path("Мат"))
    number = 0
    for page_index in range(math_doc.page_count):
        img = render(math_doc[page_index])
        cv2.imwrite(str(SCRATCH / "pages" / f"math-{page_index + 1:02d}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 82])
        for card_index, (top, bottom) in enumerate(card_spans(img)):
            card = img[top : bottom + 1]
            if mostly_black(card):
                continue
            oranges = orange_boxes(card)
            if len(oranges) != 1:
                warnings.append(f"math p{page_index + 1} c{card_index} orange={len(oranges)}")
                continue
            number += 1
            answer_img = crop_box(card, oranges[0], pad=2)
            answer_text = await reader.read(deorange(answer_img))
            above = card[: max(0, oranges[0][1] - 8)]
            prompt_img, stimulus_img = prompt_and_stimulus(card, oranges[0][1])
            ocr_above = await reader.read(above)
            stimulus_file = None
            if stimulus_img is not None and stimulus_img.shape[0] > 70:
                path = RAW / "math" / f"q{number:04d}-stimulus.png"
                save_png(deorange(tight(stimulus_img)), path)
                stimulus_file = rel(path)
            draft["math"].append(
                {
                    "number": number,
                    "page": page_index + 1,
                    "answer": answer_text,
                    "ocr_above": ocr_above,
                    "stimulus": stimulus_file,
                    "answer_wide": oranges[0][2] > oranges[0][3] * 2.4,
                }
            )
    math_doc.close()

    (SCRATCH / "draft.json").write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    (SCRATCH / "warnings.txt").write_text("\n".join(warnings), encoding="utf-8")
    print(f"verbal {len(draft['verbal'])} abstract {len(draft['abstract'])} math {len(draft['math'])}")
    print(f"warnings {len(warnings)}")
    for line in warnings:
        print(" ", line)


TEXT = ROOT / "scripts" / "sap2026_text.json"
PAIR_PROMPT = "Серед представлених слів оберіть два поняття одного порядку:"
ANALOGY_PROMPT = "Серед представлених слів оберіть те, що доповнює смислове відношення:"
OPERATOR_PROMPT = "Підставте у числовий вираз потрібні арифметичні операції:"


def verbal_prompt(item: dict) -> str:
    kind = item["kind"]
    if kind == "pair":
        return PAIR_PROMPT
    if kind == "analogy":
        return f"{ANALOGY_PROMPT} {item['stem']}"
    if kind == "synonym":
        return f"Визначте слово, найбільш близьке за значенням до слова {item['word']}"
    if kind == "antonym-most":
        return f"Визначте слово, найбільш протилежне за значенням до слова {item['word']}"
    return f"Визначте слово, протилежне за значенням до слова {item['word']}"


def fold(text: str) -> str:
    text = (text or "").casefold()
    text = text.replace("’", "'").replace("ʼ", "'").replace("`", "'")
    text = text.replace("−", "-").replace("–", "-").replace("—", "-")
    text = text.replace("×", "*").replace("÷", "/")
    text = text.replace("²", "2").replace("³", "3")
    text = re.sub(r"[^0-9a-zа-яіїєґ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def norm_answer(value: str) -> str:
    text = str(value).strip().casefold()
    text = text.replace(" ", "")
    text = text.replace("×", "*").replace("÷", "/").replace(":", "/")
    text = text.replace("−", "-").replace("–", "-").replace("—", "-")
    text = text.replace(",", ".")
    text = text.replace("²", "^2").replace("³", "^3")
    return text


def shown_answers(record: dict) -> list[str]:
    options = {str(option.get("id")): option.get("text") or str(option.get("id")) for option in record.get("options") or []}
    shown = []
    for item in record.get("correct") or []:
        shown.append(str(options.get(str(item), item)))
    return shown


def same_key(left: list[str], right: list[str]) -> bool:
    if len(left) != len(right):
        return False
    return {norm_answer(item) for item in left} == {norm_answer(item) for item in right}


def operator_prompt(expression: str) -> str:
    left, right = expression.split("=", 1)
    numbers = re.findall(r"\d+(?:[.,]\d+)?", left)
    return f"{OPERATOR_PROMPT} {' □ '.join(numbers)} = {right.strip()}"


def abstract_wording(item: dict) -> tuple[str, str]:
    ocr = (item.get("ocr_prompt") or "").casefold()
    if "зайв" in ocr or not item.get("stimulus"):
        return "odd-one-out", "Визначте, яка з фігур є зайвою:"
    if "нижн" in ocr or item.get("page", 0) >= 7:
        return "transformation", "Як повинна змінитися нижня фігура?"
    return "sequence", "Яка з представлених нижче фігур доповнює послідовність?"


def index_bank(records: list[dict]) -> list[dict]:
    indexed = []
    for record in records:
        if record.get("library") == LIBRARY:
            continue
        options = [fold(option.get("text") or "") for option in record.get("options") or []]
        indexed.append(
            {
                "record": record,
                "options": frozenset(part for part in options if part),
                "prompt": fold(record.get("prompt") or ""),
                "numbers": tuple(re.findall(r"\d+(?:[.,]\d+)?", record.get("prompt") or "")),
            }
        )
    return indexed


def match_verbal(item: dict, bank: list[dict]) -> dict | None:
    wanted = frozenset(fold(option) for option in item["options"])
    hits = [entry for entry in bank if entry["options"] and entry["options"] == wanted]
    if not hits:
        return None
    prompt = fold(verbal_prompt(item))
    hits.sort(key=lambda entry: (entry["prompt"] != prompt, entry["record"]["library"] != "2025"))
    return hits[0]["record"]


def match_math(item: dict, bank: list[dict]) -> dict | None:
    if item["subtype"] == "grid":
        return None
    if item["subtype"] == "operators":
        prompt = operator_prompt(item["answer"])
    else:
        prompt = item["prompt"]
    folded = fold(prompt)
    numbers = tuple(re.findall(r"\d+(?:[.,]\d+)?", prompt))
    if item["subtype"] == "grid" or len(numbers) < 3:
        hits = [entry for entry in bank if entry["prompt"] and entry["prompt"] == folded]
    else:
        hits = [
            entry
            for entry in bank
            if entry["numbers"] == numbers
            and entry["record"].get("block") == "math"
            and SequenceMatcher(None, folded, entry["prompt"]).ratio() >= 0.45
        ]
    if not hits:
        return None
    hits.sort(key=lambda entry: (-SequenceMatcher(None, folded, entry["prompt"]).ratio(), entry["record"]["library"] != "2025"))
    best = hits[0]
    if SequenceMatcher(None, folded, best["prompt"]).ratio() < 0.45:
        return None
    return best["record"]


def link(record: dict, previous: dict | None, correct: list[str], differs: list[dict]) -> None:
    if previous is None:
        return
    record["duplicate_of"] = previous["id"]
    old = shown_answers(previous)
    if same_key(old, correct):
        record["explanation"] = (previous.get("explanation") or "").strip()
        return
    record["issues"].append("key-differs")
    shown = ", ".join(old)
    record["explanation"] = f"У попередній бібліотеці ключ інший: {shown}."
    differs.append(
        {
            "id": record["id"],
            "duplicate_of": previous["id"],
            "old": old,
            "new": correct,
        }
    )


def shell(block: str, source: str, number: int, subtype: str, interaction: str) -> dict:
    meta = SOURCES[source]
    return {
        "id": f"{LIBRARY}-{source}-{number:04d}",
        "library": LIBRARY,
        "block": block,
        "source": source,
        "source_title": meta["title"],
        "source_order": meta["order"],
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


def build() -> None:
    draft = json.loads((SCRATCH / "draft.json").read_text(encoding="utf-8"))
    text = json.loads(TEXT.read_text(encoding="utf-8"))
    if len(text["verbal"]) != len(draft["verbal"]) or len(text["math"]) != len(draft["math"]):
        raise SystemExit(
            f"text/draft mismatch verbal {len(text['verbal'])}/{len(draft['verbal'])} "
            f"math {len(text['math'])}/{len(draft['math'])}"
        )
    bank_records = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    bank = index_bank(bank_records)
    made: list[dict] = []
    differs: list[dict] = []
    matched = 0

    for geometry, item in zip(draft["verbal"], text["verbal"]):
        if len(item["options"]) != geometry["buttons"]:
            raise SystemExit(f"verbal {geometry['number']} options {len(item['options'])} != buttons {geometry['buttons']}")
        kind = item["kind"]
        subtype = {"pair": "pair", "analogy": "analogy", "synonym": "synonym", "antonym": "antonym", "antonym-most": "antonym"}[kind]
        interaction = "pair" if kind == "pair" else "single"
        record = shell("verbal", "verbal", geometry["number"], subtype, interaction)
        record["prompt"] = verbal_prompt(item)
        record["options"] = [{"id": option, "text": option, "image": None} for option in item["options"]]
        record["correct"] = [item["options"][index] for index in geometry["correct_indexes"]]
        record["source_pages"] = [geometry["page"]]
        if kind == "pair" and len(record["correct"]) != 2:
            record["issues"].append("key-missing")
            record["confidence"] = "low"
        if interaction == "single" and not record["correct"]:
            record["issues"].append("key-missing")
            record["confidence"] = "low"
        previous = match_verbal(item, bank)
        if previous:
            matched += 1
        link(record, previous, record["correct"], differs)
        made.append(record)

    for geometry in draft["abstract"]:
        subtype, prompt = abstract_wording(geometry)
        record = shell("abstract", "abstract", geometry["number"], subtype, "single")
        record["prompt"] = prompt
        record["options"] = [
            {"id": str(index), "text": None, "image": path}
            for index, path in enumerate(geometry["options"], start=1)
        ]
        record["correct"] = [str(geometry["correct_index"] + 1)]
        record["stimulus_images"] = [geometry["stimulus"]] if geometry.get("stimulus") else []
        record["source_pages"] = [geometry["page"]]
        made.append(record)

    for geometry, item in zip(draft["math"], text["math"]):
        subtype = {"sequence": "number-sequence", "grid": "number-grid", "equation": "equation", "operators": "operators"}[item["subtype"]]
        interaction = "expression" if item["subtype"] == "operators" else "numeric"
        record = shell("math", "math", geometry["number"], subtype, interaction)
        if item["subtype"] == "operators":
            record["prompt"] = operator_prompt(item["answer"])
            record["correct"] = [item["answer"]]
        else:
            record["prompt"] = item["prompt"]
            record["correct"] = [item["answer"]]
        record["stimulus_images"] = [geometry["stimulus"]] if geometry.get("stimulus") else []
        record["source_pages"] = [geometry["page"]]
        if subtype == "number-grid" and not record["stimulus_images"]:
            record["issues"].append("missing-diagram")
            record["confidence"] = "low"
        previous = match_math(item, bank)
        if previous:
            matched += 1
        link(record, previous, record["correct"], differs)
        made.append(record)

    problems = [record["id"] for record in made if not record["correct"] or "key-missing" in record["issues"]]
    if problems:
        raise SystemExit(f"questions without a key: {problems}")
    for record in made:
        if record["interaction"] == "pair" and len(record["correct"]) != 2:
            raise SystemExit(f"pair without two keys: {record['id']}")
        if record["interaction"] == "expression" and "=" not in record["correct"][0]:
            raise SystemExit(f"expression without equals: {record['id']}")

    raw = QUESTIONS.read_text(encoding="utf-8")
    marker = raw.find('"id": "2026-')
    if marker != -1:
        brace = raw.rfind("\n  {", 0, marker)
        raw = raw[:brace].rstrip()
        if not raw.endswith(","):
            raw += ","
    else:
        raw = raw.rstrip()
        if not raw.endswith("]"):
            raise SystemExit("questions.json does not end with ]")
        raw = raw[:-1].rstrip()
        if not raw.endswith(","):
            raw += ","
    chunks = []
    for record in made:
        body = json.dumps(record, ensure_ascii=False, indent=2)
        chunks.append("\n".join("  " + line for line in body.splitlines()))
    QUESTIONS.write_text(raw + "\n" + ",\n".join(chunks) + "\n]\n", encoding="utf-8")

    counts = {
        "verbal": sum(1 for record in made if record["block"] == "verbal"),
        "abstract": sum(1 for record in made if record["block"] == "abstract"),
        "math": sum(1 for record in made if record["block"] == "math"),
    }
    report = {
        "counts": counts,
        "matched": matched,
        "key_same": matched - len(differs),
        "key_differs": differs,
        "unmatched": counts["verbal"] + counts["math"] - matched,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("counts", "matched", "key_same", "unmatched")}, ensure_ascii=False))
    print(f"key differs {len(differs)}")
    for item in differs:
        print(f"  {item['id']} vs {item['duplicate_of']}: {item['old']} -> {item['new']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=("extract", "build"))
    args = parser.parse_args()
    if args.step == "extract":
        asyncio.run(extract())
    else:
        build()


if __name__ == "__main__":
    main()
