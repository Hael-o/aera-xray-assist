# Hardware & deployment

[← back to README](../README.md)

Distilled from the design specs in [`en/files/hardware.md`](../en/files/hardware.md), [`deployment.md`](../en/files/deployment.md), and [`tech-stack-assessment.md`](../en/files/tech-stack-assessment.md). This describes **target/production intent**; the current repo runs Phase 1 on a mock camera.

## Depth cameras (evaluated)

| Camera | Phase | Sensing | Depth | Link / power | Notes |
|---|---|---|---|---|---|
| **Intel RealSense D455** | MVP | active IR stereo | 1280×720 @ 30 fps (Z16), 0.6–6.0 m, FoV 87°×58° | USB 3.1 Gen1 Type-C, ~2.1 W | cable ≤1 m ideal (3 m+ needs active repeater); silent USB 2.0 fallback risk; SDK org moved `IntelRealSense`→`realsenseai` (mid-2025) |
| **Orbbec Femto Mega I** | installed PoC | iToF | 1024×1024 @ 15 fps, RGB 4K | Ethernet/PoE, ~10–15 W, IP65 | ceiling-mount stable; static IP on isolated VLAN; Orbbec SDK v2 |
| **Luxonis OAK-D Pro PoE** | AI-offload PoC | active stereo + neural | — | USB 3.0 / PoE (802.3af) | Myriad X (RVC2, 4 TOPS); DepthAI v2→v3 break (Sept 2025) → full re-validation |

## Compute boards

| Board | Phase | CPU / GPU | AI | Notes |
|---|---|---|---|---|
| **Raspberry Pi 5 (8 GB)** | MVP | Cortex-A76 4-core @ 2.4 GHz | opt. AI HAT+ (Hailo-8L 13 TOPS / Hailo-8 26 TOPS) | USB 3.0 ×2 (900 mA/port); NVMe; active cooling for 8 h sustained; RPi OS 64-bit / Ubuntu 22.04 ARM64 |
| **Jetson Orin Nano (8 GB / Super)** | production | Cortex-A78AE 6-core + Ampere 1024 CUDA | 40 TOPS (67 TOPS Super, JetPack 6.2) | shared 8 GB LPDDR5 — memory-profile to avoid OOM; use `nvpmodel` (not `jetson_clocks`); TensorRT 10.3 / CUDA 12.6 |
| **Industrial x86** | fixed install | — | — | Ubuntu 22.04 LTS |

### Known SDK / toolchain hazards (spec)

- **TensorRT 8→10** (JetPack 6): implicit batch removed, `enqueueV2`→`enqueueV3`, `Dims` int32→int64; old `.engine` files must be rebuilt (tag files with JetPack/TRT/CUDA versions).
- **ONNX Runtime TRT EP**: `pip install onnxruntime-gpu` may silently activate CPU EP only — source-build with `--use_tensorrt`.
- **Hailo compilation** (DFC) is x86-only — RPi cannot compile `.onnx`→`.hef`; needs an x86 CI/build server.
- **RPi 5 Wayland/Chromium**: default `labwc` drops full-screen on HDMI change → use `cage` (kiosk compositor).

## Release bundle

```
release-package/
  manifest.json            (versions, migration flags, rollback)
  checksums.sha256
  signature.sig            (Ed25519 over manifest)
  services/{camera_service, depth_processor, respiration_gating,
            exposure_recommender, api_gateway, audit_logger}
  ui/operator-console.tar.gz
  configs/{device,camera,gating,exposure_lut}.yaml
  models/{*.onnx|*.engine, manifest.json, model_signature.sig}
  migrations/{001_init.sql, 002_audit_hash.sql}
  systemd/{xray-camera,xray-core,xray-ui}.service
  scripts/{install.sh, rollback.sh, healthcheck.sh, collect-logs.sh}
```

## systemd services

| Service | Responsibility |
|---|---|
| `xray-camera.service` | camera connection + frame publish |
| `xray-core.service` | depth processing, gating, recommendation |
| `xray-api.service` | REST + WebSocket API gateway |
| `xray-ui.service` | operator display (Chromium kiosk or Qt) |
| `xray-watchdog.service` | health checks + auto-recovery |

Hardening in the unit files: `NoNewPrivileges=true`, `PrivateTmp=true`, `ProtectSystem=full`, `ProtectHome=true`, `Restart=always`, `WatchdogSec=10` (the service must call `sd_notify(WATCHDOG=1)` periodically, or the watchdog never fires).

## Config files (production paths)

`device.yaml` (id/site/room, `mode: operator_assist`, DB `/var/lib/xray-assist/xray.db`, `raw_frame_storage: disabled`) · `camera.yaml` (provider/model/serial, resolution/fps, quality gates) · `gating.yaml` (thresholds + per-device `audio_latency_offset_ms`) · `exposure_lut.yaml` (signed LUT + guardrails). See [`smart-xray-assist/configs/`](../smart-xray-assist/configs).

## Offline update & rollback

Air-gapped hospital networks mean **no `apt install` in production** — SDKs/TensorRT/CUDA are vendored and version-locked (SBOM generated).

1. transfer bundle (USB / internal net) → 2. verify SHA-256 → 3. verify Ed25519 on `manifest.json` → 4. backup current → 5. stop services → 6. `install.sh` → 7. DB migrations → 8. start → 9. Golden Test Suite (`healthcheck.sh --golden`) → 10. on failure `rollback.sh`.

**Automatic rollback triggers**: health check fails, DB migration fails, model signature invalid, camera SDK init fails, UI unresponsive > 60 s, core crash loop.

Health check: `curl -fsS http://127.0.0.1:8080/api/v1/health | jq -e '.status=="ok"'`. Log rotation via `logrotate` (daily, 30-day, compress).

## On-site installation checklist

mounting (no beam interference) → camera bracket/cabling → OS image → deploy bundle → camera recognition (`rs-enumerate-devices -s`) → empty-bed calibration → static phantom accuracy → breathing phantom → UI/audio/manual-mode → fault injection (disconnect → safe state ≤ 2 s) → **signed installation report** (serials, firmware, OS/SDK versions, calibration JSON+signature, frame-drop & audio-latency results, technician signature).

Related: [Camera abstraction](camera-abstraction.md) · [Verification](verification.md)
