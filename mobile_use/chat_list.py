"""Scan a scrollable list view and match rows against target labels.

Assumes a portrait phone where rows have avatars on the left and metadata
on the right. Only reads rows whose OCR center-x is small enough to be a
title (not a timestamp). Row bounds are configurable so the same scanner
works for any Chinese/English list UI.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Iterable, Optional
from pathlib import Path

from .ocr import OcrEngine


def default_norm(s: str) -> str:
    return (s.replace(' ', '').replace('　', '')
             .replace('（', '(').replace('）', ')')
             .replace('，', ',').replace('、', ','))


@dataclass
class ScannerConfig:
    y_min: int = 280
    y_max: int = 2180
    max_title_x: int = 800
    min_match_len: int = 4


class ChatListScanner:
    def __init__(self, ocr: OcrEngine, targets: Iterable[str],
                 config: Optional[ScannerConfig] = None,
                 normalize: Callable[[str], str] = default_norm):
        self.ocr = ocr
        self.targets = list(targets)
        self.config = config or ScannerConfig()
        self.normalize = normalize
        self._norm_targets = {self.normalize(t): t for t in self.targets}

    def rows(self, screenshot: str | Path) -> list[tuple[str, int]]:
        cfg = self.config
        out = []
        for text, xc, yc in self.ocr.read(screenshot):
            if yc < cfg.y_min or yc > cfg.y_max:
                continue
            if xc > cfg.max_title_x:
                continue
            out.append((text, yc))
        return out

    def match(self, text: str) -> Optional[str]:
        comp = self.normalize(text)
        if len(comp) < self.config.min_match_len:
            return None
        for key, original in self._norm_targets.items():
            if not key:
                continue
            if key in comp:
                return original
            if len(comp) >= 5 and comp in key:
                return original
        return None

    def find_next(self, screenshot: str | Path, exclude: set[str]) -> Optional[tuple[str, int, str]]:
        for text, y in self.rows(screenshot):
            hit = self.match(text)
            if hit and hit not in exclude:
                return hit, y, text
        return None
