#!/usr/bin/env python3
"""Daily empty-bed calibration check (camera.md).

camera.md mandates a daily empty-bed calibration: the script measures the depth
plane of the EMPTY bed (no patient) and checks it is within tolerance of the
stored reference. If it drifts beyond the threshold (camera bumped, table height
changed), the service refuses to publish recommendations and logs
CALIBRATION_DRIFT. Calibration profiles live in configs/calib_*.json and carry a
signature; an unsigned/mismatched profile blocks startup (CALIBRATION_MISSING).

    python scripts/calibrate_empty_bed.py --profile configs/calib_room_a.json
    python scripts/calibrate_empty_bed.py --profile configs/calib_room_a.json --json
    python scripts/calibrate_empty_bed.py --profile configs/calib_room_a.json --write-signature

Maps to GTS-002 (Empty-bed calibration: completes without error, profile signed).
Exit code 0 on PASS, non-zero on drift / error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from xray_assist.camera.interface import CameraConfig  # noqa: E402
from xray_assist.camera.service import build_camera  # noqa: E402
from xray_assist.common.config import compute_signature  # noqa: E402
from xray_assist.common.errors import SafeStateError  # noqa: E402
from xray_assist.depth.calibration import (  # noqa: E402
    DEFAULT_DRIFT_TOLERANCE_MM,
    CalibrationProfile,
)


def measure_bed_plane_mm(provider: str, frames: int) -> float:
    """Capture N empty-bed frames and estimate the bed plane in mm.

    The bed plane is the median of valid (non-zero) depth pixels; raw uint16
    units are converted to mm via depth_scale_m * 1000. Median is robust to the
    chest box and the ~5% depth holes the camera produces."""
    cfg = CameraConfig(provider=provider)
    camera = build_camera(cfg)
    if not camera.open(cfg):
        raise SafeStateError("CAMERA_DISCONNECTED", "camera failed to open")
    try:
        valid: list[np.ndarray] = []
        for _ in range(max(frames, 1)):
            frame = camera.get_frame(timeout_ms=100)
            if frame is None:
                continue
            mm = frame.data.astype(np.float64) * frame.depth_scale_m * 1000.0
            valid.append(mm[frame.data > 0])
        if not valid:
            raise SafeStateError("FRAME_DROP_EXCEEDED",
                                 "no valid frames captured for calibration")
        return float(np.median(np.concatenate(valid)))
    finally:
        camera.close()


def write_signature(path: Path) -> str:
    """Re-sign the profile in place (after an intentional recalibration).

    Recomputes the HMAC over the profile JSON without the signature field, sets
    data["signature"], and writes the file back pretty-printed. Returns the new
    signature string."""
    data = json.loads(path.read_text(encoding="utf-8"))
    payload = json.dumps({k: v for k, v in data.items() if k != "signature"},
                         sort_keys=True, separators=(",", ":")).encode()
    signature = compute_signature(payload)
    data["signature"] = signature
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return signature


def main() -> int:
    ap = argparse.ArgumentParser(description="Daily empty-bed calibration check")
    ap.add_argument("--profile", required=True, help="path to configs/calib_*.json")
    ap.add_argument("--provider", default="mock", help="camera provider (default mock)")
    ap.add_argument("--frames", type=int, default=30, help="frames to average")
    ap.add_argument("--tolerance-mm", type=float, default=DEFAULT_DRIFT_TOLERANCE_MM,
                    help="max allowed drift in mm")
    ap.add_argument("--write-signature", action="store_true",
                    help="re-sign the profile and write it back (after recalibration)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    profile_path = Path(args.profile)

    # Optional re-signing step: do this before loading so the load gate passes.
    if args.write_signature:
        if not profile_path.exists():
            return _fail(args.json, "CALIBRATION_MISSING",
                         f"calibration not found: {profile_path}")
        signature = write_signature(profile_path)
        if not args.json:
            print(f"[calibrate] re-signed {profile_path}")
            print(f"[calibrate] new signature: {signature}")

    # Load + signature gate. A missing/invalid profile is a clean error, not a
    # traceback (CALIBRATION_MISSING -> safe state).
    try:
        profile = CalibrationProfile.load(profile_path)
    except SafeStateError as exc:
        return _fail(args.json, exc.code, exc.message)

    # Capture the empty bed and compare against the stored reference.
    try:
        measured = measure_bed_plane_mm(args.provider, args.frames)
    except SafeStateError as exc:
        return _fail(args.json, exc.code, exc.message)

    delta = measured - profile.bed_origin_mm

    # check_drift raises CALIBRATION_DRIFT past tolerance; catch it to report
    # cleanly instead of crashing.
    drift_code: str | None = None
    drift_msg: str | None = None
    try:
        profile.check_drift(measured, args.tolerance_mm)
    except SafeStateError as exc:
        drift_code = exc.code
        drift_msg = exc.message

    passed = drift_code is None
    if args.json:
        print(json.dumps({
            "result": "PASS" if passed else "FAIL",
            "profile_id": profile.profile_id,
            "provider": args.provider,
            "frames": args.frames,
            "measured_bed_mm": round(measured, 2),
            "reference_bed_origin_mm": profile.bed_origin_mm,
            "delta_mm": round(delta, 2),
            "tolerance_mm": args.tolerance_mm,
            "signed": True,  # load() already verified the signature
            "code": drift_code,
            "message": drift_msg,
        }))
    else:
        print(f"[calibrate] profile        : {profile.profile_id}")
        print(f"[calibrate] signed         : OK (signature verified on load)")
        print(f"[calibrate] provider       : {args.provider} ({args.frames} frames)")
        print(f"[calibrate] measured bed   : {measured:.2f} mm")
        print(f"[calibrate] reference bed  : {profile.bed_origin_mm:.2f} mm")
        print(f"[calibrate] delta          : {delta:+.2f} mm (tol +/-{args.tolerance_mm} mm)")
        if passed:
            print("[calibrate] RESULT         : PASS")
        else:
            print(f"[calibrate] {drift_code}: {drift_msg}")
            print("[calibrate] RESULT         : FAIL")

    return 0 if passed else 1


def _fail(as_json: bool, code: str, message: str) -> int:
    """Report a clean error (no traceback) and return a non-zero exit code."""
    if as_json:
        print(json.dumps({"result": "FAIL", "code": code, "message": message}))
    else:
        print(f"[calibrate] {code}: {message}")
        print("[calibrate] RESULT         : FAIL")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
