from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from . import config
from .analysis import active_ms, max_window_insertions

# (t_ms, expected, typed, word_idx)
Keystroke = tuple[float, str, str, int]


class AnalyzeRequest(BaseModel):
    duration_ms: float = Field(ge=0, le=(config.CUSTOM_MAX_SECONDS + 60) * 1000 * 4)
    pauses: list[tuple[float, float]] = Field(default_factory=list, max_length=10_000)
    words: list[str] = Field(max_length=100_000)
    keystrokes: list[Keystroke] = Field(max_length=config.MAX_KEYSTROKES)
    mode: Literal["learn", "speed"] = "learn"
    level: Literal["easy", "medium", "hard"] = "medium"

    @model_validator(mode="after")
    def check_plausible(self) -> "AnalyzeRequest":
        if any(len(w) == 0 or len(w) > 60 for w in self.words):
            raise ValueError("words must be 1-60 characters")
        prev_end = 0.0
        for start, end in self.pauses:
            if start < prev_end or end < start or end > self.duration_ms + 1:
                raise ValueError("pauses must be ordered, non-overlapping and inside the test")
            prev_end = end
        prev_t, prev_idx = 0.0, 0
        for t, expected, typed, idx in self.keystrokes:
            if t < 0 or t < prev_t:
                raise ValueError("keystroke timestamps must be non-negative and non-decreasing")
            if t > self.duration_ms + 1000:
                raise ValueError("keystroke after the end of the test")
            if not 0 <= idx < len(self.words) or idx < prev_idx:
                raise ValueError("word index out of range or going backwards")
            if len(typed) > 1 or len(expected) > 1:
                raise ValueError("one character per keystroke")
            if any(s < t < e for s, e in self.pauses):
                raise ValueError("keystroke recorded during a pause")
            prev_t, prev_idx = t, idx
        act = active_ms(self.duration_ms, self.pauses)
        inserts = sum(1 for k in self.keystrokes if k[2] != "")
        per_10s = config.MAX_SUSTAINED_WPM * 5 / 6  # chars allowed in any 10 s window
        if act >= 5000 and inserts / 5 / (act / 60000) > config.MAX_SUSTAINED_WPM:
            raise ValueError(f"over {config.MAX_SUSTAINED_WPM} WPM sustained is not humanly plausible")
        if max_window_insertions(self.keystrokes, self.pauses) > per_10s:
            raise ValueError(f"over {config.MAX_SUSTAINED_WPM} WPM sustained is not humanly plausible")
        return self


class Point(BaseModel):
    t: float
    wpm: float


class Consistency(BaseModel):
    stdev: float
    score: float


class ProblemKey(BaseModel):
    key: str
    errors: int
    total: int


class Mistyped(BaseModel):
    word: str
    typed: str


class AnalyzeResponse(BaseModel):
    net_wpm: float
    raw_wpm: float
    cpm: float
    accuracy: float
    correct_chars: int
    typed_chars: int
    errors: int
    active_seconds: float
    consistency: Consistency
    series: list[Point]
    problem_keys: list[ProblemKey]
    mistyped_words: list[Mistyped]


class Sense(BaseModel):
    pos: str
    label: str
    meaning: str
    examples: list[str]


class WordRecord(BaseModel):
    id: str
    word: str
    level: str
    ipa: str
    senses: list[Sense]
    forms: list[str] = []
    source: str


class VocabResponse(BaseModel):
    level: str
    seed: int
    cursor: int
    next_cursor: int | None
    total: int
    words: list[WordRecord]
