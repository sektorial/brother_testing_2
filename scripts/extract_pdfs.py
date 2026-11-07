"""Extract page images, embedded figures, and text layers from the test PDFs.

Page snapshots and figures are files. The text layer is only a draft.
"""

from __future__ import annotations

import json
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
MATERIALS = ROOT / "materials"
RAW = ROOT / "data" / "raw"

def source_files() -> list[tuple[str, Path]]:
    pdfs = list(MATERIALS.glob("*.pdf"))
    found = {}
    for path in pdfs:
        name = path.name
        if "GOLD" in name:
            found["verbal-gold"] = path
        elif "STANDART" in name:
            found["verbal-standart"] = path
        elif "PSYMETRICS" in name:
            found["math"] = path
        else:
            found["abstract"] = path
    order = ["abstract", "math", "verbal-gold", "verbal-standart"]
    missing = [key for key in order if key not in found]
    if missing or len(pdfs) != 4:
        raise SystemExit(f"unexpected materials: {missing} count={len(pdfs)}")
    return [(key, found[key]) for key in order]

PAGE_DPI = 110
JPEG_QUALITY = 80
# An image that covers almost the whole page is the page snapshot, not a figure.
FULL_PAGE_RATIO = 0.85


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def save_pixmap(pix: pymupdf.Pixmap, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if pix.n >= 4 and pix.alpha:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    pix.save(dest, jpg_quality=JPEG_QUALITY)


def image_entries(page: pymupdf.Page) -> list[dict]:
    page_area = page.rect.width * page.rect.height
    entries = []
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
        area = rect.width * rect.height
        entries.append(
            {
                "xref": xref,
                "width": info[2],
                "height": info[3],
                "bbox": [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)],
                "full_page": area >= FULL_PAGE_RATIO * page_area,
            }
        )
    entries.sort(key=lambda e: (round(e["bbox"][1], 0), e["bbox"][0]))
    return entries


def write_xref_image(doc: pymupdf.Document, xref: int, dest_stem: Path, suffix: str) -> Path:
    pix = pymupdf.Pixmap(doc, xref)
    if pix.n >= 4 and pix.alpha:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    elif pix.colorspace and pix.colorspace.n != 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    dest = dest_stem.with_suffix(suffix)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".jpg":
        pix.save(dest, jpg_quality=JPEG_QUALITY)
    else:
        pix.save(dest)
    return dest


def extract_source(source: str, src: Path) -> None:
    out = RAW / source
    if out.exists():
        for child in out.rglob("*"):
            if child.is_file():
                child.unlink()
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "text").mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open(src)
    pages = []
    for index, page in enumerate(doc):
        number = index + 1
        stem = f"{number:03d}"
        text = page.get_text()
        (out / "text" / f"p{stem}.txt").write_text(text, encoding="utf-8")

        entries = image_entries(page)
        full = [e for e in entries if e["full_page"]]
        figures = [e for e in entries if not e["full_page"]]

        if full:
            page_path = write_xref_image(doc, full[0]["xref"], out / f"page-{stem}", ".jpg")
        else:
            pix = page.get_pixmap(dpi=PAGE_DPI)
            page_path = out / f"page-{stem}.jpg"
            save_pixmap(pix, page_path)

        figure_rels = []
        for k, entry in enumerate(figures, start=1):
            fig_path = write_xref_image(doc, entry["xref"], out / "images" / f"p{stem}-{k}", ".png")
            entry["file"] = rel(fig_path)
            figure_rels.append(entry["file"])

        pages.append(
            {
                "page": number,
                "text": rel(out / "text" / f"p{stem}.txt"),
                "page_image": rel(page_path),
                "images": [
                    {"file": e["file"], "width": e["width"], "height": e["height"], "bbox": e["bbox"]}
                    for e in figures
                ],
            }
        )
        if number % 40 == 0 or number == doc.page_count:
            print(f"{source}: {number}/{doc.page_count}", flush=True)

    manifest = {"source": source, "file": src.name, "pages": pages}
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    doc.close()
    print(f"{source}: wrote {len(pages)} pages", flush=True)


def main() -> None:
    for source, path in source_files():
        extract_source(source, path)


if __name__ == "__main__":
    main()
