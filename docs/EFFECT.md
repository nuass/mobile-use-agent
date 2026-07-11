# Effect notes

Per-target coverage progression on the reference deployment (wx, 14 groups).
All group names and chat contents redacted.

## Cycle-by-cycle coverage (production)

```
cycle  coverage  notes
──────────────────────────────────────────────────────────────
   1    0 / 14   v0 fixed-y prototype tapped wrong rows
   3    5 / 14   discovered typos in target set via OCR of chat list
   5   12 / 14   OCR-based row discovery replaces hard-coded ys
   8   13 / 14   6 target-name typos fixed; 1 group persistently missed
  22   13 / 14   stable; miss_streak on ▓ group climbs to 22
  24   14 / 14   SEAgent search curriculum recovers ▓; miss_streak resets to 0
```

## Adaptive budget effect

Screens allotted per target after 30 cycles:

```
target        recent-avg-blocks  budget
──────────────────────────────────────────
Alpha List             12.3        25
Beta List               6.8        18
Gamma List              1.4        12
Delta List              0.3         6
```

## Cycle time

- Wall clock: ~ 30 min / 14 groups
- Screencap+OCR per screen: ~ 0.9 s
- Per-group swipe budget: 6 → 25 screens (adaptive)
- Idle sleep between cycles: 6 min

## What's in this directory

- `screens/` — redacted screenshots showing the automation flow
  (list view, group entry, pin toggle before/after). Every chat line
  is masked; only UI chrome is visible.
- `memory_sample.json` — synthetic example of the memory file structure.

## AndroidWorld OpenApp smoke (2026-07-08)

Scoped subset benchmark, 5/116 tasks. See `README.md#benchmarks` for full
context and reproduction command. Result JSON:
`benchmarks/results/openapp_smoke.json`.

| Task | seeds | success |
|---|---|---|
| Open Settings | 3 | 3/3 |
| Open Clock | 3 | 3/3 |
| Open Contacts | 3 | 3/3 |
| Open Camera | 3 | 3/3 |
| Open Phone (Dialer) | 3 | 3/3 |
| **Overall** | | **15/15 (100%)** |

Emulator: Pixel 6, API 33, `google_apis;arm64-v8a`, headless.
Judgment: AndroidWorld's own `is_successful` — package on top of the
activity stack after our OCR-driven home→drawer→tap sequence.
