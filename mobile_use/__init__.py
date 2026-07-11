"""mobile-use: an ADB-connected self-evolving GUI agent for mobile apps.

Domain-agnostic building blocks for scraping / automating Android apps
through pure vision (screencap + OCR) — no accessibility, no root, no
private APIs. Designed for apps that block uiautomator (wx and similar).

Modules:
  adb          — thin wrapper around `adb` binary
  ocr          — RapidOCR wrapper returning (text, x, y) rows
  chat_list    — scan a scrollable list, match candidate rows against targets
  group_capture— enter a chat / detail view and capture N screens with dedup
  memory       — Agent S2/S3 style per-target agentic memory
  curriculum   — SEAgent style search-based fallback for persistently-missed targets
  pin          — auto-pin: locate pin toggle by OCR, flip by pixel color check
  vlm          — vision-language model client for OCR miss verification
  agent        — outer loop harness combining the above

The package is business-agnostic. Domain logic (which text counts as a hit,
how to parse blocks, where to persist results) is injected via callbacks.
See examples/wx_group_scraper.py for a redacted end-to-end integration.
"""
from .adb import ADB
from .ocr import OcrEngine
from .chat_list import ChatListScanner
from .group_capture import GroupCapturer
from .memory import AgenticMemory
from .curriculum import SearchCurriculum
from .pin import AutoPinner
from .vlm import VLMClient
from .agent import ScrapingAgent

__all__ = [
    'ADB', 'OcrEngine', 'ChatListScanner', 'GroupCapturer',
    'AgenticMemory', 'SearchCurriculum', 'AutoPinner', 'VLMClient',
    'ScrapingAgent',
]
__version__ = '0.1.0'
