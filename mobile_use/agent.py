"""Outer harness that composes the pieces:
  1. Wake device, open app, scroll list to top
  2. Loop: OCR the list, pick a matching row not yet covered, enter+capture
  3. For persistently-missed targets (miss_streak >= trigger), fall back to
     the SEAgent-style search curriculum
  4. Update agentic memory, dedup blocks, return per-target results

The class is intentionally free of any business logic. Callers supply:
  - `entry_point(agent)`   — do whatever it takes to bring the target list
                              into view (open app, hit tab, scroll to top).
  - `blocks_by_target`     — comes back as {target_name: [blocks, ...]}.

See examples/wx_group_scraper.py for the full stack wired together.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .adb import ADB
from .ocr import OcrEngine
from .chat_list import ChatListScanner
from .group_capture import GroupCapturer
from .memory import AgenticMemory
from .curriculum import SearchCurriculum


@dataclass
class AgentConfig:
    max_iters: int = 40
    empty_streak_stop: int = 3
    scroll_swipe: tuple[int, int, int, int, int] = (540, 1700, 540, 900, 400)
    scroll_dwell: float = 0.6
    row_pause: float = 0.3


class ScrapingAgent:
    def __init__(self, adb: ADB, ocr: OcrEngine,
                 scanner: ChatListScanner,
                 capturer: GroupCapturer,
                 memory: AgenticMemory,
                 curriculum: Optional[SearchCurriculum] = None,
                 entry_point: Optional[Callable[['ScrapingAgent'], None]] = None,
                 config: Optional[AgentConfig] = None):
        self.adb = adb
        self.ocr = ocr
        self.scanner = scanner
        self.capturer = capturer
        self.memory = memory
        self.curriculum = curriculum
        self.entry_point = entry_point
        self.cfg = config or AgentConfig()

    def _scroll(self) -> None:
        x1, y1, x2, y2, ms = self.cfg.scroll_swipe
        self.adb.swipe(x1, y1, x2, y2, ms)
        time.sleep(self.cfg.scroll_dwell)

    def run_cycle(self, batch_dir: Path) -> dict:
        batch_dir = Path(batch_dir)
        batch_dir.mkdir(parents=True, exist_ok=True)
        if self.entry_point:
            self.entry_point(self)

        blocks_by_target: dict[str, list[str]] = {}
        covered: set[str] = set()
        empty_streak = 0

        for it in range(self.cfg.max_iters):
            if len(covered) >= len(self.scanner.targets):
                break
            shot = batch_dir / f'list_{it:02d}.png'
            if self.adb.screencap(shot) < self.capturer.cfg.min_png_bytes:
                self._scroll()
                continue
            pick = self.scanner.find_next(shot, covered)
            if pick is None:
                empty_streak += 1
                if empty_streak >= self.cfg.empty_streak_stop:
                    break
                self._scroll()
                continue
            empty_streak = 0
            target, y, matched_text = pick
            screens = self.memory.budget_screens(target)
            try:
                blocks = self.capturer.tap_and_capture(target, y, batch_dir, screens=screens)
            except Exception as exc:
                blocks = []
                print(f'  capture error on {target}: {exc}', flush=True)
            covered.add(target)
            if blocks:
                blocks_by_target.setdefault(target, []).extend(blocks)
            self.memory.record_hit(target, blocks=len(blocks), y=y,
                                    screens=screens, strategy='scroll')
            time.sleep(self.cfg.row_pause)

        # Curriculum fallback for persistently-missed targets
        curriculum_recovered = []
        if self.curriculum:
            missing = set(self.scanner.targets) - covered
            for target in list(missing):
                streak = self.memory.miss_streak(target)
                if not self.curriculum.should_trigger(target, streak):
                    continue
                safe = self.capturer.safe_name(target)
                if not self.curriculum.try_all(target, batch_dir, safe):
                    continue
                screens = self.memory.budget_screens(target)
                try:
                    blocks = self.capturer.capture_inside(target, batch_dir,
                                                          screens=screens,
                                                          probe_tag='search')
                except Exception as exc:
                    blocks = []
                    print(f'  curriculum capture error on {target}: {exc}', flush=True)
                if not blocks:
                    continue
                blocks_by_target.setdefault(target, []).extend(blocks)
                covered.add(target)
                curriculum_recovered.append(target)
                self.memory.record_hit(target, blocks=len(blocks),
                                        screens=screens, strategy='search')

        # Dedup by content hash
        for name in list(blocks_by_target):
            seen = set()
            unique = []
            for b in blocks_by_target[name]:
                h = self.capturer.content_hash(b)
                if h in seen:
                    continue
                seen.add(h)
                unique.append(b)
            blocks_by_target[name] = unique

        # Record misses
        missing = sorted(set(self.scanner.targets) - covered)
        for t in missing:
            self.memory.record_miss(t)
        self.memory.save()

        return {
            'covered': sorted(covered),
            'missed': missing,
            'curriculum_recovered': curriculum_recovered,
            'blocks_by_target': blocks_by_target,
        }
