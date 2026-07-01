# Deployment Guide

Hospital networks are air-gapped by design. Everything here assumes you can't `apt install` anything on the target device during deployment — the release bundle has to carry its own dependencies.

---

## Target Platforms

| Platform | OS | Use Case |
|----------|----|----------|
| Raspberry Pi 5 | Ubuntu 22.04 ARM64 | MVP, D455-based PoC |
| Jetson Orin Nano | JetPack 6.x (Ubuntu 22.04) | Production candidate |
| Industrial x86 | Ubuntu 22.04 LTS | Hospital fixed install |

---

## Release Bundle Layout

Every release ships as a single signed tarball:

```
release-package/
  manifest.json         ← versions, migration flags, rollback support
  checksums.sha256
  signature.sig         ← Ed25519 signature over manifest
  services/
    camera_service
    depth_processor
    respiration_gating
    exposure_recommender
    api_gateway
    audit_logger
  ui/
    operator-console.tar.gz
  configs/
    device.yaml
    camera.yaml
    gating.yaml
    exposure_lut.yaml
  models/
    *.onnx / *.engine
    manifest.json
    model_signature.sig
  migrations/
    001_init.sql
    002_audit_hash.sql
  systemd/
    xray-camera.service
    xray-core.service
    xray-ui.service
  scripts/
    install.sh
    rollback.sh
    healthcheck.sh
    collect-logs.sh
```

---

## Services

| Service | Responsibility |
|---------|----------------|
| `xray-camera.service` | Camera connection and frame publish |
| `xray-core.service` | Depth processing, gating, recommendation |
| `xray-api.service` | REST + WebSocket for operator UI |
| `xray-ui.service` | Operator display (Chromium kiosk or Qt) |
| `xray-watchdog.service` | Health checks and automatic recovery |

### systemd Unit (example: camera service)

```ini
[Unit]
Description=X-ray Assist Camera Service
After=network.target

[Service]
Type=simple
User=xray
Group=xray
WorkingDirectory=/opt/xray-assist
ExecStart=/opt/xray-assist/bin/camera_service --config /etc/xray-assist/camera.yaml
Restart=always
RestartSec=2
WatchdogSec=10          # service must call sd_notify("WATCHDOG=1") periodically
Environment=XRAY_ENV=production
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/var/lib/xray-assist /var/log/xray-assist /dev/shm

[Install]
WantedBy=multi-user.target
```

> **`WatchdogSec`**: set this on every service and implement `sd_notify(0, "WATCHDOG=1")` inside the service loop. Without the in-process notification, systemd's watchdog never triggers even if the service is frozen.

Install and enable:

```bash
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable xray-camera xray-core xray-api xray-ui
sudo systemctl start xray-camera xray-core xray-api xray-ui
```

---

## System Account

All services run as the `xray` user. Set this up once:

```bash
sudo useradd --system \
  --home /var/lib/xray-assist \
  --shell /usr/sbin/nologin \
  xray

sudo mkdir -p /var/lib/xray-assist /var/log/xray-assist /etc/xray-assist
sudo chown -R xray:xray /var/lib/xray-assist /var/log/xray-assist
```

---

## Configuration Files

### `device.yaml`

```yaml
device:
  id: edge-001
  site_id: hospital-a
  room_id: xray-room-1
  mode: operator_assist
  timezone: Asia/Seoul

storage:
  database_path: /var/lib/xray-assist/xray.db
  log_path: /var/log/xray-assist
  raw_frame_storage: disabled    # never enable in production
```

### `camera.yaml`

```yaml
camera:
  provider: realsense            # realsense | orbbec | depthai
  model: D455
  serial: auto
  width: 1280
  height: 720
  fps: 30
  align_depth_to_color: false

quality:
  min_valid_pixel_ratio: 0.85
  max_frame_drop_per_min: 30
  min_confidence: 0.80
```

### `gating.yaml`

```yaml
gating:
  stable_dz_dt_threshold_mm_s: 2.0
  stable_variance_threshold: 0.03
  min_stable_duration_ms: 1000
  timeout_ms: 10000
  audio_latency_offset_ms: 1800   # measure per-device; see calibration procedure
  cough_abort_d2z_threshold_mm_s2: 25.0
```

> **`audio_latency_offset_ms`**: this is not a guess. Measure it at installation by recording a reference microphone signal and comparing it against the GStreamer output timestamp. The procedure is in [`docs/verification-validation.md`](verification-validation.md#audio-latency-measurement).

### `exposure_lut.yaml`

```yaml
metadata:
  version: 1.3.0
  approved_by: qa
  signed: true

chest_pa:
  adult:
    - { thickness_mm_min:   0, thickness_mm_max: 180, kvp:  70, mas:  8.0 }
    - { thickness_mm_min: 181, thickness_mm_max: 240, kvp:  82, mas: 15.0 }
    - { thickness_mm_min: 241, thickness_mm_max: 320, kvp:  90, mas: 22.0 }
  pediatric:
    - { thickness_mm_min:   0, thickness_mm_max: 120, kvp:  60, mas:  4.0, note: "pending clinical review" }
  bariatric:
    - { thickness_mm_min: 321, thickness_mm_max: 450, kvp: 100, mas: 40.0, note: "pending clinical review" }

guardrails:
  kvp_min: 60
  kvp_max: 120
  mas_min: 1.0
  mas_max: 80.0
```

Entries marked `"pending clinical review"` cause the service to return a `manual_review_required: true` flag on any recommendation for that mode — the UI will not show a numeric suggestion.

---

## Database Initialization

```bash
sqlite3 /var/lib/xray-assist/xray.db < migrations/001_init.sql

# Set WAL pragmas (persisted)
sqlite3 /var/lib/xray-assist/xray.db <<SQL
PRAGMA journal_mode=WAL;
PRAGMA synchronous=FULL;
PRAGMA foreign_keys=ON;
SQL
```

---

## Log Rotation

Without logrotate, audit logs will fill the disk. Add this to `/etc/logrotate.d/xray-assist`:

```
/var/log/xray-assist/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    postrotate
        systemctl kill -s HUP xray-core.service 2>/dev/null || true
    endscript
}
```

---

## Offline Update Procedure

```
1. Transfer release-package via USB or internal network
2. Verify SHA-256 checksums
3. Verify Ed25519 signature on manifest.json
4. Backup current version (binaries + DB snapshot)
5. Stop services
6. Run install.sh (binaries, config, models)
7. Run DB migrations
8. Start services
9. Run Golden Test Suite (healthcheck.sh --golden)
10. On failure → run rollback.sh automatically
```

### `manifest.json` (example)

```json
{
  "package_version": "0.6.0",
  "target": "jetson-orin-nano",
  "created_at": "2026-06-24T00:00:00+09:00",
  "components": {
    "camera_service": "0.6.0",
    "core": "0.6.0",
    "operator_ui": "0.6.0",
    "model": "respiration-0.3.1",
    "lut": "exposure-lut-1.3.0"
  },
  "requires_migration": true,
  "rollback_supported": true
}
```

### Automatic Rollback Triggers

- Health check fails after service start
- DB migration fails
- Model signature invalid
- Camera SDK fails to initialize
- UI doesn't respond within 60 seconds
- Core service enters crash loop

---

## Security Hardening

**SSH:**
- Disable password auth (`PasswordAuthentication no` in `sshd_config`)
- Key-only access
- Separate maintenance account with limited sudo
- Block external network access by default

**USB:**
- Disable USB mass storage in production (`/etc/modprobe.d/disable-usb-storage.conf`)
- Camera ports whitelisted by udev rule
- Log export only in signed maintenance mode

**Update verification:**

```bash
# On delivery of a release bundle:
sha256sum -c checksums.sha256
gpg --verify signature.sig manifest.json
# Or using the Ed25519 device key:
./scripts/verify-release.sh release-package/
```

---

## Health Check

```bash
curl -fsS http://127.0.0.1:8080/api/v1/health | jq -e '.status == "ok"'
```

Used by the systemd watchdog script and the post-update Golden Test Suite.

---

## On-Site Installation Checklist

```
1.  Confirm mounting location (no X-ray beam interference)
2.  Install camera bracket
3.  Mount and fix cable runs
4.  Flash OS or image the board
5.  Deploy release bundle
6.  Camera recognition test (rs-enumerate-devices -s)
7.  Empty-bed calibration
8.  Static phantom depth accuracy test
9.  Dynamic breathing phantom test
10. UI / audio / manual-mode test
11. Fault injection: disconnect camera → safe state within 2 s
12. Generate and sign installation report
```

**Installation report must include:**
- Device serial, camera serial + firmware
- OS and SDK versions
- Calibration results (JSON + signature)
- Frame-drop test results
- Audio latency measurement
- Technician signature

---

## Operations Monitoring

| Metric | Interval | Purpose |
|--------|----------|---------|
| CPU / GPU temp | 60 s | Thermal tracking |
| FPS | 1 s | Frame stability |
| Frame drop rate | 1 s | Cable / USB / PoE quality |
| Service restart count | event | Fault analysis |
| DB write latency | 10 s | Storage health |
| Disk usage | 5 min | Log / DB capacity |
| Recommendation count | per session | Usage analytics |
| Abort count | per session | Workflow improvement |

---

## Fault Runbook

### Camera not recognized

```bash
lsusb
rs-enumerate-devices
systemctl restart xray-camera
journalctl -u xray-camera -n 200
```

Check: USB 3.x port, cable, camera power. If unresolved → switch to manual mode.

### Excessive frame drops

```bash
journalctl -u xray-camera | grep FRAME_DROP
tegrastats        # Jetson
vcgencmd get_throttled  # RPi
```

Check: resolution/FPS settings, USB hub removal, PoE switch status, thermal throttling.

### DB error / disk full

```bash
df -h
sqlite3 /var/lib/xray-assist/xray.db "PRAGMA integrity_check;"
```

Free disk space, restore from backup, or rotate logs manually.

### UI not displaying

```bash
systemctl status xray-ui
curl http://localhost:8080/api/v1/health
```

Restart UI service, check HDMI connection and kiosk compositor. Inform operator to use manual mode.

---

## Kiosk UI Setup

```bash
# cage compositor (more stable than labwc for full-screen kiosk)
sudo apt install cage
cage chromium-browser --kiosk http://localhost:3000
```

Configure via systemd user service or display manager autostart.
- Never allow the kiosk browser to reach external URLs.
- Reconnect logic must handle WebSocket drops (exponential backoff, sequence numbers).
- Error screens must show a clear **Manual Mode** path.

---

## Container vs Native

For initial deployment, native systemd is simpler and avoids USB/GPU passthrough complexity. Revisit containers in Phase 2+ if multi-service orchestration complexity warrants it.

| Approach | Pros | Cons |
|----------|------|------|
| Native systemd | Simple, direct device access | Manual dependency management |
| Docker | Reproducible environments | USB/GPU/realtime I/O complexity |
| A/B image | Strongest rollback | Complex build pipeline |
