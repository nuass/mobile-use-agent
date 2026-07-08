"""SEAgent-style curriculum fallback: when scroll-based discovery keeps
missing a target, try entering it via the app's own search UI.

The caller supplies, per target:
  - a list of pinyin / keyword strings to type (short prefixes work best)
  - a list of Chinese substrings to look for in the result rows

Coordinates for the search icon and input box are UI-specific and passed in
via `SearchUI`. Defaults match a 1080x2400 wx-style chat app.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .adb import ADB
from .ocr import OcrEngine


@dataclass
class SearchUI:
    search_icon: tuple[int, int] = (890, 220)
    search_input: tuple[int, int] = (500, 220)
    result_row_x: int = 400
    header_max_y: int = 260
    network_marker_substrings: tuple[str, ...] = ('搜索网络', '网络结果')
    reset_back_count: int = 5
    launcher_component: str = 'com.tencent.mm/.ui.LauncherUI'
    chat_tab: tuple[int, int] = (135, 2217)
    dwell_open_search: float = 1.0
    dwell_focus_input: float = 0.3
    dwell_after_type: float = 1.3
    dwell_after_tap_row: float = 1.3


@dataclass
class SearchStrategy:
    pinyins: list[str]
    fragments: list[str]


class SearchCurriculum:
    def __init__(self, adb: ADB, ocr: OcrEngine,
                 strategies: dict[str, SearchStrategy],
                 ui: Optional[SearchUI] = None,
                 miss_streak_trigger: int = 3):
        self.adb = adb
        self.ocr = ocr
        self.strategies = strategies
        self.ui = ui or SearchUI()
        self.miss_streak_trigger = miss_streak_trigger

    def should_trigger(self, target: str, miss_streak: int) -> bool:
        return miss_streak >= self.miss_streak_trigger and target in self.strategies

    def enter(self, target: str, pinyin: str, batch_dir: Path,
              safe_name: str) -> bool:
        strat = self.strategies.get(target)
        if not strat:
            return False
        ui = self.ui
        self.adb.back(ui.reset_back_count)
        self.adb.start_activity(ui.launcher_component)
        time.sleep(1.4)
        self.adb.tap(*ui.chat_tab)
        time.sleep(0.6)
        self.adb.tap(*ui.search_icon)
        time.sleep(ui.dwell_open_search)
        self.adb.tap(*ui.search_input)
        time.sleep(ui.dwell_focus_input)
        self.adb.input_text(pinyin)
        time.sleep(ui.dwell_after_type)
        png = batch_dir / f'search_{safe_name}_{pinyin}.png'
        self.adb.screencap(png)
        rows = self.ocr.read(png)
        net_y = None
        for text, _x, y in rows:
            if any(m in text for m in ui.network_marker_substrings):
                net_y = y
                break
        for text, _x, y in rows:
            if y < ui.header_max_y:
                continue
            if net_y is not None and y >= net_y - 20:
                continue
            for frag in strat.fragments:
                if frag in text:
                    self.adb.tap(ui.result_row_x, y)
                    time.sleep(ui.dwell_after_tap_row)
                    return True
        return False

    def try_all(self, target: str, batch_dir: Path, safe_name: str) -> bool:
        strat = self.strategies.get(target)
        if not strat:
            return False
        for py in strat.pinyins:
            if self.enter(target, py, batch_dir, safe_name):
                return True
        return False
