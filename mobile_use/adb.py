"""Thin ADB wrapper. Works on Windows (default) and POSIX by pointing `binary`
at the correct adb executable.
"""
from __future__ import annotations
import subprocess
import time
import re
from pathlib import Path
from typing import Optional


class ADB:
    def __init__(self, binary: str = 'adb', serial: Optional[str] = None,
                 default_timeout: int = 60):
        self.binary = binary
        self.serial = serial
        self.default_timeout = default_timeout

    def _prefix(self) -> str:
        b = f'"{self.binary}"'
        return f'{b} -s {self.serial}' if self.serial else b

    def shell(self, cmd: str, timeout: Optional[int] = None) -> str:
        full = f'{self._prefix()} shell {cmd}'
        return subprocess.run(
            full, shell=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout or self.default_timeout,
        ).stdout

    def run(self, cmd: str, timeout: Optional[int] = None) -> str:
        full = f'{self._prefix()} {cmd}'
        return subprocess.run(
            full, shell=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout or self.default_timeout,
        ).stdout

    def screencap(self, out_path: str | Path) -> int:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'wb') as f:
            subprocess.run(
                f'{self._prefix()} exec-out screencap -p',
                shell=True, stdout=f, stderr=subprocess.DEVNULL, timeout=30,
            )
        return p.stat().st_size if p.exists() else 0

    def tap(self, x: int, y: int) -> None:
        self.shell(f'input tap {x} {y}')

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 400) -> None:
        self.shell(f'input swipe {x1} {y1} {x2} {y2} {duration_ms}')

    def key(self, keycode: str) -> None:
        self.shell(f'input keyevent {keycode}')

    def back(self, times: int = 1, delay: float = 0.25) -> None:
        for _ in range(times):
            self.key('KEYCODE_BACK')
            time.sleep(delay)

    def wake(self) -> None:
        self.shell('svc power stayon true')
        self.key('KEYCODE_WAKEUP')
        time.sleep(0.4)
        self.swipe(540, 1900, 540, 400, 350)
        time.sleep(0.4)

    def top_activity(self) -> str:
        out = self.shell('dumpsys activity activities')
        for line in out.splitlines():
            if 'mResumedActivity' in line:
                m = re.search(r'\s+([^\s/]+/[^\s}]+)', line)
                if m:
                    return m.group(1)
        return ''

    def start_activity(self, component: str) -> None:
        self.shell(f'am start -n {component}')

    def force_stop(self, package: str) -> None:
        self.shell(f'am force-stop {package}')

    def input_text(self, text: str) -> None:
        self.shell(f'input text {text}')
