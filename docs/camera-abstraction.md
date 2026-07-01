# Camera abstraction & multi-camera

[← back to README](../README.md) · [한국어](camera-abstraction.ko.md)

Upper services (depth processing, etc.) **never** see vendor SDK types. Switching cameras is a config/runtime choice, not a code change.

## The `IDepthCamera` interface

[`camera/interface.py`](../smart-xray-assist/src/xray_assist/camera/interface.py) — the vendor-agnostic contract every adapter implements:

```python
class IDepthCamera(ABC):
    def open(cfg) -> bool
    def close() -> None
    def get_frame(timeout_ms) -> Optional[DepthFrame]   # uint16 HxW
    def get_device_info() -> DeviceInfo
    def is_connected() -> bool
    def usb_speed() -> str                               # USB 2.0 fallback detection
```

`DepthFrame` carries only the raw Z16 array + metadata (width/height/depth_scale/frame_id). The upper layers don't know which vendor produced it.

## Adapter factory

`build_camera(cfg)` in [`camera/service.py`](../smart-xray-assist/src/xray_assist/camera/service.py) maps a provider string → adapter:

| provider | adapter | SDK (optional install) |
|---|---|---|
| `mock` | [`mock_camera.py`](../smart-xray-assist/src/xray_assist/camera/mock_camera.py) | none — synthetic pipeline |
| `realsense` | [`realsense_adapter.py`](../smart-xray-assist/src/xray_assist/camera/realsense_adapter.py) | `pyrealsense2` |
| `orbbec` | [`orbbec_adapter.py`](../smart-xray-assist/src/xray_assist/camera/orbbec_adapter.py) | `pyorbbecsdk` |

**Import guard**: hardware SDKs are only installed on the edge board. Each adapter wraps its SDK import in `try/except`, so a dev machine without the SDK still loads the module cleanly (a clear error is raised only on instantiation).

## Discovery — enumerate real devices per vendor

[`camera/discovery.py`](../smart-xray-assist/src/xray_assist/camera/discovery.py) keeps vendor SDK probing in one place, so the orchestrator, REST, and console all agree on "what cameras exist."

```python
enumerate_all() -> [
  { id, label, available, detail, devices: [{serial, model}, ...] },
  ...
]
```

- `mock` — always available, one synthetic device
- `realsense` — `rs.context().query_devices()` enumerates each connected serial + model
- `orbbec` — `Context().query_devices()` enumerates the same
- SDK missing / no device → `available: false` + reason (`detail`)

**Adding a vendor = one registry entry + one adapter + one `build_camera` branch.**

## Runtime connect & per-serial selection

```
POST /api/v1/devices/connect  { "provider": "...", "serial": "..." }
POST /api/v1/devices/disconnect
GET  /api/v1/devices          → { active:{provider,serial}, connected, providers:[...] }
```

`connect_device(provider, serial)` runs under `_cam_lock`:

1. build a `CameraService` for the new provider/serial and `start()`
2. on failure, log `device_connect_failed` to audit and keep the existing service (graceful)
3. on success, replace the service and update the active `{provider, serial}`

The console's **Settings → Camera** select is populated from `/devices`. When several units of a vendor are attached, each shows as `model · serial — vendor`, and the chosen `provider|serial` connects to exactly that device. Unavailable vendors are shown disabled with their reason.

## Target hardware (design roadmap)

The adapters map onto these evaluated cameras (`en/files/hardware.md`, `camera.md`, `tech-stack-assessment.md`):

| Camera | Sensing | Depth | Link | Notes |
|---|---|---|---|---|
| **Intel RealSense D455** *(MVP)* | Active IR stereo | 1280×720 @ 30 fps, 0.6–6.0 m | USB 3.1 Type-C | wide ecosystem; watch silent USB 2.0 fallback; SDK org moved `IntelRealSense` → `realsenseai` (mid-2025) |
| **Orbbec Femto Mega I** *(installed PoC)* | iToF | 1024×1024 @ 15 fps | PoE, IP65 | ceiling mount, no long-USB limit; Orbbec SDK v2 |
| **Luxonis OAK-D Pro PoE** *(AI-offload PoC)* | active stereo + neural | — | USB 3.0 / PoE | Myriad X 4 TOPS; DepthAI v2→v3 API break (Sept 2025) requires re-validation |

Frame settings by use case (spec): breathing waveform 640×480 @ 30 fps · thickness 640×480–1280×720 @ 15–30 fps · UI downsampled 15–30 fps.

Related: [Architecture & pipeline](architecture.md) · [Hardware & deployment](hardware-and-deployment.md)
