"""In-memory vocabulary, loaded once from app/data/*.json."""
from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path

from . import config

DATA = Path(__file__).resolve().parent / "data"


class VocabStore:
    def __init__(self, data_dir: Path = DATA):
        self.levels: dict[str, list[dict]] = {}
        for level in config.LEVELS:
            path = data_dir / f"vocab_{level}.json"
            self.levels[level] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        meta_path = data_dir / "meta.json"
        self.meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    @property
    def total_words(self) -> int:
        return sum(len(v) for v in self.levels.values())

    @property
    def total_sentences(self) -> int:
        return sum(len(s["examples"]) for recs in self.levels.values() for r in recs for s in r["senses"])

    def _order(self, level: str, seed: int) -> list[int]:
        return _permutation(level, seed, len(self.levels[level]))

    def sample(self, level: str, count: int, seed: int, cursor: int, exclude: set[str]) -> tuple[list[dict], int | None, int]:
        """Page through a seed-specific shuffle so one session never repeats a word."""
        recs = self.levels[level]
        order = [i for i in self._order(level, seed) if recs[i]["id"] not in exclude]
        page = [recs[i] for i in order[cursor:cursor + count]]
        nxt = cursor + count if cursor + count < len(order) else None
        return page, nxt, len(order)


@lru_cache(maxsize=256)
def _permutation(level: str, seed: int, n: int) -> list[int]:
    idx = list(range(n))
    random.Random(f"{level}:{seed}").shuffle(idx)
    return idx
