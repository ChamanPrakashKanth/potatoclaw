"""Causal tiny-GPT backbone plus independent binary specialist heads.

Each instantiated specialist contains 994,946 parameters. Backbone storage is
shared; heads differ. This is a task decoder, not a pretrained general LLM.
"""
import hashlib
import re
import torch
from torch import nn

WIDTH, CONTEXT, VOCAB = 192, 32, 512


def encode(text):
    words = re.findall(r"[a-z0-9_]+", text.lower())
    if not words or len(words) > CONTEXT - 1 or len(text.encode("utf-8")) > 1000:
        raise ValueError("Request must contain 1-31 words and at most 1000 UTF-8 bytes")
    ids = [2 + int.from_bytes(hashlib.blake2s(word.encode(), digest_size=4).digest(), "little") % (VOCAB - 2) for word in words]
    return ids + [1]  # Read-out token attends only to the request before it.


def batch(texts):
    tokens = [encode(text) for text in texts]
    lengths = torch.tensor([len(row) - 1 for row in tokens])
    ids = torch.zeros((len(tokens), max(map(len, tokens))), dtype=torch.long)
    for i, row in enumerate(tokens):
        ids[i, :len(row)] = torch.tensor(row)
    return ids, lengths


class Block(nn.Module):
    def __init__(self):
        super().__init__()
        self.norm1 = nn.LayerNorm(WIDTH)
        self.attention = nn.MultiheadAttention(WIDTH, 4, batch_first=True)
        self.norm2 = nn.LayerNorm(WIDTH)
        self.mlp = nn.Sequential(nn.Linear(WIDTH, 4 * WIDTH), nn.GELU(), nn.Linear(4 * WIDTH, WIDTH))

    def forward(self, x):
        normalized = self.norm1(x)
        mask = torch.ones((x.size(1), x.size(1)), device=x.device, dtype=torch.bool).triu(1)
        x = x + self.attention(normalized, normalized, normalized, attn_mask=mask, need_weights=False)[0]
        return x + self.mlp(self.norm2(x))


class TinyGPT(nn.Module):
    def __init__(self, outputs=101):
        super().__init__()
        self.tokens = nn.Embedding(VOCAB, WIDTH)
        self.positions = nn.Embedding(CONTEXT, WIDTH)
        self.blocks = nn.Sequential(Block(), Block())
        self.norm = nn.LayerNorm(WIDTH)
        self.head = nn.Linear(WIDTH, outputs)

    def features(self, ids, lengths):
        x = self.tokens(ids) + self.positions(torch.arange(ids.size(1), device=ids.device))
        x = self.norm(self.blocks(x))
        return x[torch.arange(len(ids), device=ids.device), lengths]

    def forward(self, ids, lengths):
        return self.head(self.features(ids, lengths))


def parameter_count(outputs=2):
    return sum(p.numel() for p in TinyGPT(outputs).parameters())
