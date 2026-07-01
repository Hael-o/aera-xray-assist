# Camera Guide

Picking a depth camera for a hospital X-ray room is less about raw megapixels and more about whether it still works reliably after 8 hours on a ceiling mount. This doc covers the selection rationale, how to wire each camera up, SDK installation quirks, the Depth processing pipeline, and calibration.

---

## Camera Selection

### The Short Version

| Stage | Camera | Connection | Board |
|-------|--------|------------|-------|
| MVP | Intel RealSense D455 | USB 3.x | RPi 5 or Jetson Orin Nano |
| Installed PoC | Orbbec Femto Mega I | PoE Ethernet | Jetson or industrial x86 |
| AI offload PoC | Luxonis OAK-D Pro PoE | PoE Ethernet | RPi 5 or Jetson |
| Production | One model, fully validated | Ethernet/PoE preferred | Jetson Orin Nano |

Start with the D455 because the ecosystem is wide, the USB setup is straightforward, and you can have frames on screen in an afternoon. Once you need ceiling mounts and long cable runs, the Femto Mega I's PoE connection and IP65 housing make it the cleaner choice.

### Sensing Technology Tradeoffs

| Method | How it works | Strengths | Weaknesses | Fit |
|--------|-------------|-----------|------------|-----|
| Active IR Stereo (D455) | Projects IR pattern, computes disparity | Robust to room lighting, mature SDK | Depth holes on dark/matte fabric, multi-camera IR crosstalk | MVP first choice |
| iToF (Femto Mega) | Modulates IR, measures phase shift | Uniform depth on texture-free surfaces | IR crosstalk risk with other ToF devices | Installed PoC |
| Edge AI Stereo (OAK-D) | Stereo + on-device VPU inference | Reduces host load, privacy-friendly | Absolute accuracy needs independent validation | Low-power PoC |

---

## Physical Connections

### RealSense D455

```
[D455]
  └─── USB 3.1 Gen 1 (Type-C)
          └─── USB 3.x port on edge board (direct, no hub)
```

**Wiring rules:**
- Direct to a USB 3.x port — no passive hubs.
- Cable ≤ 1 m is ideal; ≥ 3 m needs an active USB repeater (include it in EMC testing).
- Shielded industrial cable in X-ray environments.
- After boot, run `rs-enumerate-devices -s` and confirm `USB 3.x` — silent USB 2.0 fallback kills FPS without error messages.

**Power:** Bus-powered (~2.1 W peak). RPi 5's USB 3.0 port is rated 600 mA. If the board's PSU is borderline, symptoms are random frame drops at peak current draw. Use a 27 W+ USB-C PD adapter.

### Orbbec Femto Mega I (PoE)

```
[Femto Mega I]
  └─── Cat6 Ethernet
          └─── PoE Switch / PoE Injector
                  └─── Edge board eth port
```

**Network rules:**
- Camera gets its own VLAN — isolated from hospital HIS/PACS.
- Assign a static IP. Avoid DHCP for reproducible reconnects.
- Some Orbbec models use multicast for device discovery; make sure your managed switch passes it within the VLAN.
- Check PoE budget: Femto Mega draws ~10–15 W.

```
Camera VLAN example: 192.168.50.0/24
  Camera:     192.168.50.10
  Edge board: 192.168.50.2
  Gateway:    none (isolated)
```

### Luxonis OAK-D Pro PoE

Same PoE wiring as the Femto. The difference is the pipeline model: you define a `depthai` pipeline on the host, upload it to the camera's VPU, and only receive processed results (depth, ROI coordinates) back — raw frames stay on the camera.

> **DepthAI v3 note**: The SDK broke its API in v3.0.0 (September 2025). `ColorCamera`/`MonoCamera` nodes are gone, replaced by a unified `Camera` node. If your code targets v2, pin to `v2_stable`. New code should target v3. Do **not** mix `depthai-sdk` (pip helper) with `depthai-core` in v3 — they're incompatible.

---

## SDK Installation

### librealsense (D455)

The repo moved from `IntelRealSense/` to `realsenseai/` in mid-2025. Update any hardcoded clone URLs.

We use the **RSUSB backend** — it avoids kernel patches, which matters when you need to apply OS security updates without breaking the camera driver.

```bash
git clone https://github.com/realsenseai/librealsense.git
cd librealsense
git checkout v2.XX.X   # pin to a tested release

mkdir build && cd build
cmake .. \
  -DBUILD_EXAMPLES=ON \
  -DBUILD_PYTHON_BINDINGS=ON \
  -DFORCE_RSUSB_BACKEND=ON
make -j$(nproc)
sudo make install
```

Sanity check:

```bash
rs-enumerate-devices      # lists connected devices
rs-depth-quality          # validates depth stream quality
```

Python sanity check:

```python
import pyrealsense2 as rs
ctx = rs.context()
for d in ctx.devices:
    print(d.get_info(rs.camera_info.name),
          d.get_info(rs.camera_info.serial_number))
```

> **Version pairing**: if you source-build `librealsense2`, build the Python bindings at the same time (`-DBUILD_PYTHON_BINDINGS=ON`). Mixing a source-built native library with a pip-installed `pyrealsense2` wheel causes silent ABI mismatches.

### Orbbec SDK v2

```bash
# Clone the v2 branch (OpenNI v1 protocol is a separate legacy branch)
git clone https://github.com/orbbec/OrbbecSDK.git
cd OrbbecSDK
git checkout v2.X.X    # pin version

mkdir build && cd build
cmake ..
make -j$(nproc)
sudo make install
```

> **v1 vs v2**: Femto Mega and all devices released after October 2024 require SDK v2. v1 (OpenNI protocol) is a separate branch. Don't mix them.

### DepthAI / depthai-core (OAK-D)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install depthai opencv-python   # v3 is the current release
```

Device check:

```python
import depthai as dai
print(dai.Device.getAllAvailableDevices())
```

---

## Camera Abstraction Interface

All three cameras are wrapped behind a single C++ interface. Upper services (`depth_processor`, etc.) never see vendor SDK types.

```cpp
// services/camera_service/include/IDepthCamera.h

struct DepthFrame {
    int64_t  timestamp_ms;
    int64_t  monotonic_ms;
    uint64_t frame_id;
    int      width, height;
    float    depth_scale_m;     // meters per raw unit
    const uint16_t* data;       // Z16, owned by ring buffer slot
};

struct DeviceInfo {
    std::string vendor;
    std::string model;
    std::string serial;
    std::string firmware;
    std::string sdk_version;
};

class IDepthCamera {
public:
    virtual ~IDepthCamera() = default;
    virtual bool open(const CameraConfig& cfg) = 0;
    virtual void close() = 0;
    virtual bool getFrame(DepthFrame& out,
                          std::chrono::milliseconds timeout) = 0;
    virtual DeviceInfo getDeviceInfo() const = 0;
    virtual CameraIntrinsics getIntrinsics() const = 0;
    virtual bool isConnected() const = 0;
};
```

Each vendor gets its own adapter in `services/camera_service/adapters/`. Switching cameras in production is a config change, not a code change.

---

## Depth Processing Pipeline

```
Raw Depth Frame (shared memory)
  │
  ├─ [1] Frame validity check
  │       reject: invalid timestamp, zero frame_id, excessive age
  │
  ├─ [2] Empty-bed calibration compensation
  │       thickness = Z_bed_reference − Z_patient_surface
  │
  ├─ [3] Extrinsic correction [R | t]
  │       camera frame → bed frame transform from calibration file
  │
  ├─ [4] Depth range gate
  │       discard pixels outside [min_range_mm, max_range_mm]
  │
  ├─ [5] ROI crop
  │       chest ROI template from calibration, adjusted per exam type
  │
  ├─ [6] Outlier rejection (IQR-based)
  │
  ├─ [7] Temporal filter (exponential moving average)
  │
  ├─ [8] Spatial median filter
  │
  └─ [9] Stat extraction → DepthSummary message
          median_depth_mm, mean_depth_mm, std_depth_mm,
          valid_pixel_ratio, estimated_thickness_mm
```

**Why median, not mean?** Hospital gowns and linens absorb the IR pattern and create depth holes (invalid pixels). Mean is dragged toward the hole values; median is not. Use trimmed mean as a fallback if you need mean.

**Respiration signal:**

```
dZ/dt  = (Z[t] − Z[t-1]) / Δt_ms          # velocity
d²Z/dt² = (dZ/dt[t] − dZ/dt[t-1]) / Δt_ms # acceleration (cough/jerk detection)
```

A cough produces a spike in `d²Z/dt²` that's distinct from a slow breath. The `d²Z/dt²` channel triggers an `abort` even if `dZ/dt` hasn't crossed the velocity threshold yet.

---

## Respiration State Machine

```
idle
 │ camera_ready
 ▼
tracking ──────────────────────────────────────────► abort
 │ cue_issued                                         ▲
 ▼                                                    │ cough / camera_error / low_confidence
cue_requested                                         │
 │ abs(dZ/dt) < θ_v                                   │
 │ && var(Z[t−w:t]) < θ_var                           │
 │ && valid_pixel_ratio > θ_quality                   │
 │ && stable_duration_ms > T_min                      │
 ▼                                                    │
stable_breath_hold ──────────────────────────────────►│
 │ operator_approve
 ▼
idle

tracking ─── elapsed > T_timeout ──► timeout ──► idle
any_state ── manual_override ──► manual_mode
```

All thresholds (`θ_v`, `θ_var`, `θ_quality`, `T_min`, `T_timeout`) are in `configs/gating.yaml` and are validated against a signed config signature at startup.

---

## Calibration

### One-time (installation)

| Step | Tool / Method |
|------|---------------|
| Intrinsics | Confirm SDK-reported intrinsics, store in calibration file |
| Extrinsic (camera → bed) | Flat calibration plate on table, record transform matrix |
| Depth scale validation | 50 mm / 100 mm / 200 mm rigid phantom blocks |
| ROI templates | Record chest ROI per exam type (chest PA, lateral, etc.) |
| Lighting baseline | Measure with room lights on/off, check valid_pixel_ratio |

### Daily (on service start)

```bash
# Triggered automatically by camera_service at startup
# Can also be run manually
python scripts/calibrate_empty_bed.py --profile configs/calib_room_a.json
```

The script checks that the empty-bed depth plane is within tolerance of the stored reference. If it drifts beyond the threshold (camera bumped, table height changed), the service refuses to publish recommendations and logs `CALIBRATION_DRIFT`.

Calibration profiles are stored in `configs/calib_*.json` with a SHA-256 signature. Any unsigned or mismatched file blocks the service from starting.

**Calibration JSON schema:**

```json
{
  "profile_id": "calib_room_a_20260624",
  "created_at": "2026-06-24T09:00:00+09:00",
  "camera_serial": "123456789",
  "schema_version": "1.0.0",
  "bed_origin_mm": 1112.7,
  "extrinsic_matrix_4x4": [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]],
  "roi_templates": {
    "chest_pa": {"x": 320, "y": 180, "width": 420, "height": 280}
  },
  "valid_pixel_ratio_baseline": 0.93,
  "approved_by": "installation_engineer",
  "signature": "ed25519:..."
}
```

---

## Frame Settings

| Use case | Depth resolution | FPS | Notes |
|----------|-----------------|-----|-------|
| Breathing waveform | 640×480 | 30 | MVP default |
| Thickness measurement | 640×480 – 1280×720 | 15–30 | Accuracy > FPS |
| UI display | Downsampled | 15–30 | Don't render full-res in UI |
| Precision validation | Max resolution | ≥15 | Long-run frame-drop test |

---

## Fault Handling

| Fault | Detection | Response |
|-------|-----------|----------|
| Camera not found | `sdk.device_count == 0` | `CAMERA_DISCONNECTED` error, safe state |
| USB 2.0 fallback | `rs-enumerate-devices -s` speed field | Warning log, reduced-capability mode |
| Frame drop spike | Drop rate > threshold/min | `FRAME_DROP_EXCEEDED`, degrade confidence |
| IR saturation | SDK metadata flag | `IR_SATURATION` warning, quality reduced |
| PoE link lost | Heartbeat timeout | 3 reconnect attempts, then safe state |
| Depth hole surge | `valid_pixel_ratio < θ` | Confidence reduced, manual mode prompted |
| SDK crash | systemd watchdog timeout | Service restart, recommendations disabled |

The golden rule: **a camera fault must never affect the X-ray machine's normal manual workflow.** This system is an overlay, not a gatekeeper.

---

## Related Docs

- [`docs/hardware.md`](hardware.md) — board selection, power, mounting
- [`docs/api-schema.md`](api-schema.md) — `CameraFrameMeta` and `DepthSummary` message schemas
- [`docs/tech-stack-assessment.md`](tech-stack-assessment.md) — SDK vendor status and known issues
- [`docs/verification-validation.md`](verification-validation.md) — phantom test plan
