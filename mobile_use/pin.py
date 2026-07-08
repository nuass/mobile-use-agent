"""Auto-pin (or toggle any boolean switch) by OCR-locating the label row,
then sampling pixels around the right edge to distinguish ON vs OFF.

This works when native accessibility APIs are blocked — we treat the switch
purely as pixels. Green-dominant pixels near the row's Y indicate ON; grey
pixels indicate OFF. Tuned for WeChat's teal ON color but the thresholds
are configurable.
"""
from __future__ import annotations
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .adb import ADB
from .ocr import OcrEngine


@dataclass
class SwitchScanConfig:
    switch_x_center: int = 990
    dx_range: tuple[int, int, int] = (-45, 50, 4)   # start, stop, step
    dy_range: tuple[int, int, int] = (-22, 24, 4)
    on_g_over_r: int = 15
    on_g_over_b: int = 5
    on_min_g: int = 90
    off_channel_tol: int = 25
    off_min_g: int = 140
    off_max_g: int = 235


@dataclass
class PinConfig:
    label_substrings: tuple[str, ...] = ('置顶', '顶聊天')
    row_tap_x: int = 1000
    open_info_tap: tuple[int, int] = (1000, 220)
    open_info_dwell: float = 1.3
    toggle_dwell: float = 0.8
    scan: SwitchScanConfig = None

    def __post_init__(self):
        if self.scan is None:
            self.scan = SwitchScanConfig()


class AutoPinner:
    def __init__(self, adb: ADB, ocr: OcrEngine,
                 info_activity_keywords: tuple[str, ...] = ('ChatroomInfoUI', 'ChatInfoUI'),
                 config: Optional[PinConfig] = None):
        self.adb = adb
        self.ocr = ocr
        self.info_keywords = info_activity_keywords
        self.cfg = config or PinConfig()

    def find_row_y(self, screenshot: str | Path) -> Optional[int]:
        for text, _x, y in self.ocr.read(screenshot):
            for kw in self.cfg.label_substrings:
                if kw in text:
                    return y
        return None

    def is_on(self, screenshot: str | Path, row_y: int) -> bool:
        from PIL import Image
        im = Image.open(screenshot).convert('RGB')
        s = self.cfg.scan
        on_count = 0
        off_count = 0
        for dx in range(*s.dx_range):
            for dy in range(*s.dy_range):
                x = min(max(s.switch_x_center + dx, 0), im.width - 1)
                y = min(max(row_y + dy, 0), im.height - 1)
                r, g, b = im.getpixel((x, y))
                if g > r + s.on_g_over_r and g > b + s.on_g_over_b and g > s.on_min_g:
                    on_count += 1
                elif abs(r - g) < s.off_channel_tol and abs(g - b) < s.off_channel_tol \
                        and s.off_min_g < g < s.off_max_g:
                    off_count += 1
        return on_count > off_count

    def pin(self, capture: Callable[[str], Path], tag: str,
            scroll_if_missing: bool = True) -> tuple[bool, str]:
        """Assumes we're already on ChattingUI. Opens the group's info page,
        finds the pin row, toggles it if OFF. Returns (ok, status).
        `capture(tag)` should screencap and return the resulting path.
        """
        self.adb.tap(*self.cfg.open_info_tap)
        time.sleep(self.cfg.open_info_dwell)
        act = self.adb.top_activity()
        if not any(k in act for k in self.info_keywords):
            self.adb.back()
            return False, f'info-page-not-open ({act})'

        info_png = capture(f'{tag}_info_before')
        row_y = self.find_row_y(info_png)
        if row_y is None and scroll_if_missing:
            self.adb.swipe(500, 1500, 500, 800, 300)
            time.sleep(0.7)
            info_png = capture(f'{tag}_info_scrolled')
            row_y = self.find_row_y(info_png)
        if row_y is None:
            self.adb.back(3, delay=0.3)
            return False, 'label-not-found'

        if self.is_on(info_png, row_y):
            self.adb.back(3, delay=0.3)
            return True, 'already-on'

        self.adb.tap(self.cfg.row_tap_x, row_y)
        time.sleep(self.cfg.toggle_dwell)
        after = capture(f'{tag}_info_after')
        row_y2 = self.find_row_y(after) or row_y
        ok = self.is_on(after, row_y2)
        self.adb.back(3, delay=0.3)
        return (ok, 'toggled-on' if ok else 'toggle-uncertain')
