"""Enter a target row, capture N screens while swiping, dedup by content hash.

Business plugs in:
  - `is_relevant`   — reject the screen if it's the wrong context (verifies we
                      really did enter the target, not a look-alike)
  - `split_blocks`  — turn accumulated OCR text into logical records
  - `content_hash`  — dedup key (e.g. hash of first N chars of a block)
  - `safe_name`     — filesystem-safe name for the target label
"""
from __future__ import annotations
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .adb import ADB
from .ocr import OcrEngine


def _default_hash(s: str) -> str:
    import hashlib
    return hashlib.md5(s.strip().encode('utf-8', 'ignore')).hexdigest()


def _default_safe_name(s: str) -> str:
    return re.sub(r'[^\w一-鿿]+', '_', s)[:80] or 'target'


@dataclass
class CaptureConfig:
    min_png_bytes: int = 20000
    swipe_from: tuple[int, int] = (540, 700)
    swipe_to: tuple[int, int] = (540, 2000)
    swipe_ms: int = 650
    swipe_dwell: float = 0.5
    unchanged_break: int = 3
    tap_dwell: float = 1.2
    back_dwell: float = 0.5


class GroupCapturer:
    def __init__(self, adb: ADB, ocr: OcrEngine,
                 is_relevant: Callable[[str], bool] = lambda _: True,
                 split_blocks: Callable[[str], list[str]] = lambda t: [t] if t else [],
                 content_hash: Callable[[str], str] = _default_hash,
                 safe_name: Callable[[str], str] = _default_safe_name,
                 config: Optional[CaptureConfig] = None):
        self.adb = adb
        self.ocr = ocr
        self.is_relevant = is_relevant
        self.split_blocks = split_blocks
        self.content_hash = content_hash
        self.safe_name = safe_name
        self.cfg = config or CaptureConfig()

    def tap_and_capture(self, target: str, y: int, batch_dir: Path,
                        screens: int = 25) -> list[str]:
        self.adb.tap(540, y)
        time.sleep(self.cfg.tap_dwell)
        return self.capture_inside(target, batch_dir, screens, probe_tag=f'y{y}')

    def capture_inside(self, target: str, batch_dir: Path, screens: int,
                       probe_tag: str = 'in') -> list[str]:
        cfg = self.cfg
        tag = self.safe_name(target)
        probe_path = batch_dir / f'probe_{tag}_{probe_tag}.png'
        if self.adb.screencap(probe_path) < cfg.min_png_bytes:
            return []
        probe_text = self.ocr.read_text(probe_path)
        if not self.is_relevant(probe_text):
            self.adb.back()
            return []

        group_dir = batch_dir / tag
        group_dir.mkdir(parents=True, exist_ok=True)
        texts: list[str] = []
        seen: set[str] = set()
        unchanged = 0
        for i in range(screens):
            shot = group_dir / f'{i:03d}.png'
            if self.adb.screencap(shot) < cfg.min_png_bytes:
                continue
            text = self.ocr.read_text(shot)
            (group_dir / f'{i:03d}.txt').write_text(text, encoding='utf-8')
            fp = self.content_hash(text)
            if fp in seen:
                unchanged += 1
                if unchanged >= cfg.unchanged_break:
                    break
            else:
                seen.add(fp)
                texts.append(text)
                unchanged = 0
            x1, y1 = cfg.swipe_from
            x2, y2 = cfg.swipe_to
            self.adb.swipe(x1, y1, x2, y2, cfg.swipe_ms)
            time.sleep(cfg.swipe_dwell)

        self.adb.back()
        time.sleep(cfg.back_dwell)
        joined = '\n'.join(texts)
        (group_dir / '_joined.txt').write_text(joined, encoding='utf-8')
        blocks = self.split_blocks(joined)
        return blocks
