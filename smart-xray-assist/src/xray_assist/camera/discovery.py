"""Camera discovery: enumerate the depth-camera providers this host supports and
the concrete devices attached to each. Keeps vendor SDK probing in one place so
the orchestrator, the REST API and the operator console all agree on what
cameras exist. Every SDK import is guarded — a dev machine with no SDK simply
reports the provider as unavailable instead of crashing."""

from __future__ import annotations

from typing import Any

# Provider registry. Adding a camera vendor = one entry here + an adapter in
# build_camera(). label is shown in the operator console.
PROVIDERS: dict[str, str] = {
    "mock": "Mock depth camera (no-HW)",
    "realsense": "Intel RealSense",
    "orbbec": "Orbbec",
}


def _mock() -> dict[str, Any]:
    return {"available": True, "detail": "synthetic pipeline, always available",
            "devices": [{"serial": "mock-000000001", "model": "D455 (synthetic)"}]}


def _realsense() -> dict[str, Any]:
    try:
        import pyrealsense2 as rs  # type: ignore
    except Exception:  # noqa: BLE001
        return {"available": False, "detail": "pyrealsense2 SDK not installed", "devices": []}
    try:
        devs = rs.context().query_devices()
        out = []
        for d in devs:
            info = rs.camera_info
            out.append({"serial": d.get_info(info.serial_number),
                        "model": d.get_info(info.name)})
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "detail": f"SDK present, probe failed: {exc}", "devices": []}
    if not out:
        return {"available": False, "detail": "SDK present, no RealSense device detected", "devices": []}
    return {"available": True, "detail": f"{len(out)} device(s) detected", "devices": out}


def _orbbec() -> dict[str, Any]:
    try:
        from pyorbbecsdk import Context  # type: ignore
    except Exception:  # noqa: BLE001
        return {"available": False, "detail": "pyorbbecsdk SDK not installed", "devices": []}
    try:
        devlist = Context().query_devices()
        n = devlist.get_count()
        out = []
        for i in range(n):
            di = devlist.get_device_by_index(i).get_device_info()
            out.append({"serial": di.get_serial_number(), "model": di.get_name()})
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "detail": f"SDK present, probe failed: {exc}", "devices": []}
    if not out:
        return {"available": False, "detail": "SDK present, no Orbbec device detected", "devices": []}
    return {"available": True, "detail": f"{len(out)} device(s) detected", "devices": out}


_PROBES = {"mock": _mock, "realsense": _realsense, "orbbec": _orbbec}


def probe(provider: str) -> dict[str, Any]:
    """(available, detail, devices[]) for one provider."""
    fn = _PROBES.get(provider)
    return fn() if fn else {"available": False, "detail": "unknown provider", "devices": []}


def enumerate_all() -> list[dict[str, Any]]:
    """One entry per provider, each with its attached devices."""
    out = []
    for pid, label in PROVIDERS.items():
        p = probe(pid)
        out.append({"id": pid, "label": label, "available": p["available"],
                    "detail": p["detail"], "devices": p["devices"]})
    return out
