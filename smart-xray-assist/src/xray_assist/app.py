"""Orchestrator: wires camera -> depth -> gating -> recommender -> audit through
the event bus, owns session + safe-state, and applies operator actions.

Phase 1 is a single-process pipeline (tech-stack §10: MVP = FastAPI single
worker + multiprocessing/ZeroMQ). The orchestrator is transport-agnostic: it
talks to services through the EventBus, so a later ZeroMQ/NNG split is a bus
swap, not a rewrite. The system NEVER fires the X-ray — recommendations are
reference-only and gated on operator approval; on any fault it enters safe
state (recommendations disabled) while the manual X-ray workflow is untouched."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Optional

from .audit.logger import AuditLogger
from .camera.interface import CameraConfig
from .camera.service import CameraService
from .common.clock import timestamp_ms
from .common.config import load_yaml
from .common.errors import ErrorEvent, SafeStateError, enters_safe_state
from .common.event_bus import EventBus
from .depth.calibration import CalibrationProfile
from .depth.processor import DepthProcessor, ProcessorConfig
from .exposure.recommender import ExposureRecommender
from .gating.respiration import GatingConfig, RespirationGating

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _new_session_id() -> str:
    # deterministic-ish, human-readable; not security-sensitive
    from datetime import datetime, timezone
    return "sess_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


class Orchestrator:
    def __init__(self, config_dir: str | Path | None = None,
                 camera=None) -> None:
        cfgdir = Path(config_dir) if config_dir else _REPO_ROOT / "configs"
        self.device_cfg = load_yaml(cfgdir / "device.yaml")
        self.camera_cfg_raw = load_yaml(cfgdir / "camera.yaml")
        self.gating_cfg_raw = load_yaml(cfgdir / "gating.yaml")
        self.device_id = self.device_cfg["device"]["id"]
        self.mode = self.device_cfg["device"].get("mode", "operator_assist")

        self.session_id = _new_session_id()
        self.bus = EventBus()
        self.safe_state = False
        self.last_error: Optional[dict] = None
        self.latest: dict[str, Any] = {}        # topic -> last message (for /state, UI)
        self.last_recommendation: Optional[dict] = None
        self._approved_recs: set[str] = set()
        self._rec_seq = 0

        # --- audit ---
        db_path = self.device_cfg["storage"]["database_path"]
        if not Path(db_path).is_absolute():
            db_path = _REPO_ROOT / db_path
        self.audit = AuditLogger(db_path, self.device_id,
                                 migration_sql=_REPO_ROOT / "migrations" / "001_init.sql")

        # --- calibration (signature + presence gate) ---
        self.calib = CalibrationProfile.load(cfgdir / "calib_room_a.json")

        # --- camera ---
        # camera_service can be swapped at runtime (mock <-> real hardware) from
        # the operator console, so the driver thread and the API worker both touch
        # it — guard the reference with a lock.
        self._cam_lock = threading.RLock()
        self._external_camera = camera        # injected mock in tests
        cam_cfg = CameraConfig.from_yaml(self.camera_cfg_raw["camera"])
        self.camera_provider = cam_cfg.provider
        self.camera_serial = cam_cfg.serial
        self.device_connected = True
        self.camera_service = CameraService(
            cam_cfg, self.bus, self.device_id, self.session_id,
            quality_cfg=self.camera_cfg_raw.get("quality", {}), camera=camera)

        # --- depth processor ---
        q = self.camera_cfg_raw.get("quality", {})
        self.body_region = "chest_pa"
        self.patient_mode = "adult"
        self.processor = DepthProcessor(
            self.calib,
            ProcessorConfig(min_valid_pixel_ratio=float(q.get("min_valid_pixel_ratio", 0.85)),
                            min_confidence=float(q.get("min_confidence", 0.80))),
            self.device_id, self.session_id, self.body_region)

        # --- gating ---
        self.gating = RespirationGating(
            GatingConfig.from_yaml(self.gating_cfg_raw["gating"]),
            self.device_id, self.session_id)

        # --- recommender ---
        self.recommender = ExposureRecommender.from_file(
            cfgdir / "exposure_lut.yaml", self.device_id, self.session_id)

        self.camera_service.on_frame = self._on_frame
        self.camera_service.on_error = self._on_error_event

    # --- lifecycle ------------------------------------------------------------

    def start(self) -> None:
        self.camera_service.start()
        self.gating.start_tracking()
        self.audit.append("session", "session_started",
                          {"session_id": self.session_id, "mode": self.mode},
                          session_id=self.session_id)

    def stop(self) -> None:
        self.camera_service.stop()
        self.audit.append("session", "session_ended",
                          {"session_id": self.session_id}, session_id=self.session_id)
        self.audit.close()

    def tick(self, timeout_ms: int = 100) -> Optional[dict]:
        """Pull one frame and run it through the pipeline. Returns the latest
        DepthSummary message, or None on drop/safe-state."""
        with self._cam_lock:
            if not self.device_connected:
                return None                 # console disconnected the camera
            svc = self.camera_service
            frame = svc.poll_once(timeout_ms)
        return self.latest.get("depth.summary") if frame is not None else None

    # --- device management (operator console) ---------------------------------

    def list_devices(self) -> dict[str, Any]:
        """All supported providers and the concrete devices attached to each,
        plus which one is currently active."""
        from .camera import discovery
        return {
            "active": {"provider": self.camera_provider, "serial": self.camera_serial},
            "connected": self.device_connected and self.camera_service.camera.is_connected(),
            "providers": discovery.enumerate_all(),
        }

    def connect_device(self, provider: str = "mock",
                       serial: str = "auto") -> dict[str, Any]:
        """(Re)build the camera service for `provider` and start it. Real hardware
        (realsense) only succeeds on a board with the SDK + a device attached; on
        failure the pipeline stays on its previous camera and an error is returned."""
        provider = (provider or "mock").lower()
        raw = dict(self.camera_cfg_raw["camera"])
        raw["provider"] = provider
        if serial:
            raw["serial"] = serial
        new_cfg = CameraConfig.from_yaml(raw)
        # a real device must be probed fresh, never the injected test mock
        injected = self._external_camera if provider == "mock" else None
        with self._cam_lock:
            old = self.camera_service
            try:
                svc = CameraService(
                    new_cfg, self.bus, self.device_id, self.session_id,
                    quality_cfg=self.camera_cfg_raw.get("quality", {}), camera=injected)
                svc.on_frame = self._on_frame
                svc.on_error = self._on_error_event
                svc.start()
                if not svc.camera.is_connected():
                    raise RuntimeError("camera failed to open")
            except Exception as exc:  # noqa: BLE001
                self.audit.append("device", "device_connect_failed",
                                  {"provider": provider, "error": str(exc)},
                                  severity="warning", session_id=self.session_id)
                return {"status": "error", "provider": provider, "detail": str(exc)}
            # swap in the new service, retire the old one
            try:
                old.stop()
            except Exception:  # noqa: BLE001
                pass
            self.camera_service = svc
            self.camera_provider = provider
            self.device_connected = True
            self.safe_state = False
        info = self.camera_service.camera.get_device_info()
        self.camera_serial = info.serial
        self.audit.append("device", "device_connected",
                          {"provider": provider, "model": info.model,
                           "serial": info.serial}, session_id=self.session_id)
        return {"status": "connected", "provider": provider,
                "device": {"vendor": info.vendor, "model": info.model,
                           "serial": info.serial, "firmware": info.firmware,
                           "usb_speed": self.camera_service.camera.usb_speed()}}

    def disconnect_device(self) -> dict[str, Any]:
        with self._cam_lock:
            self.device_connected = False
            try:
                self.camera_service.stop()
            except Exception:  # noqa: BLE001
                pass
        self.audit.append("device", "device_disconnected",
                          {"provider": self.camera_provider},
                          session_id=self.session_id)
        return {"status": "disconnected", "provider": self.camera_provider}

    # --- pipeline -------------------------------------------------------------

    def _on_frame(self, frame) -> None:
        try:
            summary_obj = self.processor.process(frame)
        except SafeStateError as exc:
            self._enter_safe_state(exc.code, exc.message, module="depth_processor")
            return

        # recovered from a transient fault
        if self.safe_state:
            self._clear_safe_state()

        summary = summary_obj.to_message()
        self.bus.publish("depth.summary", summary)
        self.latest["depth.summary"] = summary

        # gating consumes RAW (full-precision) measurement + the frame capture
        # time, so dt reflects the real frame cadence (not wall-clock jitter).
        # Use mean (over valid, hole-free pixels) as the breathing signal: the
        # median is the hole-robust headline for thickness, but it inherits the
        # sensor's 1mm Z16 quantization (stair-steps that explode d2Z/dt2). The
        # mean of the ~45k dithered ROI pixels is sub-mm smooth and still tracks
        # a cough's full displacement.
        m = summary_obj.measurement
        resp = self.gating.update(
            z_mm=float(m["mean_depth_mm"]),
            valid_pixel_ratio=float(m["valid_pixel_ratio"]),
            now_ms=frame.monotonic_ms,
        ).to_message()
        self.bus.publish("respiration.state", resp)
        self.latest["respiration.state"] = resp

        # recommend only when a stable breath-hold is reached (ready_to_capture)
        if resp["gating"].get("ready_to_capture") and not self.safe_state:
            self._emit_recommendation(float(m["estimated_thickness_mm"]),
                                      summary["quality"]["confidence"])

    def _emit_recommendation(self, thickness_mm: float, confidence: float) -> None:
        rec = self.recommender.recommend(
            thickness_mm, self.body_region, self.patient_mode,
            input_confidence=confidence).to_message()
        self._rec_seq += 1
        rec["recommendation_id"] = f"rec_{self._rec_seq:06d}"
        self.bus.publish("exposure.recommendation", rec)
        self.latest["exposure.recommendation"] = rec
        self.last_recommendation = rec
        self.audit.append("recommendation", "recommendation_generated", rec,
                          actor_id="exposure_recommender", session_id=self.session_id)

    # --- operator actions -----------------------------------------------------

    def operator_action(self, action: str, operator_id: str,
                        payload: Optional[dict] = None) -> dict[str, Any]:
        payload = payload or {}
        from .common.messages import make_operator_action
        evt = make_operator_action(self.device_id, self.session_id, operator_id,
                                   action, payload)
        # audit the action BEFORE it takes effect (api-schema.md)
        audit = self.audit.append("operator_action", action, evt,
                                  actor_type="operator", actor_id=operator_id,
                                  session_id=self.session_id)

        if action == "approve_recommendation":
            rec_id = payload.get("recommendation_id", "")
            self._approved_recs.add(rec_id)
            return {"status": "accepted", "audit_id": audit["audit_id"]}
        if action == "play_breath_cue":
            # issue the breath-hold cue; on the mock camera, simulate a compliant
            # patient holding their breath so the demo reaches stable_breath_hold
            self.gating.request_cue()
            cam = self.camera_service.camera
            if hasattr(cam, "hold_breath"):
                cam.hold_breath = True
            return {"status": "accepted", "audit_id": audit["audit_id"]}
        if action == "switch_manual_mode":
            self.gating.manual_override()
            return {"status": "accepted", "audit_id": audit["audit_id"]}
        if action == "abort":
            self.gating.reset()
            cam = self.camera_service.camera
            if hasattr(cam, "hold_breath"):
                cam.hold_breath = False   # resume breathing
            return {"status": "accepted", "audit_id": audit["audit_id"]}
        if action == "trigger_cough":
            # demo/QA: inject a cough spike on the mock camera so the gating
            # abort path (d²Z/dt²) can be exercised end-to-end with no hardware.
            cam = self.camera_service.camera
            if hasattr(cam, "trigger_cough"):
                cam.trigger_cough()
            return {"status": "accepted", "audit_id": audit["audit_id"]}
        return {"status": "accepted", "audit_id": audit["audit_id"]}

    def is_approved(self, recommendation_id: str) -> bool:
        return recommendation_id in self._approved_recs

    # --- safe state -----------------------------------------------------------

    def _on_error_event(self, evt: dict) -> None:
        if evt.get("safe_state_entered"):
            self.safe_state = True
        self.last_error = evt
        self.audit.append("error", evt["code"], evt, severity=evt.get("severity", "error"),
                          actor_id=evt.get("module", "system"), session_id=self.session_id)

    def _enter_safe_state(self, code: str, message: str, module: str) -> None:
        evt = ErrorEvent(device_id=self.device_id, session_id=self.session_id,
                         code=code, message=message, module=module).to_message()
        self.bus.publish("system.error", evt)
        self.latest["system.error"] = evt
        if enters_safe_state(code):
            self.safe_state = True
        self.last_error = evt
        self.audit.append("error", code, evt, severity="error",
                          actor_id=module, session_id=self.session_id)

    def _clear_safe_state(self) -> None:
        self.safe_state = False

    # --- state snapshot (REST /state, /health) --------------------------------

    def state_snapshot(self) -> dict[str, Any]:
        cam_on = self.device_connected and self.camera_service.camera.is_connected()
        return {
            "session_id": self.session_id,
            "mode": self.mode,
            "camera": "connected" if cam_on else "disconnected",
            "camera_provider": self.camera_provider,
            "calibration": "valid",
            "respiration_state": self.gating.state,
            "safe_state": self.safe_state,
        }

    def health(self, uptime_s: int = 0) -> dict[str, Any]:
        return {
            "status": "ok" if not self.safe_state else "degraded",
            "device_id": self.device_id,
            "uptime_s": uptime_s,
            "services": {
                "camera_service": "ok" if self.camera_service.camera.is_connected() else "down",
                "depth_processor": "ok",
                "respiration_gating": "ok",
                "audit_logger": "ok",
            },
        }
