"""Verify the trusted one-page demo corpus with Poppler and Pillow.

This checks generated fixtures, not hostile client uploads or arbitrary PDF layouts.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageOps, ImageStat
from pypdf import PdfReader, PdfWriter


def verify(demo: Path, output: Path):
    demo = demo.resolve()
    poppler = shutil.which("pdftoppm")
    if not poppler:
        raise RuntimeError("Install Poppler and put pdftoppm on PATH")
    manifest = json.loads((demo / "results/manifest.json").read_text())
    jobs = manifest["files"]
    if len(jobs) != 80:
        raise ValueError("This evaluator expects the 80-file generated fixture")
    inputs, outputs = [], []
    for job in jobs:
        for path, key, pages in [
            (demo / job["input"], "input_sha256", inputs),
            (demo / "results" / job["output"], "output_sha256", outputs),
        ]:
            path = path.resolve()
            if not path.is_relative_to(demo):
                raise ValueError("Manifest path escapes fixture directory")
            if hashlib.sha256(path.read_bytes()).hexdigest() != job[key]:
                raise ValueError("Fixture hash differs from processing manifest")
            reader = PdfReader(path)
            if len(reader.pages) != 1:
                raise ValueError("Visual evaluator is restricted to one-page fixtures")
            pages.append(reader.pages[0])
    output.mkdir(parents=True, exist_ok=False)
    rendered = {}
    for label, pages in [("input", inputs), ("output", outputs)]:
        writer = PdfWriter()
        for page in pages:
            writer.add_page(page)
        corpus = output / (label + ".pdf")
        with corpus.open("xb") as stream:
            writer.write(stream)
        subprocess.run([poppler, "-r", "72", "-png", str(corpus), str(output / label)],
                       check=True, capture_output=True, timeout=180)
        rendered[label] = sorted(output.glob(label + "-*.png"),
                                 key=lambda p: int(p.stem.rsplit("-", 1)[1]))
        if len(rendered[label]) != len(jobs):
            raise AssertionError("Rendered page count differs from manifest")
        print(f"Rendered {len(pages)} {label} pages", flush=True)
    operations = {
        "mirror_horizontal": ImageOps.mirror,
        "mirror_vertical": ImageOps.flip,
        "rotate_180": lambda im: im.transpose(Image.Transpose.ROTATE_180),
        "copy": lambda im: im.copy(),
    }
    rows = []
    for i, job in enumerate(jobs):
        with Image.open(rendered["input"][i]) as before, Image.open(rendered["output"][i]) as after:
            expected = operations[job["operation"]](before.convert("RGB"))
            actual = after.convert("RGB")
            if expected.size != actual.size:
                raise AssertionError("Render dimensions changed")
            mae = sum(ImageStat.Stat(ImageChops.difference(expected, actual)).mean) / 3
            if mae > 2.0:
                raise AssertionError(f"Visual threshold exceeded for {job['output']}: {mae}")
            rows.append({"file": job["output"], "operation": job["operation"],
                         "mean_absolute_rgb_difference_0_to_255": round(mae, 6)})
    result = {
        "files_rendered_and_compared": len(rows), "resolution_dpi": 72,
        "mean_absolute_rgb_error_limit": 2.0,
        "max_observed_mean_absolute_rgb_error": max(r["mean_absolute_rgb_difference_0_to_255"] for r in rows),
        "scope": "Self-created one-page fixtures from one template. Includes mirrored text by design.",
        "files": rows,
    }
    (output / "render_verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "files"}))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("demo", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify(args.demo, args.output)
