"""Offline and loopback proofs for local decoder boundaries."""
import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parent / "potato-microdecoders"
sys.path.insert(0, str(PACKAGE))
from catalog import PROFILES
from decoder import Decoder, exact_route, validate_jobs


class MicrodecoderTests(unittest.TestCase):
    def test_catalog_routes_all_100_explicit_task_types_without_model(self):
        self.assertEqual(len(PROFILES), 100)
        self.assertEqual(len({row["id"] for row in PROFILES}), 100)
        decoder = Decoder()
        with patch.object(decoder, "load", side_effect=AssertionError("Unneeded neural call")):
            for profile in PROFILES:
                output = decoder.decode(["Find " + profile["phrases"][0]], neural=True)
                self.assertEqual(output["results"][0]["task"], profile["id"])
                self.assertEqual(output["results"][0]["backend"], "deterministic")

    def test_batch_limits_and_input_types(self):
        for jobs in [[], ["x"] * 101, [None], [""], ["x " * 32], ["界" * 400], "request"]:
            with self.subTest(jobs=str(jobs)[:60]), self.assertRaises(ValueError):
                validate_jobs(jobs)
        validate_jobs(["request"] * 100)

    def test_ambiguous_and_unknown_requests_return_to_primary(self):
        for text in ["git diff changes and git history log", "Write a birthday poem"]:
            self.assertIsNone(exact_route(text))
            output = Decoder().decode([text])["results"][0]
            self.assertEqual(output["backend"], "primary_agent")
            self.assertTrue(output["needs_primary_review"])

    def test_missing_neural_models_fall_back(self):
        with tempfile.TemporaryDirectory() as directory:
            result = Decoder(directory).decode(["A request without an exact route"], neural=True)
        self.assertEqual(result["results"][0]["backend"], "primary_agent")
        self.assertEqual(result["fallback_reason"], "FileNotFoundError")

    def test_model_size_and_causal_attention_contract(self):
        import torch
        from model import TinyGPT, parameter_count
        torch.set_num_threads(2)
        self.assertGreaterEqual(parameter_count(), 990000)
        self.assertLessEqual(parameter_count(), 1000000)
        model = TinyGPT(2).eval()
        with torch.no_grad():
            first = model.features(torch.tensor([[2, 3, 4, 5]]), torch.tensor([1]))
            changed_future = model.features(torch.tensor([[2, 3, 9, 10]]), torch.tensor([1]))
        self.assertTrue(torch.allclose(first, changed_future, atol=1e-6))

    def test_checkpoint_tampering_is_rejected_before_loading_weights(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "decoders.pt").write_bytes(b"not trusted weights")
            (root / "qualification.json").write_text(json.dumps({"sha256": "wrong"}))
            with self.assertRaisesRegex(ValueError, "qualification"):
                Decoder(root).load()

    def test_changed_catalog_cannot_relabel_trained_specialists(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = b"checkpoint bytes"
            (root / "decoders.pt").write_bytes(raw)
            (root / "qualification.json").write_text(json.dumps({"sha256": hashlib.sha256(raw).hexdigest(),
                "catalog_sha256": "different catalog", "enabled": [], "confidence_threshold": .95, "margin_threshold": .1}))
            with patch("torch.load", side_effect=AssertionError("Catalog mismatch reached model loader")):
                with self.assertRaisesRegex(ValueError, "catalog"):
                    Decoder(root).load()

    def test_loopback_api_accepts_bounded_json_and_rejects_browser_origin(self):
        process = subprocess.Popen([sys.executable, str(PACKAGE / "decoder.py"), "serve", "--port", "0"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            info = json.loads(process.stdout.readline())
            self.assertTrue(info["listening"].startswith("http://127.0.0.1:"))
            body = json.dumps({"jobs": ["Find git diff changes"]}).encode()
            req = urllib.request.Request(info["listening"], data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.load(response)
            self.assertEqual(result["results"][0]["task"], "git.diff")
            req.add_header("Origin", "https://example.com")
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(req, timeout=5)
            self.assertEqual(error.exception.code, 400)
        finally:
            process.terminate()
            process.communicate(timeout=10)


if __name__ == "__main__":
    unittest.main()
