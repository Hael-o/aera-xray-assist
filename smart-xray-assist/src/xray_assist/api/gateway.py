"""api_gateway: REST + WebSocket for the operator UI (api-schema.md §Local REST
API / §WebSocket Events). FastAPI single worker (tech-stack §10 MVP). Local
only — never reaches an external network.

The gateway is a thin shell over the Orchestrator. It pushes pipeline events to
connected UIs over WebSocket and exposes health/state/session/approval REST."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..app import Orchestrator
from ..common.clock import monotonic_ms

WS_TOPICS = ("depth.summary", "respiration.state", "exposure.recommendation", "system.error")


class StartSessionBody(BaseModel):
    body_region: str = "chest_pa"
    patient_mode: str = "adult"


class DeviceConnectBody(BaseModel):
    provider: str = "mock"
    serial: str = "auto"


class ApproveBody(BaseModel):
    session_id: str
    recommendation_id: str
    operator_id: str


class ActionBody(BaseModel):
    session_id: str
    operator_id: str
    action: str
    payload: dict[str, Any] = {}


class WSManager:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self) -> None:
        self._loop = asyncio.get_event_loop()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def _send(self, message: dict) -> None:
        dead = []
        for ws in list(self._clients):
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def publish_threadsafe(self, message: dict) -> None:
        """Called from the pipeline (possibly another thread)."""
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._send(message), self._loop)


def create_app(orch: Orchestrator) -> FastAPI:
    app = FastAPI(title="Smart X-ray Assist API", version="1.0.0")
    ws_mgr = WSManager()
    start_mono = monotonic_ms()

    # bridge bus -> websocket
    for topic in WS_TOPICS:
        orch.bus.subscribe(topic, ws_mgr.publish_threadsafe)

    @app.on_event("startup")
    async def _startup() -> None:  # noqa: D401
        ws_mgr.bind_loop()

    @app.get("/api/v1/health")
    def health() -> dict:
        uptime = int((monotonic_ms() - start_mono) / 1000)
        return orch.health(uptime_s=uptime)

    @app.get("/api/v1/state")
    def state() -> dict:
        return orch.state_snapshot()

    @app.post("/api/v1/sessions")
    def start_session(body: StartSessionBody) -> dict:
        orch.body_region = body.body_region
        orch.patient_mode = body.patient_mode
        orch.processor.body_region = body.body_region
        orch.gating.start_tracking()
        return {"session_id": orch.session_id, "status": "started"}

    @app.get("/api/v1/devices")
    def devices() -> dict:
        return orch.list_devices()

    @app.post("/api/v1/devices/connect")
    def device_connect(body: DeviceConnectBody) -> dict:
        return orch.connect_device(body.provider, body.serial)

    @app.post("/api/v1/devices/disconnect")
    def device_disconnect() -> dict:
        return orch.disconnect_device()

    @app.get("/api/v1/audit")
    def audit_log(limit: int = 60) -> dict:
        return {"entries": orch.audit.recent(limit)}

    @app.get("/api/v1/audit/verify")
    def audit_verify() -> dict:
        return {"ok": orch.audit.verify_chain(), "count": orch.audit._count()}

    @app.post("/api/v1/operator/approve")
    def approve(body: ApproveBody) -> dict:
        return orch.operator_action(
            "approve_recommendation", body.operator_id,
            {"recommendation_id": body.recommendation_id})

    @app.post("/api/v1/operator/action")
    def action(body: ActionBody) -> dict:
        return orch.operator_action(body.action, body.operator_id, body.payload)

    @app.websocket("/ws/v1/events")
    async def events(ws: WebSocket) -> None:
        await ws_mgr.connect(ws)
        # push current snapshot immediately so a reconnecting UI rebuilds state
        for topic in WS_TOPICS:
            if topic in orch.latest:
                await ws.send_json(orch.latest[topic])
        try:
            while True:
                # honor subscribe message / ping-pong; we broadcast all topics
                await ws.receive_text()
        except WebSocketDisconnect:
            ws_mgr.disconnect(ws)
        except Exception:  # noqa: BLE001
            ws_mgr.disconnect(ws)

    return app
