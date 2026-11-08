"""Import FEMIDA, Psymetrics, and StartExam printouts into the question bank.

Google Forms exports keep the official key on a wrong answer, and the chosen
option's color when the answer was right. StartExam keeps the key only when
the sitting was marked correct. Questions without a key are imported and
flagged so the trainer can leave them out of the score.
"""

from __future__ import annotations

import argparse
import json
import quopri
import re
import shutil
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
MATERIALS = ROOT / "materials" / "Бібліотеки (Загальні здібності)"
QUESTIONS = ROOT / "data" / "questions.json"
REPORT = ROOT / "data" / "import_report.json"
RAW = ROOT / "data" / "raw" / "libraries"

NEW_LIBRARIES = ("femida-2022", "psymetrics-2021", "psymetrics-2022", "startexam-2022")
SCORE_RE = re.compile(r"^(\d+)\s*/\s*1$")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
URL_RE = re.compile(r"https?://\S+")
STARTEXAM_Q_RE = re.compile(r"^(\d+)\.\s*(.*)$")
OPTION_PREFIX_RE = re.compile(r"^[vV✓✔]\s+")
PUA_RE = re.compile(r"[\uE000-\uF8FF]")
EXPECTED_SLASH_RE = re.compile(r"Усього балів\s*(\d+)\s*/\s*(\d+)", re.I)
EXPECTED_IZ_RE = re.compile(r"(\d+)\s+из\s+(\d+)", re.I)

SOURCES = [
    {
        "library": "femida-2022",
        "block": "verbal",
        "source": "analogies",
        "title": "Аналогії",
        "order": 1,
        "path": MATERIALS / "1" / "FEMIDA 2022  Вербальний блок  Аналогії_.pdf",
        "kind": "forms",
    },
    {
        "library": "femida-2022",
        "block": "verbal",
        "source": "synonym-analogies",
        "title": "Аналогії синонімічних слів",
        "order": 2,
        "path": MATERIALS / "1" / "FEMIDA 2022  Вербальний блок Аналогії синонімічних слів_.pdf",
        "kind": "forms",
    },
    {
        "library": "femida-2022",
        "block": "verbal",
        "source": "same-order",
        "title": "Розуміння одного порядку",
        "order": 3,
        "path": MATERIALS / "1" / "FEMIDA 2022  Вербальний блок Розуміння одного порядку_.pdf",
        "kind": "forms",
    },
    {
        "library": "femida-2022",
        "block": "verbal",
        "source": "synonyms",
        "title": "Синоніми слів",
        "order": 4,
        "path": MATERIALS / "1" / "FEMIDA 2022  Вербальний блок Синоніми слів_.pdf",
        "kind": "forms",
    },
    {
        "library": "femida-2022",
        "block": "verbal",
        "source": "complex-analogies",
        "title": "Складні аналогії",
        "order": 5,
        "path": MATERIALS / "1" / "FEMIDA 2022 Вербальний блок Складні аналогії.pdf",
        "kind": "forms",
    },
    {
        "library": "psymetrics-2021",
        "block": "verbal",
        "source": "part-1",
        "title": "Частина 1",
        "order": 1,
        "path": MATERIALS / "2" / "Psymetrics 2021  вербальний блок (частина 1).pdf",
        "kind": "forms",
    },
    {
        "library": "psymetrics-2021",
        "block": "verbal",
        "source": "part-2",
        "title": "Частина 2",
        "order": 2,
        "path": MATERIALS / "2" / "Psymetrics 2021 вербальний блок (частина 2).pdf",
        "kind": "forms",
    },
    {
        "library": "psymetrics-2021",
        "block": "verbal",
        "source": "part-3",
        "title": "Частина 3",
        "order": 3,
        "path": MATERIALS / "2" / "Psymetrics 2021 вербальний блок (частина 3).pdf",
        "kind": "forms",
    },
    {
        "library": "psymetrics-2021",
        "block": "verbal",
        "source": "part-4",
        "title": "Частина 4",
        "order": 4,
        "path": MATERIALS / "2" / "Psymetrics 2021  вербальний блок (частина 4).pdf",
        "kind": "forms",
    },
    {
        "library": "psymetrics-2021",
        "block": "verbal",
        "source": "part-5",
        "title": "Частина 5",
        "order": 5,
        "path": MATERIALS / "2" / "Psymetrics 2021 вербальний блок (частина 5).pdf",
        "kind": "forms",
    },
    {
        "library": "psymetrics-2022",
        "block": "verbal",
        "source": "compound-concepts",
        "title": "Складені поняття",
        "order": 1,
        "path": MATERIALS / "3" / "Psymetrics test 2022 Вербальний блок Складені поняття.pdf",
        "kind": "forms",
    },
    {
        "library": "psymetrics-2022",
        "block": "math",
        "source": "numeric-relations",
        "title": "Числові співвідношення",
        "order": 1,
        "path": MATERIALS / "3" / "Psymetrics test 2022  Математичний тест  Числові співвідношення.pdf",
        "kind": "forms",
    },
    {
        "library": "psymetrics-2022",
        "block": "math",
        "source": "equations",
        "title": "Рівняння",
        "order": 2,
        "path": MATERIALS / "3" / "Psymetrics test 2022  Математичний тест Рівняння.pdf",
        "kind": "forms",
    },
    {
        "library": "psymetrics-2022",
        "block": "math",
        "source": "numeric-patterns",
        "title": "Числові закономірності",
        "order": 3,
        "path": MATERIALS / "3" / "Psymetrics test 2022 Математичний тест  Числові закономірності.pdf",
        "kind": "forms",
    },
    {
        "library": "psymetrics-2022",
        "block": "math",
        "source": "equations-inequalities",
        "title": "Рівняння і нерівності",
        "order": 4,
        "path": MATERIALS / "3" / "Psymetrics test 2022 Математичний тест РІВНЯННЯ І НЕРІВНОСТІ.mhtml",
        "kind": "mhtml",
    },
    {
        "library": "psymetrics-2022",
        "block": "abstract",
        "source": "odd-one-out-1",
        "title": "Виключення зайвого",
        "order": 1,
        "path": MATERIALS / "3" / "Psymetrics test 2022 Абстрактно-логічний блок Виключення зайвого 1.pdf",
        "kind": "forms",
    },
    {
        "library": "psymetrics-2022",
        "block": "abstract",
        "source": "odd-one-out-2",
        "title": "Виключення зайвого 2",
        "order": 2,
        "path": MATERIALS / "3" / "Psymetrics test 2022  Абстрактно-логічний блок Виключення зайвого_2.pdf",
        "kind": "forms",
    },
    {
        "library": "psymetrics-2022",
        "block": "abstract",
        "source": "sequences",
        "title": "Послідовності",
        "order": 3,
        "path": MATERIALS / "3" / "Psymetrics test 2022 Абстрактно-логічний блок Послідовності.pdf",
        "kind": "forms",
    },
    {
        "library": "psymetrics-2022",
        "block": "abstract",
        "source": "sequence-2",
        "title": "Завершення послідовності 2",
        "order": 4,
        "path": MATERIALS / "3" / "Psymetrics test 2022 Абстрактно-логічний блок Завершення послідовності_2.pdf",
        "kind": "forms",
    },
    {
        "library": "startexam-2022",
        "block": "abstract",
        "source": "timing-1",
        "title": "Тренування таймінгу 1",
        "order": 1,
        "path": MATERIALS / "4" / "StartExam 2022 Абстрактно-логічний блок_5.pdf",
        "kind": "startexam",
    },
    {
        "library": "startexam-2022",
        "block": "abstract",
        "source": "timing-2",
        "title": "Тренування таймінгу 2",
        "order": 2,
        "path": MATERIALS / "4" / "StartExam 2022 Абстрактно-логічний блок_4.pdf",
        "kind": "startexam",
    },
    {
        "library": "startexam-2022",
        "block": "abstract",
        "source": "timing-3",
        "title": "Тренування таймінгу 3",
        "order": 3,
        "path": MATERIALS / "4" / "StartExam 2022 АБСТРАКТНО-ЛОГІЧНИЙ Блок.pdf",
        "kind": "startexam",
    },
    {
        "library": "startexam-2022",
        "block": "abstract",
        "source": "timing-4",
        "title": "Тренування таймінгу 4",
        "order": 4,
        "path": MATERIALS / "4" / "StartExam 2022 Абстрактно-логічний блок_3.pdf",
        "kind": "startexam",
    },
    {
        "library": "startexam-2022",
        "block": "abstract",
        "source": "block-2",
        "title": "Блок 2",
        "order": 5,
        "path": MATERIALS / "4" / "StartExam 2022 Абстрактно-логічний блок_2.pdf",
        "kind": "startexam",
    },
]


def norm(value: str) -> str:
    value = value.replace("\xa0", " ").replace("\u00ad", "")
    value = value.replace("’", "'").replace("`", "'").replace("–", "-").replace("—", "-")
    value = value.strip().strip(".").casefold()
    return re.sub(r"\s+", " ", value)


def clean_text(value: str) -> str:
    value = value.replace("\xa0", " ").replace("\u00ad", "")
    value = EMAIL_RE.sub("", value)
    value = URL_RE.sub("", value)
    kept = []
    for line in value.splitlines():
        low = line.lower()
        if "meta-consulting" in low or "meta consulting" in low:
            continue
        if "електронна адреса" in low or "электронная почта" in low:
            continue
        if low.startswith("учасник") or low.startswith("участник"):
            continue
        kept.append(line.strip())
    return re.sub(r"[ \t]+", " ", "\n".join(kept)).strip()


def pos(item: dict) -> float:
    return item["page"] * 10000 + item["y"]


def expected_count(text: str) -> int | None:
    match = EXPECTED_SLASH_RE.search(text)
    if match:
        return int(match.group(2))
    found = [int(item.group(2)) for item in EXPECTED_IZ_RE.finditer(text)]
    if not found:
        return None
    return max(found)


def forms_items(doc: pymupdf.Document) -> list[dict]:
    items = []
    for page_index, page in enumerate(doc):
        data = page.get_text("dict")
        for block in data["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                text = "".join(span["text"] for span in line["spans"]).replace("\xa0", " ").strip()
                if not text:
                    continue
                y = line["bbox"][1]
                if y < 36 or y > 800:
                    continue
                colors = [span["color"] for span in line["spans"] if span["text"].strip()]
                items.append(
                    {
                        "kind": "text",
                        "text": text,
                        "y": y,
                        "page": page_index,
                        "color": colors[0] if colors else 0,
                    }
                )
        page_area = page.rect.width * page.rect.height
        seen = set()
        for info in page.get_images(full=True):
            xref = info[0]
            if xref in seen:
                continue
            seen.add(xref)
            rects = page.get_image_rects(xref)
            if not rects:
                continue
            rect = rects[0]
            if rect.y0 < 36 or rect.y0 > 800:
                continue
            if rect.width < 80 or rect.height < 40:
                continue
            if rect.width * rect.height >= 0.85 * page_area:
                continue
            items.append(
                {
                    "kind": "image",
                    "xref": xref,
                    "y": rect.y0,
                    "page": page_index,
                    "w": info[2],
                    "h": info[3],
                }
            )
    items.sort(key=lambda item: (item["page"], item["y"], 0 if item["kind"] == "text" else 1))
    return items


def prompt_before(score: dict, texts: list[dict], previous: dict | None) -> list[dict]:
    floor = pos(previous) if previous else -1
    cands = [line for line in texts if floor < pos(line) < pos(score)]
    chosen = []
    prev = score
    for line in reversed(cands):
        if line["text"] in {"Відгук", "Правильна відповідь"} or SCORE_RE.match(line["text"]):
            break
        if line["page"] != prev["page"]:
            if chosen or score["y"] > 180 or line["y"] < 620:
                break
        elif prev["y"] - line["y"] > 28 and chosen:
            break
        elif prev is score and score["y"] - line["y"] > 80:
            break
        chosen.append(line)
        prev = line
    return list(reversed(chosen))


def join_wrapped(lines: list[dict]) -> list[dict]:
    if not lines:
        return []
    groups = [dict(lines[0])]
    for line in lines[1:]:
        gap = line["y"] - groups[-1]["y"] if line["page"] == groups[-1]["page"] else 100
        if gap < 16:
            groups[-1]["text"] = f"{groups[-1]['text']} {line['text']}"
            groups[-1]["y"] = line["y"]
        else:
            groups.append(dict(line))
    return groups


KEY_GUESSES = [
    re.compile(r"відповідь та рішення:\s*([^\s.]+)", re.I),
    re.compile(r"правильна відповідь\s*[-–—:]\s*[\"«']?([A-EА-Яа-яІіЇїЄє0-9]{1,4})", re.I),
    re.compile(r"варіант\s*[\"«']([A-EА-Е0-9])[\"»']", re.I),
]


def guess_keys(explanation: str) -> list[str]:
    found = []
    for pattern in KEY_GUESSES:
        found.extend(pattern.findall(explanation))
    return found


def keep_choices(prompt: str, options: list[str], colors: list[int]) -> tuple[str, list[str], list[int]]:
    prose = [opt for opt in options if len(opt) > 60 or opt.endswith("?")]
    short = [(opt, color) for opt, color in zip(options, colors) if len(opt) <= 60 and not opt.endswith("?")]
    if prose and short:
        prompt = clean_text(f"{prompt} {' '.join(prose)}")
        options = [opt for opt, _color in short]
        colors = [color for _opt, color in short]
    seen = set()
    kept_options = []
    kept_colors = []
    for opt, color in zip(options, colors):
        key = norm(opt)
        if key in seen:
            continue
        seen.add(key)
        kept_options.append(opt)
        kept_colors.append(color)
    return prompt, kept_options, kept_colors


def match_keys(options: list[str], key_lines: list[str]) -> tuple[list[str], list[str]]:
    unused = set(range(len(options)))
    matched = []
    unmatched = []
    for raw in key_lines:
        key = norm(raw)
        found = None
        for index in list(unused):
            if norm(options[index]) == key:
                found = index
                break
        if found is None:
            unmatched.append(raw)
            continue
        unused.remove(found)
        matched.append(str(found + 1))
    return matched, unmatched


def parse_forms(doc: pymupdf.Document) -> list[dict]:
    items = forms_items(doc)
    texts = [item for item in items if item["kind"] == "text"]
    scores = [item for item in texts if SCORE_RE.match(item["text"])]
    parsed = []
    for index, score in enumerate(scores):
        previous = scores[index - 1] if index else None
        nxt = scores[index + 1] if index + 1 < len(scores) else None
        prompt_lines = prompt_before(score, texts, previous)
        prompt_ids = {id(line) for line in prompt_lines}
        end = pos(nxt) if nxt else 10**12
        if nxt:
            next_prompt = prompt_before(nxt, texts, score)
            if next_prompt:
                end = pos(next_prompt[0])
        body = [
            line
            for line in texts
            if pos(score) < pos(line) < end and id(line) not in prompt_ids and not SCORE_RE.match(line["text"])
        ]
        marker = None
        feedback = None
        for line_index, line in enumerate(body):
            if line["text"] == "Правильна відповідь" and marker is None:
                marker = line_index
            elif line["text"] == "Відгук" and feedback is None:
                feedback = line_index
                break
        option_end = marker if marker is not None else feedback
        option_lines = join_wrapped(body[:option_end] if option_end is not None else body)
        options = []
        option_colors = []
        for line in option_lines:
            text = clean_text(line["text"])
            if not text or text in {"Відгук", "Правильна відповідь"}:
                continue
            if URL_RE.search(line["text"]) and len(text) < 8:
                continue
            options.append(text)
            option_colors.append(line["color"])
        explicit = []
        if marker is not None:
            stop = feedback if feedback is not None else len(body)
            explicit = [clean_text(line["text"]) for line in join_wrapped(body[marker + 1 : stop])]
            explicit = [line for line in explicit if line and line not in {"Відгук", "Правильна відповідь"}]
        explanation = ""
        if feedback is not None:
            explanation = clean_text("\n".join(line["text"] for line in body[feedback + 1 :]))
        got = SCORE_RE.match(score["text"]).group(1)
        prompt = clean_text(" ".join(line["text"] for line in prompt_lines))
        prompt, options, option_colors = keep_choices(prompt, options, option_colors)
        correct = []
        issues = []
        if explicit:
            correct, _unmatched = match_keys(options, explicit)
        elif got == "1" and options:
            chosen = [str(opt_index + 1) for opt_index, color in enumerate(option_colors) if color == score["color"]]
            if chosen and len(chosen) < len(options):
                correct = chosen
            else:
                issues.append("key-missing")
        else:
            issues.append("key-missing")
        if not correct and explanation:
            correct, _unmatched = match_keys(options, guess_keys(explanation))
            if correct:
                issues = [issue for issue in issues if issue != "key-missing"]
        if not correct and "key-missing" not in issues:
            issues.append("key-missing")
        if not options:
            issues.append("no-options")
        images = [
            item
            for item in items
            if item["kind"] == "image" and pos(score) - 8 <= pos(item) < end
        ]
        if not prompt:
            issues.append("prompt-missing")
        parsed.append(
            {
                "prompt": prompt,
                "options": options,
                "correct": correct,
                "explanation": explanation,
                "issues": issues,
                "images": images,
                "pages": sorted({score["page"] + 1, *(item["page"] + 1 for item in images)}),
            }
        )
    return parsed


def startexam_selected(raw: str) -> bool:
    if OPTION_PREFIX_RE.match(raw.strip()):
        return True
    return bool(PUA_RE.search(raw))


def startexam_option_text(raw: str) -> str:
    text = PUA_RE.sub("", raw)
    text = OPTION_PREFIX_RE.sub("", text.strip())
    text = re.sub(r"^[-–—•]\s*", "", text.strip())
    return clean_text(text)


def parse_startexam(doc: pymupdf.Document) -> list[dict]:
    items = forms_items(doc)
    questions = []
    current = None

    def finish() -> None:
        nonlocal current
        if current is None:
            return
        options = current["options"]
        selected = [str(index + 1) for index, opt in enumerate(options) if opt["selected"]]
        issues = []
        correct = []
        result = current["result"]
        if result == "right" and selected:
            correct = selected
        else:
            issues.append("key-missing")
        if not options:
            issues.append("no-options")
        prompt = clean_text(re.sub(r"^\d+\.\s*", "", current["prompt"]))
        if not prompt:
            issues.append("prompt-missing")
        questions.append(
            {
                "prompt": prompt,
                "options": [opt["text"] for opt in options if opt["text"]],
                "correct": correct if options else [],
                "explanation": clean_text(" ".join(current["notes"])),
                "issues": issues,
                "images": current["images"],
                "pages": sorted({item["page"] + 1 for item in current["images"]} or {current["page"] + 1}),
            }
        )
        # Selected indexes were computed before dropping empty texts. Rebuild if needed.
        kept = [opt for opt in options if opt["text"]]
        if correct and len(kept) != len(options):
            questions[-1]["options"] = [opt["text"] for opt in kept]
            questions[-1]["correct"] = [str(index + 1) for index, opt in enumerate(kept) if opt["selected"] and result == "right"]
        current = None

    for item in items:
        if item["kind"] == "image":
            if current is not None and current["result"] is None:
                current["images"].append(item)
            continue
        text = item["text"]
        numbered = STARTEXAM_Q_RE.match(text)
        if numbered and not text.lower().startswith("http"):
            finish()
            current = {
                "prompt": numbered.group(2) or numbered.group(1),
                "options": [],
                "notes": [],
                "images": [],
                "result": None,
                "page": item["page"],
            }
            if not numbered.group(2):
                current["prompt"] = ""
            continue
        if current is None or current["result"] is not None:
            continue
        low = text.lower()
        if "вы ответили правильно" in low:
            current["result"] = "right"
            continue
        if "вы ответили неправильно" in low or "вы пропустили" in low:
            current["result"] = "wrong" if "неправильно" in low else "skipped"
            continue
        if text in {"Результат"} or low.startswith("баллы:") or low.startswith("затраченное время"):
            continue
        plain = startexam_option_text(text)
        if PUA_RE.search(text) and not plain:
            if current["options"]:
                current["options"][-1]["selected"] = True
            continue
        choice = bool(re.fullmatch(r"[A-FА-ЕІЇ1-6]", plain))
        if OPTION_PREFIX_RE.match(text.strip()) or re.match(r"^[-–—•]\s+\S", text.strip()) or (PUA_RE.search(text) and plain) or choice:
            if plain:
                current["options"].append({"text": plain, "selected": startexam_selected(text)})
            continue
        if current["options"]:
            current["notes"].append(text)
        else:
            current["prompt"] = f"{current['prompt']} {text}".strip()
    finish()
    return questions


class FormHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.questions: list[dict] = []
        self.current: dict | None = None
        self.capture = None
        self.skip_depth = 0
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._depth += 1
        attr = {key: value or "" for key, value in attrs}
        classes = set(attr.get("class", "").split())
        if tag == "div" and "Qr7Oae" in classes:
            if self.current:
                self.questions.append(self.current)
            self.current = {
                "prompt": "",
                "score": "",
                "options": [],
                "after_key": False,
                "keys": [],
                "explanation": "",
                "capture": None,
                "image_srcs": [],
            }
        if self.current is None:
            return
        if tag == "div" and "RGoode" in classes:
            self.current["capture"] = "score"
        elif tag == "span" and "M7eMe" in classes:
            self.current["capture"] = "prompt"
        elif attr.get("role") == "heading" and "Правильна" in attr.get("aria-label", ""):
            self.current["after_key"] = True
        elif tag == "img" and "googleusercontent" in attr.get("src", ""):
            self.current["image_srcs"].append(attr["src"])
        elif attr.get("role") == "radio":
            label = attr.get("aria-label", "")
            checked = attr.get("aria-checked") == "true"
            bucket = self.current["keys"] if self.current["after_key"] else self.current["options"]
            bucket.append({"text": label, "checked": checked})
        elif tag == "div" and attr.get("role") == "heading" and self.current["options"] and not self.current["after_key"]:
            self.current["capture"] = "heading"
        elif "freebirdFormviewerViewItemsItemGraderExplanation" in classes or attr.get("aria-label", "").startswith("Відгук"):
            self.current["capture"] = "explanation"

    def handle_endtag(self, tag: str) -> None:
        self._depth -= 1
        if self.current and tag in {"div", "span"}:
            if self.current["capture"] in {"score", "prompt", "explanation"}:
                self.current["capture"] = None

    def handle_data(self, data: str) -> None:
        if not self.current or not self.current["capture"]:
            return
        text = data.replace("\xa0", " ")
        if not text.strip():
            return
        field = self.current["capture"]
        if field == "heading" and "Правильна відповідь" in text:
            self.current["after_key"] = True
            self.current["capture"] = None
            return
        if field == "explanation" and self.current["after_key"] is False and "Правильна відповідь" in text:
            self.current["after_key"] = True
            return
        self.current[field if field != "heading" else "explanation"] += text

    def close_all(self) -> list[dict]:
        if self.current:
            self.questions.append(self.current)
            self.current = None
        return self.questions


def decode_mhtml(path: Path) -> str:
    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    for part in message.walk():
        if part.get_content_type() == "text/html":
            payload = part.get_payload(decode=True)
            if payload:
                return payload.decode("utf-8", errors="ignore")
    raw = path.read_text(encoding="utf-8", errors="ignore")
    marker = "Content-Type: text/html"
    start = raw.find(marker)
    rest = raw[start:]
    sep = rest.find("\r\n\r\n")
    body = rest[sep + 4 :]
    end = body.find("------MultipartBoundary")
    return quopri.decodestring(body[:end].encode("latin1", errors="ignore")).decode("utf-8", errors="ignore")


def parse_mhtml(path: Path) -> list[dict]:
    html = decode_mhtml(path)
    parser = FormHTMLParser()
    parser.feed(html)
    parsed = []
    for question in parser.close_all():
        score = re.sub(r"\s+", "", question["score"])
        options = []
        seen = set()
        for option in question["options"]:
            text = clean_text(option["text"])
            if not text or text in seen or text in {"Правильно", "Неправильно"}:
                continue
            seen.add(text)
            options.append({"text": text, "checked": option["checked"]})
        key_lines = []
        for option in question["keys"]:
            text = clean_text(option["text"])
            if text and text not in {"Правильно", "Неправильно"} and text not in key_lines:
                key_lines.append(text)
        got_full = bool(re.fullmatch(r"(\d+)/\1", score))
        issues = []
        correct = []
        if key_lines:
            correct, unmatched = match_keys([opt["text"] for opt in options], key_lines)
            if unmatched:
                issues.append("key-unmatched")
        elif got_full:
            correct = [str(index + 1) for index, opt in enumerate(options) if opt["checked"]]
        else:
            issues.append("key-missing")
        if not correct:
            issues.append("key-missing")
        if not options:
            issues.append("no-options")
        prompt = clean_text(question["prompt"])
        if not prompt:
            issues.append("prompt-missing")
        parsed.append(
            {
                "prompt": prompt,
                "options": [opt["text"] for opt in options],
                "correct": correct,
                "explanation": clean_text(question["explanation"]),
                "issues": issues,
                "images": [],
                "pages": [],
                "image_srcs": question["image_srcs"],
            }
        )
    return [item for item in parsed if item["prompt"] or item["options"] or item["image_srcs"]]


def url_key(url: str) -> str:
    return url.split("=")[0]


def mhtml_images(path: Path) -> dict[str, tuple[bytes, str]]:
    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    found = {}
    for part in message.walk():
        if part.get_content_maintype() != "image":
            continue
        location = part.get("Content-Location") or ""
        payload = part.get_payload(decode=True)
        if not location or not payload or len(payload) < 2000:
            continue
        if "googlelogo" in location:
            continue
        found[url_key(location)] = (payload, part.get_content_subtype() or "jpg")
    return found


def save_image(doc: pymupdf.Document, xref: int, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    info = doc.extract_image(xref)
    if info["ext"] in {"jpg", "jpeg"}:
        dest.write_bytes(info["image"])
        return
    pix = pymupdf.Pixmap(doc, xref)
    if pix.n >= 4 and pix.alpha:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    pix.save(dest, jpg_quality=75)


def to_question(spec: dict, number: int, parsed: dict, image_paths: list[str]) -> dict:
    issues = list(dict.fromkeys(parsed["issues"]))
    if image_paths:
        issues = [issue for issue in issues if issue != "prompt-missing"]
    correct = [item for item in parsed["correct"] if item]
    if not correct and "key-missing" not in issues:
        issues.append("key-missing")
    if "key-missing" in issues:
        correct = []
    interaction = "multi" if len(correct) > 1 else "single"
    return {
        "id": f"{spec['library']}-{spec['source']}-{number:04d}",
        "library": spec["library"],
        "block": spec["block"],
        "source": spec["source"],
        "source_title": spec["title"],
        "source_order": spec["order"],
        "number": number,
        "prompt": parsed["prompt"],
        "interaction": interaction,
        "stimulus_images": image_paths,
        "options": [{"id": str(index + 1), "text": text, "image": None} for index, text in enumerate(parsed["options"])],
        "correct": correct,
        "explanation": parsed["explanation"],
        "source_pages": parsed["pages"],
        "confidence": "low" if "key-missing" in issues or "key-unmatched" in issues else "high",
        "issues": issues,
        "duplicate_of": None,
    }


def load_source(spec: dict, write_images: bool) -> tuple[list[dict], dict]:
    if not spec["path"].exists():
        raise SystemExit(f"missing {spec['path']}")
    embedded = {}
    if spec["kind"] == "mhtml":
        parsed = parse_mhtml(spec["path"])
        embedded = mhtml_images(spec["path"])
        doc = None
        header = ""
    else:
        doc = pymupdf.open(spec["path"])
        header = "\n".join((doc[i].get_text("text") or "") for i in range(min(2, doc.page_count)))
        parsed = parse_forms(doc) if spec["kind"] == "forms" else parse_startexam(doc)
    questions = []
    for number, item in enumerate(parsed, start=1):
        paths = []
        if write_images and doc is not None:
            for image_index, image in enumerate(item["images"], start=1):
                name = f"q{number:04d}.jpg" if len(item["images"]) == 1 else f"q{number:04d}-{image_index}.jpg"
                dest = RAW / spec["library"] / spec["source"] / name
                save_image(doc, image["xref"], dest)
                paths.append(dest.relative_to(ROOT).as_posix())
        elif spec["kind"] == "mhtml":
            for image_index, src in enumerate(item.get("image_srcs") or [], start=1):
                blob = embedded.get(url_key(src))
                if not blob:
                    continue
                payload, subtype = blob
                ext = "jpg" if subtype in {"jpg", "jpeg"} else "png"
                name = f"q{number:04d}.{ext}" if len(item["image_srcs"]) == 1 else f"q{number:04d}-{image_index}.{ext}"
                dest = RAW / spec["library"] / spec["source"] / name
                if write_images:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(payload)
                    paths.append(dest.relative_to(ROOT).as_posix())
                else:
                    paths.append(name)
        questions.append(to_question(spec, number, item, paths))
    if doc is not None:
        doc.close()
    report = {
        "file": spec["path"].name,
        "library": spec["library"],
        "source": spec["source"],
        "expected": expected_count(header) if spec["kind"] != "mhtml" else None,
        "parsed": len(questions),
        "missing_keys": sum("key-missing" in q["issues"] for q in questions),
        "unmatched_keys": sum("key-unmatched" in q["issues"] for q in questions),
        "missing_prompts": sum("prompt-missing" in q["issues"] for q in questions),
        "no_options": sum("no-options" in q["issues"] for q in questions),
        "with_images": sum(bool(item["images"] or item.get("image_srcs")) for item in parsed),
    }
    if spec["kind"] == "mhtml":
        html = decode_mhtml(spec["path"])
        report["expected"] = expected_count(re.sub(r"<[^>]+>", " ", html)[:4000])
    return questions, report


def dump_item(item: dict) -> str:
    dumped = json.dumps(item, ensure_ascii=False, indent=2)
    return "\n".join(f"  {line}" if line else line for line in dumped.split("\n"))


def write_bank(imported: list[dict]) -> None:
    text = QUESTIONS.read_text(encoding="utf-8")
    marker = '"library": "femida-2022"'
    if marker in text:
        obj = text.rfind("\n  {", 0, text.find(marker))
        head = text[:obj].rstrip()
        if head.endswith(","):
            head = head[:-1].rstrip()
        text = head + "\n]\n"
    stripped = text.rstrip()
    if not stripped.endswith("]"):
        raise SystemExit("questions.json does not end with an array")
    body = stripped[:-1].rstrip()
    if not body.endswith("}"):
        raise SystemExit("questions.json has no trailing object")
    addition = ",\n".join(dump_item(item) for item in imported)
    QUESTIONS.write_text(body + ",\n" + addition + "\n]\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.write and RAW.exists():
        shutil.rmtree(RAW)
    imported: list[dict] = []
    reports = []
    for spec in SOURCES:
        questions, report = load_source(spec, write_images=args.write)
        imported.extend(questions)
        reports.append(report)
        flag = "ok" if report["expected"] in (None, report["parsed"]) else "COUNT"
        print(
            f"{flag:5} {report['parsed']:4}/{str(report['expected']):>4} "
            f"keys-missing {report['missing_keys']:3} unmatched {report['unmatched_keys']:3} "
            f"no-prompt {report['missing_prompts']:3} no-options {report['no_options']:3} imgs {report['with_images']:3} "
            f"{spec['library']} {spec['source']}"
        )
    if args.write:
        write_bank(imported)
        REPORT.write_text(json.dumps({"files": reports, "questions": len(imported)}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {len(imported)} questions")
    else:
        print("--- remaining gaps ---")
        for question in imported:
            if "no-options" in question["issues"] or (
                question["source"] == "equations-inequalities" and "prompt-missing" in question["issues"]
            ):
                print(
                    question["source"],
                    question["number"],
                    question["issues"],
                    question["prompt"][:90],
                    [opt["text"] for opt in question["options"][:8]],
                    question["correct"],
                )


if __name__ == "__main__":
    main()
