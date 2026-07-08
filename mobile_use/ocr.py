"""OCR facade over RapidOCR. Returns simple (text, x_center, y_center) tuples.

Kept intentionally minimal — the whole point of this project is that vision
is the interface, so this file must never leak backend specifics.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional


class OcrEngine:
    def __init__(self):
        self._engine = None

    def _ensure(self):
        if self._engine is None:
            from rapidocr_onnxruntime import RapidOCR
            self._engine = RapidOCR()
        return self._engine

    def read(self, image_path: str | Path) -> list[tuple[str, int, int]]:
        eng = self._ensure()
        result, _ = eng(str(image_path))
        if not result:
            return []
        rows = []
        for item in result:
            box, text, _score = item[0], item[1], item[2]
            xs = [pt[0] for pt in box]
            ys = [pt[1] for pt in box]
            rows.append((text.strip(), int(sum(xs) / 4), int(sum(ys) / 4)))
        return rows

    def read_text(self, image_path: str | Path) -> str:
        return '\n'.join(t for t, _, _ in self.read(image_path))
