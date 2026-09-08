"""Train and qualify synthetic task decoders locally; never train on user files."""
import argparse
import hashlib
import json
import random
import time
from pathlib import Path

import torch
from torch import nn
from catalog import PROFILES, CHALLENGE, OOD, catalog_digest
from model import TinyGPT, batch, parameter_count, WIDTH

TRAIN_TEMPLATES = ["Find {}", "Locate {}", "Show {}", "Identify {}", "Inspect {}", "Please find {}", "I need {}", "Extract evidence about {}"]
VALID_TEMPLATES = ["Can you point out {} please", "Help me locate evidence for {}"]


def examples(templates):
    return [(template.format(phrase), index) for index, profile in enumerate(PROFILES)
            for phrase in profile["phrases"] for template in templates]


def lexical(text):
    import re
    words = set(re.findall(r"[a-z0-9_]+", text.lower()))
    scores = [max(len(words & set(phrase.split())) / len(set(phrase.split())) for phrase in p["phrases"]) for p in PROFILES]
    return max(range(len(scores)), key=scores.__getitem__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--seconds", type=int, default=240)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output must be a new directory; preserve previous qualification runs")
    if not 1 <= args.steps <= 2000 or not 1 <= args.seconds <= 600:
        parser.error("Training budget exceeds the bounded local experiment")
    torch.set_num_threads(2)
    torch.manual_seed(20260904)
    random.seed(20260904)
    args.output.mkdir(parents=True)
    model = TinyGPT()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.0015)
    rows = examples(TRAIN_TEMPLATES) + [(text, 100) for text in OOD for _ in range(8)]
    ids, lengths = batch([text for text, _ in rows])
    labels = torch.tensor([label for _, label in rows])
    started = time.monotonic()
    def check_budget():
        if time.monotonic() - started > args.seconds:
            raise TimeoutError("Training budget exhausted; no new qualified checkpoint produced")
    completed_steps = 0
    for step in range(args.steps):
        check_budget()
        subset = torch.randint(len(rows), (32,))
        loss = nn.functional.cross_entropy(model(ids[subset], lengths[subset]), labels[subset])
        optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        completed_steps += 1
        if step % 50 == 0:
            print(json.dumps({"step": step, "loss": round(loss.item(), 4), "seconds": round(time.monotonic()-started, 1)}), flush=True)
    model.eval()
    with torch.no_grad():
        chunks = []
        for i in range(0, len(ids), 64):
            check_budget()
            chunks.append(model.features(ids[i:i+64], lengths[i:i+64]))
        features = torch.cat(chunks)
    # Each expert has its own trained two-token head: reject / accept its task.
    heads = nn.Linear(WIDTH, 200)
    optimizer = torch.optim.AdamW(heads.parameters(), lr=0.02)
    targets = (labels[:, None] == torch.arange(100)[None, :]).long()
    for step in range(150):
        check_budget()
        subset = torch.randint(len(rows), (128,))
        logits = heads(features[subset]).reshape(-1, 100, 2)
        losses = nn.functional.cross_entropy(logits.reshape(-1, 2), targets[subset].reshape(-1), reduction="none").reshape(-1, 100)
        weights = torch.where(targets[subset] == 1, 100.0, 1.0)
        loss = (losses * weights).mean()
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    validation = examples(VALID_TEMPLATES)
    by_id = {profile["id"]: i for i, profile in enumerate(PROFILES)}
    challenge = [(text, by_id[target]) for text, target in CHALLENGE]
    # New OOD text is not recycled from the negative training set.
    unknown = ["Compose a song for my dog", "Erase the whole disk now", "Order me some dinner",
               "Upload my private credentials", "Book a hotel in Paris", "Tell me a joke"]
    evaluation = validation + challenge + [(text, 100) for text in unknown]
    eval_ids, eval_lengths = batch([text for text, _ in evaluation])
    with torch.no_grad():
        chunks = []
        for i in range(0, len(eval_ids), 64):
            check_budget()
            chunks.append(model.features(eval_ids[i:i+64], eval_lengths[i:i+64]))
        decoded = torch.cat(chunks)
        probabilities = heads(decoded).reshape(-1, 100, 2).softmax(-1)[:, :, 1]
    scores, indices = probabilities.topk(2, dim=1)
    predictions = [int(indices[i, 0]) if scores[i, 0] >= .95 and scores[i, 0]-scores[i, 1] >= .10 else 100 for i in range(len(evaluation))]
    enabled = []
    specialists = []
    for index, profile in enumerate(PROFILES):
        positive = [i for i, (_, target) in enumerate(evaluation) if target == index]
        correct = sum(predictions[i] == index for i in positive)
        false_positive = sum(pred == index and evaluation[i][1] != index for i, pred in enumerate(predictions))
        passed = correct == len(positive) and false_positive == 0
        if passed:
            enabled.append(profile["id"])
        specialists.append({"id": profile["id"], "positive_cases": len(positive), "correct": correct,
                            "false_positive": false_positive, "enabled": passed})
    state = {key: value for key, value in model.state_dict().items() if not key.startswith("head.")}
    checkpoint = args.output / "decoders.pt"
    check_budget()
    torch.save({"backbone": state, "heads": heads.state_dict()}, checkpoint)
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    def accuracy(offset, count):
        return sum(predictions[i] == evaluation[i][1] for i in range(offset, offset+count)) / count
    report = {"architecture": "causal transformer, 2 layers, width 192, 4 attention heads, 512 hashed word tokens",
              "specialists": 100, "parameters_per_specialist": parameter_count(),
              "shared_backbone": True, "independent_head_parameters": 386,
              "training": "local synthetic request templates; no pretrained language knowledge or private data",
              "steps": completed_steps, "training_seconds": round(time.monotonic()-started, 2),
              "sha256": digest, "catalog_sha256": catalog_digest(), "confidence_threshold": .95, "margin_threshold": .10,
              "enabled": enabled, "template_accuracy": accuracy(0, len(validation)),
              "challenge_accuracy": accuracy(len(validation), len(challenge)),
              "ood_rejection_accuracy": accuracy(len(validation)+len(challenge), len(unknown)),
              "lexical_template_accuracy": sum(lexical(text) == target for text, target in validation)/len(validation),
              "lexical_challenge_accuracy": sum(lexical(text) == target for text, target in challenge)/len(challenge),
              "qualification": specialists,
              "limitations": "Small synthetic evaluation only; not proof of general language understanding or token savings."}
    (args.output / "qualification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key:value for key,value in report.items() if key != "qualification"}), flush=True)


if __name__ == "__main__":
    main()
