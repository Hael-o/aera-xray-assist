# deployment.md — 설치, 배포, 운영, 업데이트 설계서

작성 대상: 시니어 개발자, DevOps/임베디드 엔지니어, 병원 설치 담당자  
관련 문서: `README.md`, `docs/hardware.md`, `docs/api-schema.md`, `docs/regulatory.md`

---

## 1. 목적

본 문서는 스마트 호흡 연동 및 체형 맞춤형 촬영 보조 시스템의 운영체제 설치, 런타임 구성, 서비스 배포, systemd 등록, 오프라인 업데이트, 롤백, 현장 운영, 장애 대응 절차를 정의한다.

병원 촬영실은 폐쇄망 또는 제한망일 가능성이 높으므로, 온라인 패키지 설치에 의존하지 않는 오프라인 배포 구조를 기본으로 한다.

---

## 2. 대상 플랫폼

| 플랫폼 | OS/BSP | 권장 용도 |
|---|---|---|
| Raspberry Pi 5 | Raspberry Pi OS 64-bit / Ubuntu 22.04 ARM64 | MVP, D455 기반 PoC |
| Jetson Orin Nano | JetPack 6.x / Ubuntu 22.04 기반 | 제품 후보, TensorRT 추론 |
| 산업용 x86 | Ubuntu 22.04 LTS | 병원 설치형, 장기 유지보수 |

---

## 3. 배포 산출물 구조

```text
release-package/
  manifest.json
  checksums.sha256
  signature.sig
  services/
    camera_service
    depth_processor
    respiration_gating
    exposure_recommender
    api_gateway
    audit_logger
  ui/
    operator-ui.tar.gz
  configs/
    device.yaml
    camera.yaml
    gating.yaml
    exposure_lut.yaml
  models/
    respiration_model.onnx
    model_manifest.json
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

## 4. 레포 구조

```text
project-root/
  README.md
  docs/
    camera.md
    hardware.md
    regulatory.md
    risk-management.md
    api-schema.md
    deployment.md
  services/
    camera_service/
    depth_processor/
    respiration_gating/
    exposure_recommender/
    api_gateway/
    audit_logger/
    device_gateway/
  ui/
    operator-ui/
  configs/
  models/
  tests/
    unit/
    integration/
    playback/
    hil/
    fault-injection/
  deploy/
    systemd/
    scripts/
    docker/
  tools/
    calibration/
    log-export/
    phantom-simulator/
```

---

## 5. OS 설치 기준

### 5.1 Raspberry Pi 5

권장:

- Raspberry Pi OS 64-bit 또는 Ubuntu 22.04 ARM64
- NVMe SSD 부팅 권장
- swap 최소화 또는 명확히 관리
- active cooler 필수

초기 설정:

```bash
sudo apt update
sudo apt install -y git cmake build-essential pkg-config \
  python3 python3-venv python3-pip \
  libssl-dev sqlite3 jq curl
```

확인:

```bash
uname -a
vcgencmd measure_temp
vcgencmd get_throttled
lsusb
```

### 5.2 Jetson Orin Nano

권장:

- JetPack 6.x
- NVMe SSD rootfs
- `nvpmodel` 고정
- thermal log 수집

초기 확인:

```bash
cat /etc/nv_tegra_release
tegrastats
nvcc --version
python3 -c "import tensorrt as trt; print(trt.__version__)"
```

전력/성능:

```bash
sudo nvpmodel -q
sudo nvpmodel -m 0
sudo jetson_clocks
```

주의:

- `jetson_clocks`는 PoC/성능 측정용으로 사용하고, 제품화에서는 발열/소음/전력 정책을 별도 정의한다.

---

## 6. Camera SDK 설치 전략

상세 설치는 `docs/camera.md` 기준.

### 6.1 RealSense

권장 패키지:

- `librealsense2`
- `pyrealsense2`는 PoC용
- C++ 제품화 시 librealsense C++ API 사용

검증 명령:

```bash
rs-enumerate-devices
rs-depth-quality
realsense-viewer
```

### 6.2 Orbbec

권장:

- Orbbec SDK
- PoE 모델은 전용 네트워크 대역 구성
- SDK 예제 기반 프레임 수신 테스트

검증:

```bash
ping 10.20.30.10
# Orbbec SDK sample 실행
```

### 6.3 Luxonis OAK

권장:

- DepthAI SDK
- PoE 모델은 static IP 또는 discovery 설정
- ROI inference pipeline은 카메라 내부 배치 가능

검증:

```bash
python3 -m pip install depthai
python3 -c "import depthai as dai; print(dai.__version__)"
```

---

## 7. 서비스 배포 방식

### 7.1 systemd 서비스 분리

권장 서비스:

| 서비스 | 역할 |
|---|---|
| xray-camera.service | 카메라 연결 및 frame publish |
| xray-core.service | depth/gating/recommendation core |
| xray-api.service | REST/WebSocket API |
| xray-ui.service | Operator UI |
| xray-watchdog.service | health check 및 복구 |

### 7.2 systemd 예시

```ini
[Unit]
Description=Xray Assist Camera Service
After=network.target

[Service]
Type=simple
User=xray
Group=xray
WorkingDirectory=/opt/xray-assist
ExecStart=/opt/xray-assist/bin/camera_service --config /etc/xray-assist/camera.yaml
Restart=always
RestartSec=2
WatchdogSec=10
Environment=XRAY_ENV=production
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
```

설치:

```bash
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable xray-camera xray-core xray-api xray-ui
sudo systemctl start xray-camera xray-core xray-api xray-ui
```

상태 확인:

```bash
systemctl status xray-camera
journalctl -u xray-camera -f
```

---

## 8. 설정 파일 관리

### 8.1 device.yaml

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
  raw_frame_storage: disabled
```

### 8.2 camera.yaml

```yaml
camera:
  provider: realsense
  model: D455
  serial: auto
  width: 1280
  height: 720
  fps: 30
  align_depth_to_color: false
  roi_default:
    x: 320
    y: 180
    width: 420
    height: 280

quality:
  min_valid_pixel_ratio: 0.85
  max_frame_drop_per_min: 30
  min_confidence: 0.8
```

### 8.3 gating.yaml

```yaml
gating:
  stable_dz_dt_threshold_mm_s: 2.0
  min_stable_duration_ms: 1000
  timeout_ms: 10000
  audio_latency_offset_ms: 1800
  cough_abort_threshold_mm_s: 25.0
```

### 8.4 exposure_lut.yaml

```yaml
metadata:
  version: 1.3.0
  approved_by: qa
  signed: true

chest_pa:
  adult:
    - thickness_mm_min: 0
      thickness_mm_max: 180
      kvp: 70
      mas: 8.0
    - thickness_mm_min: 181
      thickness_mm_max: 240
      kvp: 82
      mas: 15.0
    - thickness_mm_min: 241
      thickness_mm_max: 320
      kvp: 90
      mas: 22.0

guardrails:
  kvp_min: 60
  kvp_max: 120
  mas_min: 1.0
  mas_max: 80.0
```

---

## 9. 로컬 DB 및 로그

권장 DB:

- SQLite WAL mode
- audit_events table
- calibration_profiles table
- sessions table
- system_events table

초기화:

```bash
sqlite3 /var/lib/xray-assist/xray.db < migrations/001_init.sql
```

WAL 설정:

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=FULL;
PRAGMA foreign_keys=ON;
```

로그 경로:

```text
/var/log/xray-assist/camera.log
/var/log/xray-assist/core.log
/var/log/xray-assist/api.log
/var/log/xray-assist/audit-export.log
```

로그 수집:

```bash
sudo /opt/xray-assist/scripts/collect-logs.sh --since "24 hours ago"
```

---

## 10. 보안 하드닝

### 10.1 계정

```bash
sudo useradd --system --home /var/lib/xray-assist --shell /usr/sbin/nologin xray
sudo mkdir -p /var/lib/xray-assist /var/log/xray-assist /etc/xray-assist
sudo chown -R xray:xray /var/lib/xray-assist /var/log/xray-assist
```

### 10.2 SSH

권장:

- password login 비활성화
- key-only 접근
- 현장 유지보수 계정 별도 관리
- 외부망 연결 금지 또는 제한

### 10.3 USB

제품화 단계:

- 불필요한 USB storage 차단
- 카메라 포트 고정
- 유지보수 모드에서만 USB 로그 export 허용

### 10.4 업데이트 서명 검증

```bash
sha256sum -c checksums.sha256
gpg --verify signature.sig manifest.json
```

또는 Ed25519 기반 전용 서명 검증 도구를 사용한다.

---

## 11. 오프라인 업데이트

### 11.1 업데이트 절차

```text
1. release-package를 USB 또는 내부망으로 전달
2. checksums 검증
3. signature 검증
4. 현재 버전 backup
5. 서비스 중지
6. 바이너리/설정/모델 업데이트
7. DB migration
8. 서비스 시작
9. health check
10. 실패 시 rollback
```

### 11.2 manifest.json 예시

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

### 11.3 롤백 기준

다음 조건에서 자동 롤백한다.

- 서비스 health check 실패
- DB migration 실패
- 모델 서명 검증 실패
- 카메라 SDK 초기화 실패
- UI가 60초 내 시작되지 않음
- core service crash loop 발생

---

## 12. Health Check

Endpoint:

```http
GET http://localhost:8080/api/v1/health
```

systemd watchdog script:

```bash
#!/usr/bin/env bash
set -euo pipefail
curl -fsS http://127.0.0.1:8080/api/v1/health | jq -e '.status == "ok"'
```

---

## 13. 현장 설치 절차

```text
1. 촬영실 설치 위치 확인
2. 카메라 마운트 설치
3. Edge Board 설치
4. USB/PoE/전원 배선 고정
5. OS/SDK 설치 또는 이미지 플래싱
6. 서비스 배포
7. 카메라 인식 테스트
8. 빈 베드 캘리브레이션
9. 정적 phantom 측정
10. 동적 호흡 phantom 측정
11. UI/오디오/수동모드 테스트
12. 설치 리포트 생성
```

설치 리포트 포함 항목:

- 장비 serial
- 카메라 serial/firmware
- 보드 serial
- OS/SDK 버전
- 설치 위치 사진 또는 도식
- 캘리브레이션 결과
- 프레임 드롭 테스트 결과
- 오디오 latency 측정값
- 담당자 서명

---

## 14. 운영 모니터링

수집 지표:

| 지표 | 주기 | 용도 |
|---|---|---|
| CPU/GPU 온도 | 60초 | 발열 추적 |
| FPS | 1초 | 프레임 안정성 |
| frame drop | 1초 | 카메라/USB/PoE 품질 |
| service restart count | 이벤트 | 장애 분석 |
| DB write latency | 10초 | 저장소 상태 |
| disk usage | 5분 | 로그/DB 용량 관리 |
| recommendation count | 세션 | 사용량 분석 |
| abort count | 세션 | workflow 개선 |

---

## 15. 백업/로그 export

기본 백업 대상:

- audit_events
- calibration_profiles
- system_events
- config versions
- model/lut version manifest

원본 RGB/Depth frame은 기본 백업하지 않는다.

Export 예시:

```bash
/opt/xray-assist/scripts/export-audit.sh \
  --from 2026-06-01 \
  --to 2026-06-24 \
  --output /media/usb/audit_export_20260624.zip
```

---

## 16. 장애 대응 Runbook

### 16.1 카메라 인식 실패

```bash
lsusb
rs-enumerate-devices
systemctl restart xray-camera
journalctl -u xray-camera -n 200
```

대응:

- USB 3.x 포트 확인
- 케이블 교체
- 카메라 전원 재연결
- 수동 모드 전환

### 16.2 프레임 드롭 과다

확인:

```bash
journalctl -u xray-camera | grep FRAME_DROP
tegrastats
vcgencmd get_throttled
```

대응:

- 해상도/FPS 낮춤
- USB 허브 제거
- PoE switch 상태 확인
- 발열 확인

### 16.3 DB 오류

확인:

```bash
df -h
sqlite3 /var/lib/xray-assist/xray.db "PRAGMA integrity_check;"
```

대응:

- 디스크 용량 확보
- 최근 backup 복구
- 감사로그 export 후 DB rotate

### 16.4 UI 미표시

확인:

```bash
systemctl status xray-ui
curl http://localhost:8080/api/v1/health
```

대응:

- UI 서비스 재시작
- HDMI/브라우저 kiosk 상태 확인
- 수동 모드 안내

---

## 17. Kiosk UI 배포 optional

브라우저 기반 UI 사용 시:

```bash
chromium-browser --kiosk http://localhost:3000
```

systemd user service 또는 display manager 자동 실행으로 구성한다.

주의:

- 네트워크 외부 URL 접근 금지
- UI refresh 시 세션 상태 유지
- 오류 화면에서 수동 모드 안내 표시

---

## 18. 컨테이너 사용 기준

PoC에서는 Docker를 사용할 수 있으나, Jetson 카메라/USB/GPU/real-time 처리에서는 native systemd가 단순하고 안정적일 수 있다.

컨테이너 사용 시 검토:

- USB device passthrough
- NVIDIA Container Runtime
- udev rule
- systemd watchdog 연동
- persistent volume
- offline image distribution

제품화 기준:

| 방식 | 장점 | 단점 |
|---|---|---|
| Native systemd | 단순, 디바이스 접근 쉬움 | dependency 관리 필요 |
| Docker | 환경 재현성 좋음 | USB/GPU/실시간 I/O 복잡 |
| A/B image | 롤백 강함 | 빌드/배포 체계 복잡 |

---

## 19. 배포 전 체크리스트

| 항목 | 완료 기준 |
|---|---|
| OS 버전 고정 | manifest에 기록 |
| SDK 버전 고정 | camera SDK 버전 기록 |
| 모델/설정 서명 | 검증 통과 |
| DB migration | 테스트 통과 |
| systemd 자동 시작 | 재부팅 후 정상 |
| camera health | 30 FPS 이상 안정 |
| UI health | 상태 표시 정상 |
| audit log | hash chain 생성 |
| safe state | fault injection 통과 |
| rollback | 실패 시 이전 버전 복구 |

---

## 20. 결론

배포 구조는 병원 폐쇄망과 장시간 안정성을 전제로 설계해야 한다. 초기에는 native systemd 기반으로 단순하게 구성하고, signed offline update와 rollback을 반드시 포함한다. 원본 RGB/Depth 저장은 기본 금지하며, 감사로그와 캘리브레이션 프로파일만 관리 대상으로 삼는다.
