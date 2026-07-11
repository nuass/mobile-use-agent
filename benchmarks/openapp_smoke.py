"""AndroidWorld OpenAppTaskEval smoke bench for mobile-use-agent.

Scope: only ``OpenAppTaskEval`` (5 app_names). Purpose is to prove the ADB+OCR
stack can open a named app on Pixel 6 API 33 emulator, and to have a first
paper-comparable number for the anti-automation-oriented mobile-use-agent.

This is NOT a scored submission on full AndroidWorld (116 tasks). See README
"Benchmarks" section for scope and rationale.

Run:
    python benchmarks/openapp_smoke.py \\
        --adb $ANDROID_SDK_ROOT/platform-tools/adb \\
        --console-port 5554 --grpc-port 8554 --seeds 3

Env prep:
    emulator -avd Pixel_6_API_33 -no-snapshot -grpc 8554
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from android_world.env import env_launcher
from android_world.task_evals.single import system as aw_system

from mobile_use.adb import ADB
from mobile_use.ocr import OcrEngine


# App drawer label the user sees, per Pixel 6 API 33 launcher.
APP_LABEL = {
    "settings": "Settings",
    "clock": "Clock",
    "contacts": "Contacts",
    "camera": "Camera",
    "dialer": "Phone",
}


def _open_app_via_ocr(adb: ADB, ocr: OcrEngine, label: str, tmp: Path) -> bool:
    """Home -> open app drawer -> OCR the label -> tap. Returns True on tap issued."""
    adb.key("KEYCODE_HOME")
    time.sleep(0.6)
    # Pixel launcher: swipe up from bottom to open drawer.
    adb.swipe(540, 2200, 540, 800, 350)
    time.sleep(1.0)

    for attempt in range(4):
        shot = tmp / f"drawer_{attempt}.png"
        adb.screencap(shot)
        hit = None
        for text, cx, cy in ocr.read(shot):
            if text.lower() == label.lower():
                hit = (cx, cy)
                break
        if hit is not None:
            adb.tap(hit[0], hit[1])
            time.sleep(1.5)
            return True
        # Not found on this page — scroll down inside the drawer.
        adb.swipe(540, 1800, 540, 900, 350)
        time.sleep(0.6)
    return False


def run_one(env, task_cls, app_name: str, adb: ADB, ocr: OcrEngine, tmp: Path) -> dict:
    task = task_cls({"app_name": app_name})
    task.initialize_task(env)
    label = APP_LABEL[app_name]
    tapped = _open_app_via_ocr(adb, ocr, label, tmp)
    # Give the launched activity a moment to become resumed.
    time.sleep(1.5)
    score = float(task.is_successful(env))
    try:
        task.tear_down(env)
    except Exception:  # noqa: BLE001
        pass
    return {"app": app_name, "label": label, "tapped": tapped, "score": score}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adb", required=True, help="Path to adb binary.")
    ap.add_argument("--console-port", type=int, default=5554)
    ap.add_argument("--grpc-port", type=int, default=8554)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--out", default="benchmarks/results/openapp_smoke.json")
    ap.add_argument("--tmp", default="benchmarks/_scratch")
    ap.add_argument("--emulator-setup", action="store_true",
                    help="Run android_world's first-time app install.")
    args = ap.parse_args()

    tmp = Path(args.tmp)
    tmp.mkdir(parents=True, exist_ok=True)

    env = env_launcher.load_and_setup_env(
        console_port=args.console_port,
        emulator_setup=args.emulator_setup,
        freeze_datetime=True,
        adb_path=args.adb,
        grpc_port=args.grpc_port,
    )

    adb = ADB(binary=args.adb, serial=f"emulator-{args.console_port}")
    ocr = OcrEngine()

    runs: list[dict] = []
    for seed in range(args.seeds):
        for app in APP_LABEL:
            r = run_one(env, aw_system.OpenAppTaskEval, app, adb, ocr, tmp)
            r["seed"] = seed
            runs.append(r)
            print(f"[seed={seed}] {app}: score={r['score']} tapped={r['tapped']}")

    # Aggregate: per-app success = mean over seeds; overall = mean over all runs.
    per_app: dict[str, float] = {}
    for app in APP_LABEL:
        scores = [r["score"] for r in runs if r["app"] == app]
        per_app[app] = sum(scores) / len(scores) if scores else 0.0
    overall = sum(r["score"] for r in runs) / len(runs) if runs else 0.0

    result = {
        "scope": "AndroidWorld OpenAppTaskEval only, 5/116 tasks",
        "device": "Pixel 6 emulator API 33 google_apis arm64-v8a",
        "seeds": args.seeds,
        "per_app_success": per_app,
        "overall_success": overall,
        "runs": runs,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(f"\nOverall: {overall:.2%} — wrote {out}")


if __name__ == "__main__":
    main()
