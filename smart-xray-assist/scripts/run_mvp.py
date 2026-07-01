#!/usr/bin/env python3
"""Phase 1 MVP entrypoint. Boots the orchestrator (mock camera by default),
starts the FastAPI gateway, and drives the pipeline in a background thread.

    python scripts/run_mvp.py            # serve API + UI on :8080, drive mock camera
    python scripts/run_mvp.py --headless # no HTTP server, just print pipeline state

Open the operator console at http://localhost:8080/ once running.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from xray_assist.app import Orchestrator  # noqa: E402


def _drive(orch: Orchestrator, stop: threading.Event, fps: int) -> None:
    period = 1.0 / max(fps, 1)
    while not stop.is_set():
        orch.tick(timeout_ms=int(period * 1000))
        time.sleep(period)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--headless", action="store_true", help="no HTTP server")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--seconds", type=float, default=0, help="headless run duration (0=forever)")
    args = ap.parse_args()

    orch = Orchestrator()
    orch.start()
    print(f"[run_mvp] device={orch.device_id} session={orch.session_id} "
          f"camera={orch.camera_cfg_raw['camera']['provider']}")

    stop = threading.Event()
    driver = threading.Thread(target=_drive, args=(orch, stop, args.fps), daemon=True)
    driver.start()

    if args.headless:
        try:
            t0 = time.monotonic()
            while args.seconds == 0 or time.monotonic() - t0 < args.seconds:
                time.sleep(1.0)
                s = orch.state_snapshot()
                rec = orch.last_recommendation
                kvp = rec["recommendation"]["kvp"] if rec else None
                print(f"[state] resp={s['respiration_state']:<18} "
                      f"safe={s['safe_state']} last_kvp={kvp}")
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()
            orch.stop()
        return 0

    import uvicorn
    from xray_assist.api.gateway import create_app
    app = create_app(orch)

    # serve the redesigned operator console (AERA PACS) at /.
    # Single source of truth is the redesigned artifact at the repo root; the
    # legacy console lives at ui/operator-console/index.html.
    from fastapi.responses import FileResponse

    _CONSOLE = _ROOT.parent / "index.html"
    if not _CONSOLE.exists():
        _CONSOLE = _ROOT / "ui" / "operator-console" / "index.html"

    @app.get("/")
    def index() -> FileResponse:  # noqa: D401
        return FileResponse(str(_CONSOLE))

    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    finally:
        stop.set()
        orch.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
