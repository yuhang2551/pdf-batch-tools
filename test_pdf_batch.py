import hashlib
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, NumberObject, ArrayObject
from demo import make_pdf
from pdf_batch import load_supported, run, transform


class PdfBatchTests(unittest.TestCase):
    def setUp(self):
        self.data = make_pdf(pages=2)
    def test_all_operations_preserve_structure(self):
        for op in ["mirror_horizontal", "mirror_vertical", "rotate_180", "copy"]:
            r = load_supported(transform(self.data, op))
            self.assertEqual(len(r.pages), 2)
            self.assertEqual(tuple(r.pages[0].mediabox), (0, 0, 600, 420))
            self.assertIn("SYNTHETIC SCHEMATIC", r.pages[0].extract_text())
    def test_unknown_operation(self):
        with self.assertRaises(ValueError): transform(self.data, "guess")
    def test_invalid_file(self):
        with self.assertRaises(ValueError): transform(b"not a pdf", "copy")
    def test_encryption_rejected(self):
        w = PdfWriter(); w.add_blank_page(600, 420); w.encrypt("test-only")
        b = BytesIO(); w.write(b)
        with self.assertRaises(ValueError): load_supported(b.getvalue())
    def test_rotated_input_rejected(self):
        w = PdfWriter(); p = w.add_blank_page(600, 420); p.rotate(90)
        b = BytesIO(); w.write(b)
        with self.assertRaises(ValueError): load_supported(b.getvalue())
    def test_nonzero_origin_rejected(self):
        w = PdfWriter(); p = w.add_blank_page(600, 420); p.mediabox.lower_left = (1, 1)
        b = BytesIO(); w.write(b)
        with self.assertRaises(ValueError): load_supported(b.getvalue())
    def test_annotations_rejected(self):
        w = PdfWriter(); p = w.add_blank_page(600, 420)
        p[NameObject("/Annots")] = ArrayObject([NumberObject(1)])
        b = BytesIO(); w.write(b)
        with self.assertRaises(ValueError): load_supported(b.getvalue())
    def setup_manifest(self, directory, jobs=None):
        root = Path(directory); source = root / "source.pdf"; source.write_bytes(self.data)
        manifest = root / "jobs.json"
        manifest.write_text(json.dumps({"version": 1, "jobs": jobs or [{"input": "source.pdf", "output": "result.pdf", "operation": "mirror_horizontal"}]}))
        return root, source, manifest
    def test_source_preserved_and_hashes_match(self):
        with tempfile.TemporaryDirectory() as d:
            root, source, manifest = self.setup_manifest(d)
            result = run(manifest, root / "out")
            self.assertEqual(source.read_bytes(), self.data)
            self.assertEqual(result["files"][0]["output_sha256"], hashlib.sha256((root / "out/result.pdf").read_bytes()).hexdigest())
    def test_output_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            root, _, manifest = self.setup_manifest(d); run(manifest, root / "out")
            with self.assertRaises(FileExistsError): run(manifest, root / "out")
    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root, _, m = self.setup_manifest(d, [{"input": "../source.pdf", "output": "result.pdf", "operation": "copy"}])
            with self.assertRaises(ValueError): run(m, root / "out")
            self.assertFalse((root / "out").exists())
    def test_duplicate_output_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            j = {"input": "source.pdf", "output": "result.pdf", "operation": "copy"}
            root, _, m = self.setup_manifest(d, [j, {**j, "output": "RESULT.pdf"}])
            with self.assertRaises(ValueError): run(m, root / "out")
    def test_output_path_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root, _, m = self.setup_manifest(d, [{"input": "source.pdf", "output": "../result.pdf", "operation": "copy"}])
            with self.assertRaises(ValueError): run(m, root / "out")
    def test_preflight_no_partial_batch(self):
        with tempfile.TemporaryDirectory() as d:
            j = {"input": "source.pdf", "output": "result.pdf", "operation": "copy"}
            root, _, m = self.setup_manifest(d, [j, {**j, "output": "bad.pdf", "operation": "bad"}])
            with self.assertRaises(ValueError): run(m, root / "out")
            self.assertFalse((root / "out").exists())


if __name__ == "__main__":
    unittest.main()
