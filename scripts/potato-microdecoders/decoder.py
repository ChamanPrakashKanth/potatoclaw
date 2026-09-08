"""Batch request decoding with no tools, writes, or outbound networking."""
import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from catalog import PROFILES, catalog_digest

DEFAULT_MODELS = Path(__file__).resolve().parent / "models"


def validate_jobs(jobs):
    if not isinstance(jobs, list) or not 1 <= len(jobs) <= 100:
        raise ValueError("Expected 1-100 short request strings")
    for text in jobs:
        if not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > 1000 or len(re.findall(r"[a-z0-9_]+", text.lower())) > 31:
            raise ValueError("Each request must be nonempty, at most 31 words and 1000 bytes")


def exact_route(text):
    clean = " ".join(re.findall(r"[a-z0-9_]+", text.lower()))
    matches = [profile["id"] for profile in PROFILES if any(re.search(r"\b" + re.escape(phrase) + r"\b", clean) for phrase in profile["phrases"])]
    return matches[0] if len(matches) == 1 else None


class Decoder:
    def __init__(self, model_dir=DEFAULT_MODELS):
        self.model_dir = Path(model_dir)
        self.model = None

    def status(self):
        report_path = self.model_dir / "qualification.json"
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
        return {"profiles": len(PROFILES), "model_present": (self.model_dir / "decoders.pt").is_file(),
                "parameters_per_specialist": report.get("parameters_per_specialist"),
                "qualified_specialists": len(report.get("enabled", [])),
                "shared_backbone": True, "native_codex_subagents": False,
                "neural_preferred": report.get("challenge_accuracy", 0) > report.get("lexical_challenge_accuracy", 0),
                "token_savings_measured": False}

    def load(self):
        if self.model is not None:
            return
        import torch
        from model import TinyGPT, WIDTH
        report = json.loads((self.model_dir / "qualification.json").read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise ValueError("Invalid qualification record")
        path = self.model_dir / "decoders.pt"
        if path.stat().st_size > 8 * 1024 * 1024 or hashlib.sha256(path.read_bytes()).hexdigest() != report["sha256"]:
            raise ValueError("Checkpoint does not match qualification")
        if report.get("catalog_sha256") != catalog_digest():
            raise ValueError("Checkpoint catalog differs from qualification")
        enabled = report.get("enabled")
        if not isinstance(enabled, list) or any(not isinstance(name, str) or name not in {p["id"] for p in PROFILES} for name in enabled):
            raise ValueError("Invalid enabled specialists")
        for key in ("confidence_threshold", "margin_threshold"):
            if type(report.get(key)) not in (int, float) or not 0 < report[key] <= 1:
                raise ValueError("Invalid qualification threshold")
        torch.set_num_threads(2)
        state = torch.load(path, map_location="cpu", weights_only=True)
        model = TinyGPT(2)
        # The shared feature extractor is used without a generic output head.
        del model.head
        model.load_state_dict(state["backbone"], strict=True)
        heads = torch.nn.Linear(WIDTH, 200)
        heads.load_state_dict(state["heads"], strict=True)
        self.model, self.heads, self.report = model.eval(), heads.eval(), report

    def decode(self, jobs, neural=False):
        validate_jobs(jobs)
        start = time.monotonic()
        results = [{"task": exact_route(text), "backend": "deterministic"} for text in jobs]
        unresolved = [i for i, row in enumerate(results) if row["task"] is None]
        failure = None
        if neural and unresolved:
            try:
                import torch
                from model import batch
                self.load()
                # Experimental neural decoding is explicitly opt-in; never overwrite exact routes.
                with torch.no_grad():
                    for offset in range(0, len(unresolved), 16):
                        indices = unresolved[offset:offset+16]
                        ids, lengths = batch([jobs[i] for i in indices])
                        probabilities = self.heads(self.model.features(ids, lengths)).reshape(-1, 100, 2).softmax(-1)[:, :, 1]
                        values, labels = probabilities.topk(2, dim=1)
                        for j, i in enumerate(indices):
                            name = PROFILES[int(labels[j, 0])]["id"]
                            if (name in self.report["enabled"] and float(values[j, 0]) >= self.report["confidence_threshold"]
                                    and float(values[j, 0]-values[j, 1]) >= self.report["margin_threshold"]):
                                results[i] = {"task": name, "backend": "tiny-gpt", "confidence": round(float(values[j, 0]), 4)}
            except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError, ImportError) as exc:
                failure = type(exc).__name__
        for row in results:
            row["needs_primary_review"] = True
            if row["task"] is None:
                row["backend"] = "primary_agent"
        return {"results": results, "seconds": round(time.monotonic()-start, 4), "fallback_reason": failure}


def serve(decoder, port):
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *args):
            pass  # Do not log user input.

        def do_POST(self):
            try:
                if self.path != "/decode" or self.headers.get("Origin") or self.headers.get("Content-Type") != "application/json":
                    raise ValueError("Only local JSON requests to /decode are accepted")
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= 65536:
                    raise ValueError("Request body exceeds limit")
                self.connection.settimeout(5)
                payload = json.loads(self.rfile.read(length))
                output = decoder.decode(payload["jobs"], neural=payload.get("experimental_neural") is True)
                status = 200
            except (ValueError, KeyError, TypeError, OSError):
                output, status = {"error": "Invalid request", "fallback": "primary_agent"}, 400
            body = json.dumps(output).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    # Sequential handling prevents an unbounded worker/model queue.
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(json.dumps({"listening": f"http://127.0.0.1:{server.server_address[1]}/decode", "profiles": 100}), flush=True)
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["status", "catalog", "decode", "serve"])
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODELS)
    parser.add_argument("--file", type=Path)
    parser.add_argument("--text")
    parser.add_argument("--experimental-neural", action="store_true")
    parser.add_argument("--port", type=int, default=11436)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("Port must be between 0 and 65535")
    decoder = Decoder(args.model_dir)
    try:
        if args.command == "status":
            result = decoder.status()
        elif args.command == "catalog":
            result = [profile["id"] for profile in PROFILES]
        elif args.command == "serve":
            serve(decoder, args.port)
            return 0
        else:
            if (args.text is not None) == (args.file is not None):
                raise ValueError("Use either --text or --file with a JSON array of requests")
            if args.file:
                with args.file.open("rb") as source:
                    raw = source.read(65537)
                if len(raw) > 65536:
                    raise ValueError("Input file exceeds 64 KiB")
                jobs = json.loads(raw)
            else:
                jobs = [args.text]
            result = decoder.decode(jobs, args.experimental_neural)
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"error": str(exc), "fallback": "primary_agent"}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
