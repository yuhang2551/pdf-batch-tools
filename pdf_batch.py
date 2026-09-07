"""Manifest-driven whole-page PDF transforms, with explicit supported boundaries."""
from __future__ import annotations

import argparse
import hashlib
import json
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader, PdfWriter

OPERATIONS = {"mirror_horizontal", "mirror_vertical", "rotate_180", "copy"}
MAX_BYTES = 20 * 1024 * 1024
MAX_PAGES = 100


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_supported(data: bytes) -> PdfReader:
    if len(data) > MAX_BYTES or not data.startswith(b"%PDF-"):
        raise ValueError("Expected a PDF of at most 20 MiB")
    reader = PdfReader(BytesIO(data), strict=True)
    if reader.is_encrypted:
        raise ValueError("Encrypted PDFs are not supported")
    root = reader.trailer["/Root"]
    if any(k in root for k in ("/AcroForm", "/OpenAction", "/AA", "/Names")):
        raise ValueError("Forms, document actions and named/embedded objects require separate handling")
    if not 1 <= len(reader.pages) <= MAX_PAGES:
        raise ValueError("Each input must contain between 1 and 100 pages")
    for page in reader.pages:
        if page.get("/Annots") or page.get("/AA"):
            raise ValueError("Annotations and page actions are not supported")
        if page.rotation % 360 != 0 or float(page.get("/UserUnit", 1)) != 1:
            raise ValueError("Rotated pages and non-default user units require normalization first")
        box = tuple(float(v) for v in page.mediabox)
        crop = tuple(float(v) for v in page.cropbox)
        if box[:2] != (0.0, 0.0) or box != crop or box[2] <= 0 or box[3] <= 0:
            raise ValueError("Only positive, zero-origin, equal media/crop boxes are supported")
    return reader


def transform(data: bytes, operation: str) -> bytes:
    if operation not in OPERATIONS:
        raise ValueError("Unknown operation")
    reader = load_supported(data)
    writer = PdfWriter()
    for page in reader.pages:
        w, h = float(page.mediabox.width), float(page.mediabox.height)
        matrix = {"mirror_horizontal": (-1, 0, 0, 1, w, 0),
                  "mirror_vertical": (1, 0, 0, -1, 0, h),
                  "rotate_180": (-1, 0, 0, -1, w, h),
                  "copy": (1, 0, 0, 1, 0, 0)}[operation]
        output_page = writer.add_page(page)
        output_page.add_transformation(matrix)
    writer.add_metadata({"/Producer": "PDF Batch Tools", "/Subject": "Explicit whole-page transform"})
    stream = BytesIO()
    writer.write(stream)
    output = stream.getvalue()
    checked = load_supported(output)
    assert len(checked.pages) == len(reader.pages)
    return output


def run(manifest_path: Path, output: Path) -> dict:
    root = manifest_path.resolve().parent
    spec = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or set(spec) != {"version", "jobs"} or spec["version"] != 1:
        raise ValueError("Manifest must contain version 1 and jobs")
    jobs = spec["jobs"]
    if not isinstance(jobs, list) or not 1 <= len(jobs) <= 500:
        raise ValueError("A batch must contain 1 to 500 jobs")
    prepared, targets = [], set()
    for job in jobs:
        if not isinstance(job, dict) or set(job) != {"input", "output", "operation"}:
            raise ValueError("Each job requires input, output and operation only")
        if not all(isinstance(v, str) for v in job.values()):
            raise ValueError("Job fields must be strings")
        source = (root / job["input"]).resolve()
        if not source.is_relative_to(root):
            raise ValueError("Input escapes the manifest directory")
        name = job["output"]
        if Path(name).name != name or name in ("", ".", "..") or not name.lower().endswith(".pdf"):
            raise ValueError("Output must be a simple PDF filename")
        if name.casefold() in targets:
            raise ValueError("Duplicate output filenames are not allowed")
        targets.add(name.casefold())
        if source.stat().st_size > MAX_BYTES:
            raise ValueError("Input exceeds 20 MiB")
        data = source.read_bytes()
        converted = transform(data, job["operation"])
        pages = load_supported(data).pages
        prepared.append((job, converted, {"input": job["input"], "output": name,
            "operation": job["operation"], "input_sha256": digest(data),
            "output_sha256": digest(converted), "pages": len(pages),
            "page_sizes_pt": [[float(p.mediabox.width), float(p.mediabox.height)] for p in pages]}))
        if sum(len(p[1]) for p in prepared) > 100 * 1024 * 1024:
            raise ValueError("Prepared batch exceeds 100 MiB")
    # Preflight all jobs before producing any output. Existing directories are rejected.
    output.mkdir(parents=True, exist_ok=False)
    for job, converted, _ in prepared:
        with (output / job["output"]).open("xb") as stream:
            stream.write(converted)
    result = {"version": 1, "files_processed": len(prepared),
              "pages_processed": sum(p[2]["pages"] for p in prepared),
              "whole_page_transform_includes_text": True,
              "files": [p[2] for p in prepared]}
    with (output / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = run(args.manifest, args.output)
    except Exception as exc:
        parser.exit(2, f"PDF batch stopped: {type(exc).__name__}: {exc}\n")
    print(json.dumps({k: result[k] for k in ("files_processed", "pages_processed")}))


if __name__ == "__main__":
    main()
