"""Per-target agentic memory (Agent S2/S3 pattern).

For each target we track a small dict:
  {
    "last_y":          int   # last row Y where we found it
    "last_ts":         iso8601
    "last_screens":    int   # screens budget used last time
    "recent_blocks":   [int, ...]   # rolling window of blocks captured
    "miss_streak":     int   # consecutive cycles we failed to find it
    "strategy":        "scroll" | "search"
  }

`budget_screens` picks how many screens to capture next time based on the
recent yield — a quiet group shrinks to 6, a busy group holds at 25. This
compresses total wall-clock while keeping high-signal targets fully covered.
"""
from __future__ import annotations
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class BudgetPolicy:
    max_screens: int = 25
    default_screens: int = 22
    min_recent: int = 2
    keep_window: int = 8


class AgenticMemory:
    def __init__(self, path: str | Path, policy: Optional[BudgetPolicy] = None):
        self.path = Path(path)
        self.policy = policy or BudgetPolicy()
        self._state: dict[str, dict] = {}
        self.load()

    def load(self) -> dict:
        if self.path.exists():
            try:
                self._state = json.loads(self.path.read_text(encoding='utf-8'))
            except Exception:
                self._state = {}
        else:
            self._state = {}
        return self._state

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + '.tmp')
        tmp.write_text(json.dumps(self._state, ensure_ascii=False, indent=2),
                       encoding='utf-8')
        tmp.replace(self.path)

    def get(self, target: str) -> dict:
        return self._state.get(target, {})

    def budget_screens(self, target: str) -> int:
        p = self.policy
        entry = self.get(target)
        if not entry:
            return p.default_screens
        recent = entry.get('recent_blocks', [])
        if len(recent) < p.min_recent:
            return p.default_screens
        tail = recent[-p.keep_window:]
        avg = sum(tail) / len(tail)
        peak = max(tail)
        if avg < 1 and peak <= 2:
            return 6
        if avg < 3:
            return 12
        if avg < 8:
            return 18
        return p.max_screens

    def record_hit(self, target: str, blocks: int, y: Optional[int] = None,
                   screens: Optional[int] = None, strategy: str = 'scroll') -> None:
        entry = dict(self.get(target))
        entry['last_ts'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        if y is not None:
            entry['last_y'] = y
        if screens is not None:
            entry['last_screens'] = screens
        entry['strategy'] = strategy
        recent = list(entry.get('recent_blocks', []))[-(self.policy.keep_window - 1):]
        recent.append(blocks)
        entry['recent_blocks'] = recent
        entry['miss_streak'] = 0
        self._state[target] = entry

    def record_miss(self, target: str) -> int:
        entry = dict(self.get(target))
        entry['miss_streak'] = entry.get('miss_streak', 0) + 1
        entry['last_miss_ts'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        self._state[target] = entry
        return entry['miss_streak']

    def miss_streak(self, target: str) -> int:
        return self.get(target).get('miss_streak', 0)
