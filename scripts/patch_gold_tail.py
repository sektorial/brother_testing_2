"""Hand fixes for the few GOLD items the image read still left open."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "questions.json"

OPTIONS = {
    54: ["Щільний", "Кристалічний", "Стійкий", "Різноманітний", "Надійний"],
    136: ["Багряний", "Норовливий"],
    152: ["Четвер", "Субота", "Вівторок", "Середа", "П'ятниця"],
}
CORRECT = {
    23: ["Палички"],
    54: ["Кристалічний"],
    73: ["Аспірин", "Пеніцилін"],
    98: ["Сад"],
    99: ["Острів"],
    118: ["Какофонія"],
    119: ["Викладати", "Шити одяг"],
    136: ["Норовливий"],
    152: ["Вівторок"],
}
ISSUES = {
    136: ["buttons-illegible"],
}


def main() -> None:
    records = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    for record in records:
        if record["source"] != "verbal-gold":
            continue
        number = record["number"]
        if record["explanation"].startswith(": "):
            record["explanation"] = record["explanation"][2:]
        if number in OPTIONS:
            record["options"] = [{"id": word, "text": word, "image": None} for word in OPTIONS[number]]
        if number in CORRECT:
            record["correct"] = CORRECT[number]
            record["issues"] = ISSUES.get(number, [])
            record["confidence"] = "low" if record["issues"] else "high"
    QUESTIONS.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    gold = [record for record in records if record["source"] == "verbal-gold"]
    low = [record for record in gold if record["confidence"] != "high"]
    print("low", len(low), [(record["number"], record["issues"]) for record in low])


if __name__ == "__main__":
    main()
