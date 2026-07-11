# mobile-use-agent

**A self-evolving GUI agent for Android apps — driven by ADB + vision only.**

> [中文说明 (Chinese README)](./README_zh.md)

`mobile-use-agent` scrapes and automates mobile apps that block traditional
accessibility-based automation (uiautomator, appium, xpath, view hierarchy).
It reads the screen the same way a human does — screenshots + OCR — and
learns which paths are worth taking as it runs.

Battle-tested on the notoriously automation-hostile wx client:
14 target chat rooms, deep swipe capture, auto-pin toggle, 24/7 loop.

---

## Why this exists

Most "mobile automation" stacks rely on `uiautomator2`, accessibility trees,
or app-side hooks. All three are dead on apps that ship anti-automation
countermeasures (obfuscated view IDs, dynamic layouts, no exported activities,
hidden accessibility labels).

The one interface that can't be blocked is **pixels on the screen**.
So the entire agent commits to that surface:

- **Only input:** `adb shell screencap` (raw PNG)
- **Only output:** `adb shell input tap / swipe / text / keyevent`
- **Only reasoning primitive:** OCR (`rapidocr_onnxruntime`)

Everything else — target discovery, page identification, dedup, budgeting,
recovery — is derived from those three primitives plus a small memory file.

---

## Technical highlights

### 1. Vision-first navigation
No view hierarchy, no XPaths, no accessibility. Every decision (which row to
tap, whether we entered the right page, when to stop swiping) is grounded in
OCR of the last screenshot. Works even when the target app strips
`android:contentDescription` and reflows its layout across versions.

### 2. Agentic Memory (Agent S2/S3 pattern)
For every target, the agent maintains a rolling window of recent yields
and adapts its swipe budget dynamically:

| recent avg blocks | screens allotted next cycle |
|---|---|
| < 1 (and peak ≤ 2) | 6 |
| < 3 | 12 |
| < 8 | 18 |
| ≥ 8 | 25 (max) |

Quiet targets shrink their footprint; high-signal targets stay fully
covered. Memory persists to disk (`target_memory.json`) — the agent picks
up where it left off across restarts.

### 3. SEAgent-style curriculum fallback
When scroll-based discovery fails ≥ N cycles for the same target,
the agent switches strategy: enters the app's own search UI, types a
learned pinyin/keyword prefix, then OCRs the results page and taps the
row that contains any expected substring. Recovers targets that are
permanently buried below screen-fulls of noise.

### 4. Verified auto-pin (no accessibility)
`AutoPinner` locates the "pin" toggle by OCR label, then samples ~200
pixels around the switch's right-edge coordinates and classifies ON vs OFF
by green-channel dominance vs. neutral grey. Toggles only if OFF. Verifies
state after tap. Works with zero knowledge of the toggle widget's ID.

### 5. Content-hash dedup
Every screen's OCR text is fingerprinted; three consecutive unchanged
fingerprints mean "we've hit the top of the history" and the scroll loop
exits early. Across a cycle, blocks are dedup'd again by hash — so
overlapping search + scroll paths don't double-count.

### 6. Domain-agnostic core
`mobile_use/` has zero business coupling. Callers inject:
- targets (any list of labels)
- relevance predicate (any function `text -> bool`)
- block splitter + hash (any function `text -> list[str]`)
- persistence callback (do whatever you want with the results)

Same core has been used against wx chat groups, wx mini-programs,
and native list apps.

---

## Effect: real numbers from the reference deployment

Deployment: wx on OPPO PEAM00 (1080×2400, Android 12), 14 target
groups, 6-minute loop interval, 24/7 uptime, results persisted to Postgres
via SSH tunnel.

| Milestone | Coverage | Notes |
|---|---|---|
| v0 fixed y-coords | 0 / 14 | tapped wrong groups; hard-coded rows drift |
| v1 OCR row discovery | 12 / 14 | robust to pinned/list order changes |
| v2 typo-fixed target names | 13 / 14 | 6 OCR-derived corrections to target set |
| v3 Agentic Memory | 13 / 14 stable | adaptive budgets, memory persisted |
| v4 SEAgent curriculum | 14 / 14 | recovers group buried below screen-fulls |

Per cycle (v4):
- ~ 30 min wall clock
- ~ 40–100 raw OCR blocks captured
- ~ 50–80 unique blocks after dedup
- 0 human intervention

Screenshots and detailed logs are in `docs/` (chat contents are redacted).

---

## Benchmarks

`mobile-use-agent` was designed for real automation-hostile apps, not for
public benchmark scoreboards. That said, we ran a scoped slice of Google
DeepMind's **AndroidWorld** to have a paper-comparable number.

**Scope:** `OpenAppTaskEval` only — 5 tasks of the 116-task suite. This is
the one AndroidWorld task family whose success criterion (bring the named
package to foreground) can be judged without an LLM planner, so the ADB+OCR
stack is measured directly, no orchestration layer added.

Setup: Pixel 6 emulator, API 33, `google_apis;arm64-v8a`, headless
(`-no-window -no-audio`). See `benchmarks/openapp_smoke.py` for the runner.

| Task | seed 0 | seed 1 | seed 2 | success |
|---|---|---|---|---|
| Open Settings | ✓ | ✓ | ✓ | 3/3 |
| Open Clock | ✓ | ✓ | ✓ | 3/3 |
| Open Contacts | ✓ | ✓ | ✓ | 3/3 |
| Open Camera | ✓ | ✓ | ✓ | 3/3 |
| Open Phone (Dialer) | ✓ | ✓ | ✓ | 3/3 |
| **Overall** | | | | **15/15 (100%)** |

Landscape (**not** run head-to-head; numbers below are from each paper's
own full-116 evaluation with different agent architectures — listed here
only so a reader can locate this scoped subset on the map):

| Agent | Scope | AndroidWorld success |
|---|---|---|
| M3A baseline (Gemini 1.5 Pro) | full 116 | ~30% |
| SeeAct (GPT-4o) | full 116 | ~16% |
| UI-TARS-72B-SFT | full 116 | ~46% |
| **mobile-use-agent (ours)** | **5/116 (OpenApp only)** | **100%** |

Reading the table honestly: the numbers on the same row are not comparable
because the scopes differ. This subset intentionally isolates perception +
tap grounding, which is what this project optimizes for. Tasks that need
LLM-driven multi-step planning (`SimpleCalendarAddOneEvent`,
`RecipeAddSingleRecipe`, etc.) are out of scope for the current codebase
and would score 0 on a full run.

Reproduce:

```bash
# Start emulator with gRPC 8554
emulator -avd Pixel_6_API_33 -no-snapshot -grpc 8554 -no-window

# Then, in the mobile-use-agent repo
python benchmarks/openapp_smoke.py \
    --adb $ANDROID_SDK_ROOT/platform-tools/adb --seeds 3
```

Result JSON: `benchmarks/results/openapp_smoke.json`.

---

## Architecture

```
                  ┌────────────────────────────────────────┐
                  │            ScrapingAgent               │
                  │        (run_cycle harness)             │
                  └──┬───────────────┬──────────────────┬──┘
                     │               │                  │
              ┌──────▼──────┐  ┌─────▼─────┐   ┌────────▼────────┐
              │ ChatListSc- │  │ Group-    │   │ SearchCurricu-  │
              │ anner       │  │ Capturer  │   │ lum  (SEAgent)  │
              │ (OCR list)  │  │ (deep     │   │  fallback route │
              └──────┬──────┘  │  swipe)   │   └────────┬────────┘
                     │         └─────┬─────┘            │
                     │               │                  │
                     │        ┌──────▼──────────────────▼─┐
                     │        │      AgenticMemory        │
                     │        │  (per-target state file)  │
                     │        └──────────────┬────────────┘
                     │                       │
                     └────────┬──────────────┴──────────┐
                              │                         │
                        ┌─────▼─────┐             ┌─────▼─────┐
                        │    ADB    │             │ OcrEngine │
                        │ wrapper   │             │ RapidOCR  │
                        └───────────┘             └───────────┘
```

Each box is a plain Python class with no framework baggage — you can use
any of them in isolation.

---

## Install

```bash
pip install -e .
# also required by the OCR + pin modules:
pip install rapidocr_onnxruntime Pillow
```

Requires the Android platform-tools `adb` binary on your machine and a
device that has USB debugging enabled (or ADB-over-TCP: `adb connect …`).

---

## Quick start

```python
from mobile_use import ADB, OcrEngine, ChatListScanner, GroupCapturer, AgenticMemory, ScrapingAgent

adb = ADB(binary='adb')
ocr = OcrEngine()

scanner = ChatListScanner(ocr, targets={'Alpha List', 'Beta List'})
capturer = GroupCapturer(adb, ocr,
    is_relevant=lambda t: 'expected-marker' in t,
    split_blocks=lambda t: [b for b in t.split('\n\n') if len(b) > 20],
)
memory = AgenticMemory('./target_memory.json')
agent = ScrapingAgent(adb, ocr, scanner, capturer, memory)

result = agent.run_cycle(batch_dir='./batch/2026-07-08')
print(result['covered'], result['missed'])
```

See `examples/wx_group_scraper.py` for a full 24/7 loop with search
curriculum, business persistence, and app-specific entry point wired in.

---

## Redacted demo output

Example log line after a normal cycle (personally-identifying content
replaced with ▓):

```
{"round": 47, "batch": "20260707_142107",
 "covered": ["Alpha List", "Beta List", ..., "Nu List"],
 "missed": [],
 "curriculum_recovered": ["Mu List"],
 "elapsed_sec": 1732.4,
 "inserted_blocks": 63}
```

Screenshot samples (fully redacted) live in `docs/screens/` — every
line of chat text is boxed out; only the UI chrome and pin toggle are
visible, which is enough to verify the automation flow.

---

## Roadmap

- [ ] VeriGUI-style temporal action graph — record trajectories and mine
      recurring subpaths as reusable skills.
- [ ] Multi-device fan-out (one agent, N phones, shared memory).
- [ ] Optional VLM verifier — when OCR is ambiguous (e.g. rare glyphs,
      handwriting), ping a small vision model just for that crop.
- [ ] Web dashboard for live status + memory inspection.

---

## License

MIT — see `LICENSE`.
