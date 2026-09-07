"""Make 80 self-created diagram PDFs and exercise all four supported operations."""
import argparse
import json
from io import BytesIO
from pathlib import Path
from reportlab.pdfgen import canvas
from pdf_batch import run


def make_pdf(number=1, pages=1):
    stream = BytesIO()
    c = canvas.Canvas(stream, pagesize=(600, 420), invariant=1)
    c.setTitle("Synthetic schematic - not a construction drawing")
    c.setAuthor("Independent demonstration")
    for p in range(pages):
        c.setFillColorRGB(.96, .97, .99); c.rect(0, 0, 600, 420, fill=1, stroke=0)
        c.setFillColorRGB(.1, .16, .27); c.setFont("Helvetica-Bold", 19)
        c.drawString(36, 380, f"SYNTHETIC SCHEMATIC {number:03d}")
        c.setFont("Helvetica", 10); c.drawString(36, 358, "Whole-page transform fixture. Text is part of the page.")
        c.setStrokeColorRGB(.17, .24, .36); c.setLineWidth(2)
        c.rect(58, 92, 470, 230, fill=0)
        c.line(338, 92, 338, 322); c.line(58, 210, 338, 210); c.line(198, 92, 198, 210)
        c.setFillColorRGB(.86, .9, .98); c.rect(339, 93, 188, 228, fill=1, stroke=0)
        c.setFillColorRGB(.1, .16, .27); c.setFont("Helvetica-Bold", 15)
        c.drawString(378, 202, "GARAGE"); c.drawString(165, 263, "LIVING")
        c.setFont("Helvetica", 12); c.drawString(89, 150, "ROOM A"); c.drawString(236, 150, "ROOM B")
        c.setFillColorRGB(.8, .24, .12); c.circle(84, 301, 7, fill=1, stroke=0)
        c.setFillColorRGB(.1, .16, .27); c.setFont("Helvetica", 10)
        c.drawString(36, 42, f"Self-created test asset | Page {p+1}/{pages} | No client or architectural data")
        c.showPage()
    c.save()
    return stream.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("demo-output"))
    args = parser.parse_args()
    source_dir = args.output / "inputs"
    source_dir.mkdir(parents=True, exist_ok=False)
    operations = ["mirror_horizontal", "mirror_vertical", "rotate_180", "copy"]
    jobs = []
    for i in range(1, 81):
        name = f"schematic_{i:03d}.pdf"
        (source_dir / name).write_bytes(make_pdf(i))
        jobs.append({"input": "inputs/" + name, "output": name, "operation": operations[(i - 1) % 4]})
    manifest = args.output / "jobs.json"
    manifest.write_text(json.dumps({"version": 1, "jobs": jobs}, indent=2), encoding="utf-8")
    result = run(manifest, args.output / "results")
    assert result["files_processed"] == result["pages_processed"] == 80
    print(json.dumps({"fixture": "self-created", "files": 80, "pages": 80, "operations": operations}))


if __name__ == "__main__":
    main()
