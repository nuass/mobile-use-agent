"""End-to-end example: continuously scrape a small set of chat groups.

Everything sensitive (real group names, DB credentials, message content) is
redacted or replaced with generic placeholders. Copy this file, edit the
CONFIG section, and you have a working self-evolving scraper.

Business layer responsibilities (defined here — NOT in the mobile_use pkg):
  - TARGETS               : the set of groups you care about
  - RELEVANCE_HINTS       : words that prove you're really inside a target
  - split_blocks / hash   : how to turn OCR text into logical records
  - persist_blocks(...)   : where to send the deduped output
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import re
import sys
import time
from pathlib import Path

from mobile_use import (
    ADB, OcrEngine, ChatListScanner, GroupCapturer,
    AgenticMemory, SearchCurriculum, ScrapingAgent,
)
from mobile_use.curriculum import SearchStrategy


# ==== CONFIG ==============================================================
ADB_BIN = r'C:\platform-tools\adb.exe'          # path to your adb
DEVICE_SERIAL = None                             # or 'xxxx' if you have >1 device
ROOT = Path(r'D:\scraper-workdir')              # where screenshots + memory live
LOOP_INTERVAL_MIN = 6

TARGETS = {
    # NOTE: replace with the actual list titles you want to visit.
    # The scanner does normalised substring matching, so the strings just
    # have to be recognisable in an OCR pass of the list view.
    'Group A - example',
    'Group B - example',
    'Group C - example',
}

RELEVANCE_HINTS = ('example-keyword-1', 'example-keyword-2')
NEGATIVE_HINTS = ('advertisement', 'file transfer helper')

SEARCH_STRATEGIES = {
    # Optional: teach the curriculum how to reach targets that the scroll
    # discovery keeps missing. Pinyin/keyword prefixes work best.
    'Group A - example': SearchStrategy(
        pinyins=['grouA', 'aexample'],
        fragments=['Group A'],
    ),
}
# ==========================================================================


def is_relevant(text: str) -> bool:
    tl = text.lower()
    if any(neg in tl for neg in NEGATIVE_HINTS):
        return False
    return any(h in text for h in RELEVANCE_HINTS)


def split_blocks(joined: str) -> list[str]:
    # Toy implementation — split on blank lines, keep chunks with useful signal.
    out = []
    for chunk in re.split(r'\n\s*\n', joined):
        chunk = chunk.strip()
        if len(chunk) < 20:
            continue
        out.append(chunk)
    return out


def content_hash(s: str) -> str:
    return hashlib.md5(s.strip()[:400].encode('utf-8', 'ignore')).hexdigest()


def safe_name(s: str) -> str:
    return re.sub(r'[^\w一-鿿]+', '_', s)[:80] or 'target'


async def persist_blocks(blocks_by_target: dict[str, list[str]]) -> dict:
    """Wire this to your database / warehouse. Here we just count."""
    inserted = sum(len(v) for v in blocks_by_target.values())
    return {'inserted_blocks': inserted}


def open_app_and_go_top(agent: ScrapingAgent) -> None:
    """wx-style entry: back-out fully, relaunch, tap chat tab, scroll to top."""
    agent.adb.wake()
    focus = agent.adb.shell('dumpsys window displays')
    if 'com.tencent.mm' not in focus:
        agent.adb.force_stop('com.tencent.mm')
        time.sleep(0.6)
        agent.adb.start_activity('com.tencent.mm/.ui.LauncherUI')
        time.sleep(2.5)
    agent.adb.back(5, delay=0.25)
    agent.adb.start_activity('com.tencent.mm/.ui.LauncherUI')
    time.sleep(1.4)
    agent.adb.tap(135, 2217)
    time.sleep(0.5)
    agent.adb.tap(135, 2217)
    time.sleep(0.6)
    for _ in range(4):
        agent.adb.swipe(540, 500, 540, 1900, 250)
        time.sleep(0.25)


def build_agent() -> ScrapingAgent:
    ROOT.mkdir(parents=True, exist_ok=True)
    adb = ADB(binary=ADB_BIN, serial=DEVICE_SERIAL)
    ocr = OcrEngine()
    scanner = ChatListScanner(ocr, targets=TARGETS)
    capturer = GroupCapturer(
        adb, ocr,
        is_relevant=is_relevant,
        split_blocks=split_blocks,
        content_hash=content_hash,
        safe_name=safe_name,
    )
    memory = AgenticMemory(path=ROOT / 'state' / 'target_memory.json')
    curriculum = SearchCurriculum(adb, ocr, strategies=SEARCH_STRATEGIES)
    return ScrapingAgent(
        adb, ocr, scanner, capturer, memory,
        curriculum=curriculum,
        entry_point=open_app_and_go_top,
    )


async def loop_forever(interval_min: int = LOOP_INTERVAL_MIN):
    agent = build_agent()
    round_no = 0
    while True:
        round_no += 1
        batch_id = time.strftime('%Y%m%d_%H%M%S')
        batch_dir = ROOT / 'photos' / batch_id
        started = time.time()
        result = agent.run_cycle(batch_dir)
        stats = await persist_blocks(result['blocks_by_target'])
        summary = {
            'round': round_no,
            'batch': batch_id,
            'covered': result['covered'],
            'missed': result['missed'],
            'curriculum_recovered': result['curriculum_recovered'],
            'elapsed_sec': round(time.time() - started, 1),
            **stats,
        }
        print(json.dumps(summary, ensure_ascii=False), flush=True)
        await asyncio.sleep(interval_min * 60)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'once':
        agent = build_agent()
        batch_dir = ROOT / 'photos' / time.strftime('%Y%m%d_%H%M%S')
        result = agent.run_cycle(batch_dir)
        print(json.dumps({
            'covered': result['covered'],
            'missed': result['missed'],
            'curriculum_recovered': result['curriculum_recovered'],
            'groups_with_blocks': [k for k, v in result['blocks_by_target'].items() if v],
        }, ensure_ascii=False))
    else:
        asyncio.run(loop_forever())
