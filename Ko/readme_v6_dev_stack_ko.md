# 스마트 호흡 연동 및 체형 맞춤형 X-ray 촬영 지원 시스템 구축 가이드라인 (V6 - 실제 개발 스택 포함)

> 작성 대상: 시니어 개발자, 시스템 아키텍트, 임베디드 개발자, 의료기기 소프트웨어 개발 리드  
> 문서 목적: 3D Depth 센서 기반 환자 체형/호흡 측정, X-ray 촬영 파라미터 추천, Operator Assist UI, 안전 검증, 장비 연동 확장, 실제 개발 가능한 기술스택과 런타임 아키텍처 정의  
> V6 주요 개정사항: 실제 개발 기술스택, 보드 연결 방식, 카메라 SDK/드라이버, 서비스 모듈 구조, IPC, DB, 배포, 테스트, DevOps, 보안, 위험관리 기준 추가

---

## 0. 제품 범위와 기본 설계 원칙

본 시스템은 3D Depth 카메라를 이용해 환자의 촬영 부위 두께와 호흡 안정 상태를 실시간으로 측정하고, 방사선사 또는 장비 조작자에게 촬영 조건과 촬영 타이밍을 보조적으로 제안하는 시스템이다.

초기 제품은 X-ray 장비를 단독으로 제어하거나 촬영을 자동 결정하지 않는다. 모든 추천값과 촬영 타이밍은 작업자의 최종 확인 및 승인 절차를 거친다.

### 0.1 개발 단계별 권장 범위

| 단계 | 범위 | X-ray 장비 제어 | 권장도 | 설명 |
|---|---|---:|---:|---|
| Phase 1 | Operator Assist | 없음 | 매우 높음 | 3D 센서 측정값과 추천 kVp/mAs를 UI에 표시하고 작업자가 수동 입력 |
| Phase 2 | Workstation Agent | 제한적 반자동 | 중간 | 촬영 PC Agent가 추천값을 오토필하되 작업자 최종 승인 필수 |
| Phase 3 | Generator Direct Integration | 직접 제어 | 낮음/후속 | 제조사 API·프로토콜 협조, 의료기기 심사, 전기안전 검증 후 추진 |
| Phase 4 | Controlled Model Update | 승인된 모델 업데이트 | 후속 | 현장 단말에서 임의 학습이 아니라 검증된 모델/룰셋만 서명 후 배포 |
| Phase 5 | On-device Continual Learning | 제한적 고도화 | 연구/후속 | 별도 임상·규제·검증 체계 확보 후 제한적 활성화 |

### 0.2 핵심 안전 원칙

- 시스템은 X-ray 조사를 단독 결정하지 않는다.
- 추천 kVp/mAs에는 최소·최대 허용 범위와 장비별 금지 조합을 둔다.
- 호흡 안정 판정 실패, 센서 오류, 캘리브레이션 실패, 통신 오류 발생 시 기본값은 `Abort` 또는 `Manual Mode`로 전환한다.
- 자동 학습 또는 모델 업데이트 기능은 초기 MVP 범위에서 제외한다.
- 환자 식별 정보와 원시 3D 데이터는 기본적으로 저장하지 않는다.
- 모든 추천, 승인, Abort, 모델 버전, 캘리브레이션 버전은 감사로그로 남긴다.

---

## 1. 실제 개발 기술스택 요약

### 1.1 권장 스택 매트릭스

| 계층 | MVP 권장 | 제품화 후보 | 비고 |
|---|---|---|---|
| Target Board | Raspberry Pi 5 8GB 또는 Jetson Orin Nano 8GB | Jetson Orin Nano / Orin Nano Super / 산업용 x86 | MVP는 Pi도 가능. AI/3D 고도화는 Jetson 또는 x86 권장 |
| AI Accelerator | 없음 또는 Raspberry Pi AI HAT+ | Jetson CUDA/TensorRT, 산업용 NVIDIA GPU | AI HAT+는 카메라 드라이버가 아니라 추론 가속용 |
| OS | Raspberry Pi OS 64-bit / Ubuntu 22.04 ARM64 | JetPack 6.x Ubuntu 22.04 기반 / Ubuntu LTS | 제품화 시 read-only rootfs, watchdog 권장 |
| Camera | Intel RealSense D455 | Orbbec Femto Mega I / OAK-D Pro PoE / 최종 선정 1종 | PoE 설치형은 별도 검증 후 전환 |
| Camera SDK | `librealsense2`, `pyrealsense2` | Orbbec SDK, DepthAI SDK, vendor C++ SDK | SDK 버전 고정 필요 |
| Core Language | Python 3.11 for PoC | C++20 중심, Python은 툴링/테스트 | 실시간 서비스는 C++ 권장 |
| Build | `pip`, `venv`, 간단 스크립트 | CMake, Conan/vcpkg, Docker/Podman, Debian package | 병원 폐쇄망은 오프라인 패키지 필요 |
| AI Runtime | ONNX Runtime CPU / Hailo Runtime | TensorRT, ONNX Runtime TensorRT EP | Jetson은 TensorRT 우선 |
| CV/Math | NumPy, OpenCV | OpenCV C++, Eigen, PCL, CUDA/VPI optional | Point Cloud는 PCL 또는 자체 경량 구조 |
| IPC | REST/WebSocket 단일 프로세스 | ZeroMQ/gRPC + Shared Memory Ring Buffer | 실시간 Depth는 JSON으로 넘기지 않음 |
| UI | Web UI 또는 PyQt 빠른 PoC | React/Vue + TypeScript + WebSocket, 또는 Qt/QML | Operator Assist UI |
| Local DB | SQLite | SQLite WAL / DuckDB optional / append-only audit log | 원시 Depth 저장 금지 기본 |
| Config | YAML/TOML | YAML/TOML + JSON Schema + signed config | 병원별 장비 프로파일 분리 |
| Logging | text log | structured log, audit log, log rotation, hash chain | 의료기기 감사 대응 |
| Device Control | 없음 | GPIO opto relay, TCP/IP, RS-422, CAN, Modbus | Phase 2/3부터 적용 |
| Audio | OS 기본 재생 | GStreamer + ALSA, 레이턴시 측정 보정 | 호흡 안내용 |
| Test | 수동 테스트 | GoogleTest, pytest, HIL, playback, phantom | 제품화 전 필수 |
| Deployment | 수동 설치 | systemd service, signed package, offline update, rollback | 폐쇄망 대응 |
| Security | 계정/방화벽 | Secure Boot, disk encryption, mTLS, RBAC, signed update | 병원망 분리 |

### 1.2 기술 선택 원칙

- MVP는 빠른 실험을 위해 Python을 허용하되, 제품화 후보는 C++20 기반 서비스로 전환한다.
- Camera SDK는 Vendor API를 직접 UI에 붙이지 않고 `camera_service`에서 추상화한다.
- 실시간 Depth Frame은 Shared Memory Ring Buffer로 공유하고, UI에는 요약 상태만 WebSocket으로 전달한다.
- 장비 제어는 초기에는 구현하지 않고, Phase 2부터 별도 `device_gateway` 프로세스로 격리한다.
- 모델 추론은 최소한 `model_id`, `model_hash`, `runtime`, `latency_ms`를 로그로 남긴다.

---

## 2. 권장 레포지토리 구조

```text
smart-xray-assist/
├─ README.md
├─ docs/
│  ├─ architecture.md
│  ├─ camera.md
│  ├─ risk-management.md
│  ├─ regulatory-notes.md
│  ├─ validation-plan.md
│  └─ deployment.md
├─ configs/
│  ├─ default.yaml
│  ├─ hospital_profile.example.yaml
│  ├─ camera_profile.d455.yaml
│  ├─ camera_profile.orbbec.yaml
│  └─ exposure_lut.example.yaml
├─ schemas/
│  ├─ config.schema.json
│  ├─ audit_event.schema.json
│  └─ depth_summary.schema.json
├─ services/
│  ├─ camera_service/
│  │  ├─ include/
│  │  ├─ src/
│  │  ├─ adapters/
│  │  │  ├─ realsense_adapter.cpp
│  │  │  ├─ orbbec_adapter.cpp
│  │  │  └─ depthai_adapter.cpp
│  │  └─ CMakeLists.txt
│  ├─ depth_processor/
│  ├─ respiration_gating/
│  ├─ exposure_recommender/
│  ├─ device_gateway/
│  ├─ audit_logger/
│  └─ api_gateway/
├─ ui/
│  ├─ operator-console/
│  └─ kiosk-display/
├─ models/
│  ├─ README.md
│  ├─ stable_breathhold.onnx
│  └─ manifest.json
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  ├─ playback/
│  ├─ hil/
│  └─ fixtures/
├─ scripts/
│  ├─ install_realsense_ubuntu.sh
│  ├─ setup_jetson.sh
│  ├─ setup_pi.sh
│  ├─ calibrate_empty_bed.py
│  └─ export_onnx_to_trt.sh
├─ deploy/
│  ├─ systemd/
│  ├─ docker/
│  ├─ debian/
│  └─ offline-update/
└─ CMakeLists.txt
```

---

## 3. 런타임 서비스 아키텍처

### 3.1 프로세스 분리 구조

```text
[3D Depth Camera]
      │ USB 3.x / Ethernet PoE
      ▼
[camera_service]
      │ Shared Memory Ring Buffer: depth_frame, confidence, timestamp
      ├──────────────► [depth_processor]
      │                    │ ROI, thickness, motion_vector, quality_score
      │                    ▼
      │              [respiration_gating]
      │                    │ stable/unstable, gating_window, trigger_recommendation
      │                    ▼
      │              [exposure_recommender]
      │                    │ recommended kVp/mAs, confidence, constraints
      │                    ▼
      ├──────────────► [api_gateway] ── WebSocket/REST ──► [Operator UI]
      │
      ├──────────────► [audit_logger]
      │
      └──────────────► [device_gateway]  Phase 2+ only
```

### 3.2 서비스별 책임

| 서비스 | 책임 | 권장 구현 |
|---|---|---|
| `camera_service` | Vendor SDK 연동, Depth Frame 수집, timestamp 정렬, frame quality 산출 | C++20, vendor SDK wrapper |
| `depth_processor` | Empty bed 보정, ROI 추출, thickness 계산, noise filtering | C++20, OpenCV/Eigen/PCL |
| `respiration_gating` | 호흡 파형 생성, peak/plateau 감지, stable window 판정 | C++20, rule-based first |
| `exposure_recommender` | thickness/body profile 기반 kVp/mAs 추천, safety clamp | C++20 or Rust, LUT + rules |
| `api_gateway` | UI용 REST/WebSocket, 상태 요약, 작업자 승인 이벤트 | FastAPI for MVP, C++/Go for product |
| `audit_logger` | append-only audit log, hash chain, SQLite WAL | C++/Go/Python 가능 |
| `device_gateway` | RS-422/CAN/TCP/GPIO Relay 격리 제어 | C++20, 별도 권한/프로세스 |
| `ui/operator-console` | 작업자 UI, 추천값 표시, 승인/Abort/Manual Mode | React/Vue + TypeScript 또는 Qt/QML |

### 3.3 프로세스 간 통신

| 데이터 종류 | 방식 | 이유 |
|---|---|---|
| Raw Depth Frame | Shared Memory Ring Buffer | 30FPS 이상 대용량 프레임 복사 비용 최소화 |
| ROI/Thickness Summary | ZeroMQ pub/sub 또는 gRPC streaming | 모듈 간 느슨한 결합 |
| UI State | WebSocket | 실시간 상태 표시 |
| Config Update | REST + signed config validation | 운영 중 변경 관리 |
| Audit Event | local append-only queue | 네트워크 장애와 무관하게 기록 |
| Device Command | 별도 IPC + allowlist command | 장비 제어 권한 격리 |

---

## 4. 엣지 하드웨어 및 보드 구성

### 4.1 하드웨어 모델별 타당성 비교

| 검토 항목 | Raspberry Pi 5 + AI HAT+ | NVIDIA Jetson Nano 4GB | NVIDIA Jetson Orin Nano / Super 8GB | 평가 및 의사결정 |
|---|---|---|---|---|
| CPU | Cortex-A76 4-core 2.4GHz | Cortex-A57 4-core 1.43GHz | Cortex-A78AE 6-core급 | 범용 I/O와 경량 UI는 Pi 5도 충분. 고성능 AI/3D 처리는 Orin 계열 권장 |
| GPU/CUDA | CUDA 미지원 | Maxwell CUDA | Ampere CUDA | TensorRT/LibTorch 파이프라인은 Jetson 계열이 유리 |
| AI 가속 | AI HAT+ 13/26 TOPS 추론 가속 | 성능 제한 | Orin Nano/Super 40~67 TOPS급 | 실시간 추론은 Pi 5 + AI HAT+ 가능. 복잡한 비전은 Orin 권장 |
| 개발환경 | Raspberry Pi OS, Ubuntu ARM64 | JetPack 4.x 제약 | JetPack 6.x 계열 | 신규 제품은 Pi 5 또는 Orin 계열 권장 |
| 전력/발열 | 저전력 | 저전력이나 성능 제한 | 고성능 모드 시 발열 관리 필수 | 의료 장비 하우징 내 온도 모니터링 필수 |
| 권장 용도 | Phase 1 | PoC/교육용 | Phase 2 이상 | 제품 고도화 표준은 Orin 계열 권장 |

### 4.2 MVP 권장 BOM

| 부품 | 권장 사양 | 비고 |
|---|---|---|
| Board | Raspberry Pi 5 8GB 또는 Jetson Orin Nano 8GB | 개발팀 역량이 CUDA 중심이면 Jetson 우선 |
| Storage | NVMe SSD 256GB 이상 | SD card 단독 운용 비권장 |
| Camera | Intel RealSense D455 | USB 3.x 기반 빠른 MVP |
| Cooler | Active cooler/fan | 8시간 이상 테스트 기준 |
| Display | 10~15 inch touch monitor 또는 외부 웹 UI | Operator Assist |
| Audio | USB speaker 또는 내장 speaker | 호흡 안내 레이턴시 측정 필요 |
| Trigger Interface | Phase 1에서는 미사용 | Phase 2부터 opto-isolated relay 검토 |
| Network | 병원망과 분리된 개발망 | PoE 카메라 사용 시 카메라 전용 VLAN |

### 4.3 Jetson 권장 OS/BSP

- Jetson Orin 계열은 JetPack 6.x 기반으로 고정한다.
- CUDA/TensorRT/cuDNN 버전은 JetPack에 포함된 버전을 사용하고, 임의 업그레이드를 금지한다.
- 제품화 시 container runtime을 쓰더라도 GPU runtime, camera device permission, udev rule을 명시적으로 관리한다.

### 4.4 Raspberry Pi 권장 OS

- Raspberry Pi OS 64-bit 또는 Ubuntu 22.04/24.04 ARM64 중 SDK 호환성이 좋은 쪽을 선택한다.
- RealSense 사용 시 커널/USB/UVC 호환성 검증이 필수다.
- AI HAT+는 Depth 카메라 드라이버가 아니라 Hailo 기반 추론 가속용으로 사용한다.

---

## 5. 3D Depth 카메라 및 실제 연결 방법

### 5.1 단계별 카메라 선정

| 단계 | 추천 카메라 | 연결 방식 | 추천 보드 | 목적 |
|---|---|---|---|---|
| MVP | Intel RealSense D455 | USB 3.x | Pi 5 / Jetson Orin Nano | 흉부 ROI Depth 추적, 호흡 파형 검출, 두께 산출 |
| 설치형 PoC | Orbbec Femto Mega / Mega I | USB 3.0 또는 Ethernet/PoE | Jetson / 산업용 PC | 천장 마운트, 장거리 배선, 산업용 설치성 검증 |
| AI 오프로딩 PoC | Luxonis OAK-D Pro / OAK-D Pro PoE | USB 3.0 또는 PoE | Pi 5 / Jetson | 카메라 내부 ROI 검출, 저전력 보드 연동 |
| 제품화 | 최종 1종 선정 | Ethernet/PoE 우선 검토 | Jetson / 산업용 x86 | 장시간 안정성, 케이블 내구성, 장애 복구성 검증 |

### 5.2 Intel RealSense D455 연결

#### 물리 연결

| 항목 | 권장 구성 |
|---|---|
| 데이터 | USB 3.1 Gen 1 이상, Type-C to USB-A/C |
| 전원 | USB bus power |
| 케이블 길이 | 1~2m 권장, 3m 이상은 산업용 active USB cable 검토 |
| 장착 | 촬영 테이블 상부 또는 측면 고정 브라켓 |
| 권장 보드 | Raspberry Pi 5, Jetson Orin Nano, 산업용 x86 |

#### 드라이버/SDK

- SDK: `librealsense2`
- Python PoC: `pyrealsense2`
- ROS 2 optional: `realsense2_camera`
- Linux에서는 udev rule, kernel module, RSUSB backend 여부를 명확히 결정한다.

#### 데이터 수집 예시 구조

```text
D455 USB 3.x
  └─ librealsense2 pipeline
      ├─ depth stream: Z16
      ├─ color stream: optional
      ├─ align depth to color: MVP에서는 최소화
      └─ camera_service publishes depth_frame to shared memory
```

#### 개발 주의사항

- USB 2.0으로 fallback되면 해상도/FPS가 크게 제한되므로 부팅 시 연결 모드를 검사한다.
- `frame_timestamp`, `hardware_timestamp`, `system_timestamp`의 차이를 로깅한다.
- RGB는 개인정보 위험이 크므로 초기에는 Depth만 활성화하고, RGB는 검증 목적일 때만 제한적으로 사용한다.

### 5.3 Orbbec Femto Mega / Mega I 연결

#### 물리 연결

| 항목 | USB 구성 | Ethernet/PoE 구성 |
|---|---|---|
| 데이터 | USB 3.0 | Gigabit Ethernet |
| 전원 | 별도 어댑터 또는 USB 구성에 따름 | PoE Switch 또는 PoE Injector |
| 케이블 길이 | 1~3m 권장 | Cat6 기준 장거리 설치 유리 |
| 설치 | 근거리 실험 | 천장/벽면 고정 설치 |
| 권장 보드 | Jetson/x86 | Jetson/x86, Pi 5 가능하나 부하 검증 필요 |

#### 드라이버/SDK

- SDK: Orbbec SDK v2
- ROS 2 optional: Orbbec ROS2 wrapper
- Ethernet 사용 시 카메라 전용 subnet/VLAN을 구성한다.

#### 네트워크 예시

```text
Camera VLAN: 192.168.40.0/24
- Orbbec Camera: 192.168.40.10
- Edge Board eth1: 192.168.40.2
- Hospital Network eth0: separate, no routing to camera VLAN by default
```

#### 개발 주의사항

- ToF 장비는 IR 간섭, 반사면, 복수 ToF 카메라 동시 사용 시 crosstalk 검증이 필요하다.
- PoE 카메라는 네트워크 지연, packet loss, reconnect 동작을 HIL 테스트에 포함한다.

### 5.4 Luxonis OAK-D Pro / OAK-D Pro PoE 연결

#### 물리 연결

| 항목 | USB 모델 | PoE 모델 |
|---|---|---|
| 데이터 | USB 3.x | Gigabit Ethernet/PoE |
| 전원 | USB 또는 외부 전원 | PoE Switch/Injector |
| 권장 용도 | 개발/실험 | 설치형 PoC |
| 권장 보드 | Pi 5, Jetson, x86 | Pi 5, Jetson, x86 |

#### 드라이버/SDK

- SDK: DepthAI SDK / depthai-core
- Python PoC: `depthai`
- C++ 제품화: `depthai-core`
- ROS 2 optional: `depthai-ros`

#### 개발 주의사항

- 카메라 내부 VPU에서 ROI 검출을 수행할 수 있지만, 의료용 측정 정확도는 별도 검증한다.
- 카메라가 ROI 좌표만 넘기는 구조는 개인정보 최소화에 유리하지만, 디버깅/검증을 위한 원본 프레임 보존 정책을 별도로 정의해야 한다.

---

## 6. Depth 처리 및 호흡 게이팅 알고리즘

### 6.1 Depth 처리 파이프라인

```text
Depth Frame
  ├─ frame validity check
  ├─ empty bed calibration compensation
  ├─ extrinsic correction [R|T]
  ├─ ROI extraction
  ├─ outlier rejection
  ├─ temporal filtering
  ├─ thickness estimation
  └─ respiration waveform extraction
```

### 6.2 좌표계

| 좌표계 | 설명 |
|---|---|
| Camera Frame | 카메라 기준 좌표계 |
| Bed Frame | 촬영 테이블 기준 좌표계 |
| Patient ROI Frame | 흉부/복부 ROI 기준 좌표계 |
| Device Frame | X-ray 장비 기준 좌표계, Phase 2 이상에서 필요 |

설치 시 `Camera Frame -> Bed Frame` 변환 행렬을 캘리브레이션으로 산출한다.

### 6.3 두께 산출

```text
Thickness = Z_bed_reference - Z_patient_surface_corrected
```

단, 실제 X-ray 투과량은 단순 외형 두께만으로 결정되지 않으므로, 추천 엔진은 체형 모드, 촬영 부위, 장비 프로파일, 병원 정책 LUT를 함께 적용한다.

### 6.4 호흡 안정성 판정

```text
stable = abs(dZ/dt) < theta_velocity
      && variance(Z[t-window:t]) < theta_variance
      && frame_quality > theta_quality
      && no_abort_signal
```

### 6.5 오디오 안내와 트리거 추천

- 시스템은 촬영 트리거를 직접 발생시키지 않고, Phase 1에서는 UI에 “촬영 권장” 상태를 표시한다.
- Phase 2 이상에서도 실제 조사 전 작업자 승인이 필요하다.
- 오디오 안내 지연시간은 장비별 측정값으로 보정한다.

---

## 7. X-ray 장비 연동 아키텍처

### 7.1 사후 DICOM 보정과 사전 추천/제어 비교

| 방식 | 설명 | 장점 | 한계 |
|---|---|---|---|
| 사후 DICOM 보정 | 고정 kVp/mAs 촬영 후 Window/LUT 보정 | 구현 단순, 장비 제어 불필요 | 원본 SNR 부족/과다 피폭 문제 해결 불가 |
| 사전 추천 | 3D 측정값 기반 추천 kVp/mAs를 UI에 표시 | 안전하고 인허가 리스크 낮음 | 작업자 입력 필요 |
| 반자동 오토필 | Workstation Agent가 값 입력, 작업자 승인 | 워크플로우 개선 | 제조사 SW 연동 리스크 |
| 제너레이터 직접 제어 | CAN/RS-422/TCP 등으로 제너레이터 설정 | 완전 자동화 가능 | 규제/전기안전/책임 리스크 큼 |

### 7.2 Phase별 장비 연동

```text
Phase 1: 3D Sensor -> Recommendation UI -> Operator manual input -> Shoot
Phase 2: 3D Sensor -> Workstation Agent -> Auto-fill -> Operator approve -> Shoot
Phase 3: 3D Sensor -> Generator Interface -> Safety Interlock -> Operator approve -> Trigger
```

### 7.3 Device Gateway 설계

`device_gateway`는 반드시 별도 프로세스로 분리한다.

| 항목 | 설계 원칙 |
|---|---|
| 권한 | root/GPIO/CAN 접근 권한은 device_gateway에만 부여 |
| 명령 | allowlist command만 허용 |
| 입력 | 추천값, 승인 이벤트, 장비 상태, safety interlock |
| 출력 | 오토필, 릴레이, CAN/RS-422 frame, TCP command |
| 실패 | 통신 실패 시 Manual Mode 전환 |
| 로그 | 모든 명령과 응답을 audit log에 기록 |

### 7.4 전기적 인터페이스

- GPIO 직접 연결 금지.
- 릴레이/트리거 접점은 opto-isolated interface board 사용.
- 절연 내압, 누설전류, creepage/clearance, EMC 기준 검토.
- 기본 상태는 normally-open 또는 fail-safe inactive.
- watchdog timeout 시 트리거 라인은 비활성화된다.

---

## 8. Operator Assist UI

### 8.1 UI 핵심 화면

| 화면 | 기능 |
|---|---|
| Live Measurement | Depth 품질, ROI 상태, 측정 두께 표시 |
| Respiration Monitor | 호흡 파형, 안정 구간, 안내 타이밍 표시 |
| Exposure Recommendation | 추천 kVp/mAs, 근거, confidence, safety clamp 표시 |
| Approval Panel | 작업자 승인, 보류, Manual Mode, Abort |
| Calibration | Empty bed calibration, camera alignment status |
| Diagnostics | 카메라 연결, FPS, latency, temperature, storage, model version |
| Audit Viewer | 촬영 이벤트, 추천값, 승인 이벤트 조회 |

### 8.2 UI 기술스택

| 옵션 | 장점 | 단점 | 권장 |
|---|---|---|---|
| React + TypeScript + WebSocket | 개발 생산성, 웹 접근성 | 브라우저 런타임 관리 필요 | MVP/제품화 모두 가능 |
| Vue + TypeScript | 학습/구현 용이 | 팀 표준에 따라 결정 | 가능 |
| Qt/QML | 임베디드 kiosk에 강함 | 웹보다 개발자 풀이 좁음 | 의료장비 내장형 UI 후보 |
| PyQt | 빠른 PoC | 제품화 유지보수 낮음 | PoC 한정 |

### 8.3 UI 안전 요구사항

- 추천값과 실제 장비 입력값이 다르면 경고한다.
- confidence가 낮으면 추천값을 숨기고 Manual Mode를 권장한다.
- Abort 버튼은 항상 최상위 visible 상태여야 한다.
- UI 오류가 발생해도 `device_gateway`는 안전 상태를 유지해야 한다.

---

## 9. 데이터 저장, 감사로그, 개인정보 보호

### 9.1 저장 정책

| 데이터 | 기본 저장 | 조건부 저장 | 비고 |
|---|---:|---:|---|
| Raw RGB | 금지 | 검증 모드에서 비식별/동의 후 | 얼굴 정보 위험 |
| Raw Depth Frame | 금지 | 테스트 모드에서 제한 저장 | 기본은 ring buffer only |
| ROI Summary | 허용 | - | 비식별 수치 데이터 |
| Thickness | 허용 | - | 감사 및 품질관리 |
| Recommended kVp/mAs | 허용 | - | 의사결정 근거 |
| Operator Approval | 허용 | - | 책임 추적 |
| Model Version/Hash | 허용 | - | 재현성 |
| Calibration Profile | 허용 | - | 측정 신뢰도 |

### 9.2 DB 스키마 초안

```sql
CREATE TABLE audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_time_utc TEXT NOT NULL,
  event_type TEXT NOT NULL,
  session_id TEXT NOT NULL,
  operator_id_hash TEXT,
  camera_id TEXT,
  model_id TEXT,
  model_hash TEXT,
  calibration_id TEXT,
  measured_thickness_mm REAL,
  recommended_kvp REAL,
  recommended_mas REAL,
  confidence REAL,
  decision TEXT,
  reason TEXT,
  prev_hash TEXT,
  event_hash TEXT NOT NULL
);
```

### 9.3 개인정보 보호

- 얼굴/두부 ROI는 Depth ROI Nulling 또는 좌표 양자화 처리한다.
- UI는 기본적으로 RGB 화면을 표시하지 않는다.
- 원시 프레임 저장 기능은 개발/검증 모드에서만 활성화하고, 접근 권한과 보존 기간을 제한한다.
- 로그에는 주민등록번호, 환자명, 촬영영상 원본을 저장하지 않는다.

---

## 10. AI/ML 런타임 및 모델 운영

### 10.1 MVP 모델 전략

MVP에서는 학습형 AI보다 규칙 기반 알고리즘과 고정 모델을 우선한다.

| 기능 | MVP 방식 | 후속 방식 |
|---|---|---|
| ROI 검출 | 수동 ROI 또는 경량 rule-based | YOLO/segmentation model |
| 호흡 안정성 | dZ/dt, variance, quality score | TensorRT/ONNX 모델 |
| 두께 기반 추천 | LUT + rule clamp | 병원/장비별 calibrated model |
| 지속 학습 | 제외 | 승인된 offline training + signed update |

### 10.2 AI 런타임 선택

| 환경 | 권장 Runtime | 비고 |
|---|---|---|
| Raspberry Pi only | ONNX Runtime CPU 또는 Hailo Runtime | AI HAT+ 사용 시 Hailo toolchain 필요 |
| Jetson | TensorRT 우선, ONNX Runtime TensorRT EP 가능 | ONNX export -> TensorRT engine build |
| x86 NVIDIA GPU | TensorRT / ONNX Runtime TensorRT EP | 배포 환경 고정 필요 |
| 카메라 내부 AI | DepthAI / OAK pipeline | ROI 결과만 host로 전송 가능 |

### 10.3 모델 배포 정책

- 모델 파일은 `models/manifest.json`에 `model_id`, `version`, `sha256`, `runtime`, `input_shape`, `approval_status`를 기록한다.
- 서명되지 않은 모델은 로드하지 않는다.
- 새 모델은 Golden Test Suite를 통과해야만 `active` 상태가 된다.
- 모델 변경 시 이전 모델로 즉시 rollback 가능해야 한다.

---

## 11. 캘리브레이션

### 11.1 설치 시 캘리브레이션

| 항목 | 설명 |
|---|---|
| Empty Bed Plane | 빈 촬영 테이블의 depth plane을 기준면으로 저장 |
| Extrinsic Calibration | 카메라-베드 좌표계 변환 행렬 산출 |
| ROI Preset | 촬영 부위별 기본 ROI 정의 |
| Camera Intrinsic | 제조사 SDK intrinsic 저장 및 버전 기록 |
| Lighting/IR Baseline | 촬영실 조명/IR 노이즈 baseline 측정 |

### 11.2 일일 캘리브레이션

- 시스템 시작 시 빈 베드 확인.
- 기준 평면 오차가 threshold를 넘으면 재캘리브레이션 요구.
- 카메라 위치가 흔들린 경우 `Calibration Invalid` 상태로 전환.
- 캘리브레이션 프로파일은 hash와 함께 audit log에 기록.

---

## 12. 보안 및 배포

### 12.1 보안 요구사항

| 영역 | 요구사항 |
|---|---|
| Boot | Secure Boot 검토 |
| Storage | Disk encryption 또는 최소한 sensitive partition encryption |
| Update | signed package, offline update, rollback |
| Network | 카메라망/병원망 분리, mTLS, firewall allowlist |
| Account | RBAC, default password 금지, SSH 기본 비활성 |
| USB | 운영 모드에서 USB mass storage 제한 |
| Log | append-only, hash chain, rotation, export control |
| Model | signed model, hash validation |

### 12.2 systemd 서비스 예시

```ini
[Unit]
Description=Smart X-ray Assist Camera Service
After=network-online.target

[Service]
ExecStart=/opt/smart-xray/bin/camera_service --config /etc/smart-xray/config.yaml
Restart=always
RestartSec=3
User=smartxray
Group=smartxray
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/smart-xray /var/log/smart-xray /dev/shm

[Install]
WantedBy=multi-user.target
```

### 12.3 오프라인 업데이트 구조

```text
update_package.tar
├─ manifest.json
├─ services/*.deb
├─ ui/*.tar.gz
├─ models/*.onnx
├─ configs/*.yaml
├─ migration/*.sql
└─ signature.sig
```

업데이트 전후로 다음을 수행한다.

1. 서명 검증
2. 패키지 hash 검증
3. DB migration dry-run
4. 서비스 중지
5. 설치
6. Golden Test Suite 실행
7. 실패 시 rollback

---

## 13. 테스트 및 검증 계획

### 13.1 테스트 레벨

| 레벨 | 테스트 | 목표 |
|---|---|---|
| Unit | 필터, ROI, LUT, gating logic | 알고리즘 함수 검증 |
| Integration | camera_service -> depth_processor -> UI | 모듈 간 계약 검증 |
| Playback | 저장된 비식별 depth sequence 재생 | 회귀 테스트 |
| HIL | 실제 보드 + 실제 카메라 + phantom | 하드웨어 통합 검증 |
| Fault Injection | 카메라 disconnect, frame drop, IR saturation | 안전 상태 전환 검증 |
| Long-run | 8/24/72시간 연속 스트리밍 | 메모리 누수, 발열, FPS 안정성 |
| Usability | 작업자 UI 사용성 | 오입력/오해 방지 |

### 13.2 Mechanical Breathing Phantom

- 스텝모터 기반 상하 운동 장치.
- 진폭: 2~50mm.
- 주기: 성인/소아/불규칙 호흡 패턴.
- 목표: gating window 오차, false stable, false abort 측정.

### 13.3 합격 기준 예시

| 항목 | 기준 |
|---|---|
| Depth FPS | 목표 FPS 대비 95% 이상 유지 |
| Frame Drop | 1분 평균 drop rate threshold 이하 |
| Thickness Repeatability | 동일 phantom 반복 측정 오차 threshold 이하 |
| Gating Latency | 내부 처리 지연 33ms 이하 목표 |
| Abort Response | fault 발생 후 지정 시간 내 Manual/Abort 전환 |
| UI Update | 10Hz 이상 상태 업데이트 |
| Log Integrity | hash chain 검증 통과 |

---

## 14. 위험관리 초안

| 위험 | 원인 | 영향 | 완화책 |
|---|---|---|---|
| 잘못된 두께 측정 | 카메라 오정렬, calibration 실패 | 잘못된 촬영조건 추천 | calibration check, confidence 표시, Manual Mode |
| 과다 선량 추천 | LUT 오류, 체형 보정 오류 | 환자 피폭 증가 | min/max clamp, operator approval, 장비별 금지 조합 |
| 과소 선량 추천 | 비만/의복/ROI 오류 | 영상 품질 저하, 재촬영 | quality score, bariatric offset, confidence threshold |
| 잘못된 호흡 안정 판정 | 센서 노이즈, 기침, 움직임 | 영상 blur, 재촬영 | dZ/dt abort, timeout, 재안내 |
| 비의도 트리거 | 릴레이/소프트웨어 오류 | 안전 사고 | Phase 1 미사용, opto isolation, interlock, watchdog |
| 모델 성능 저하 | 잘못된 업데이트 | 오판단 | signed model, golden test, rollback |
| 개인정보 유출 | RGB/Depth 원본 저장 | 법적/윤리적 문제 | raw 저장 금지, ROI masking, RBAC |
| 네트워크 침해 | 병원망 연결 | 장비/데이터 위험 | network segmentation, firewall, mTLS |

---

## 15. 의료기기 및 규제 고려사항

본 문서는 규제 판단을 확정하지 않는다. 실제 등급과 제출 문서는 사용목적, X-ray 장비 제어 여부, 임상 의사결정 영향도, 소프트웨어 독립성에 따라 별도 판단이 필요하다.

초기 단계부터 다음 체계를 고려한다.

- ISO 13485: 품질경영시스템
- IEC 62304: 의료기기 소프트웨어 생명주기
- ISO 14971: 위험관리
- IEC 62366: 사용적합성
- IEC 60601 계열: 의료용 전기기기 안전/EMC 검토
- 개인정보보호법 및 병원 내부 보안 정책

---

## 16. 개발 마일스톤

### Milestone 1: Depth MVP

- D455 연결
- depth frame 수집
- empty bed calibration
- ROI thickness 산출
- 단순 Web UI 표시

### Milestone 2: Respiration Gating

- 호흡 파형 생성
- stable/unstable 판정
- audio guide timing
- abort/timeout 처리

### Milestone 3: Exposure Recommendation

- 촬영 부위별 LUT
- safety clamp
- confidence score
- operator approval workflow

### Milestone 4: Audit & Validation

- SQLite audit log
- model/config/calibration version logging
- playback regression test
- phantom test

### Milestone 5: PoE Camera & Production Hardening

- Orbbec/OAK PoE PoC
- camera abstraction layer
- systemd service
- offline update
- security hardening

### Milestone 6: Workstation Agent / Device Gateway

- 제조사 연동 가능성 검토
- Workstation auto-fill PoC
- opto-isolated relay test only in lab
- 규제/전기안전 검토 후 진행

---

## 17. 개발 환경 설치 가이드 초안

### 17.1 공통 패키지

```bash
sudo apt update
sudo apt install -y \
  build-essential cmake ninja-build pkg-config git curl jq \
  python3 python3-venv python3-pip \
  libopencv-dev libeigen3-dev libssl-dev sqlite3 \
  gstreamer1.0-tools alsa-utils
```

### 17.2 Python PoC 환경

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install numpy opencv-python fastapi uvicorn pydantic pyzmq pytest
```

### 17.3 RealSense PoC

```bash
# 실제 설치는 OS/커널/보드별 공식 librealsense 가이드를 따른다.
# 설치 후 확인:
realsense-viewer
python -c "import pyrealsense2 as rs; print(rs.__version__)"
```

### 17.4 Jetson TensorRT 변환 예시

```bash
trtexec \
  --onnx=models/stable_breathhold.onnx \
  --saveEngine=models/stable_breathhold_fp16.engine \
  --fp16 \
  --workspace=2048
```

---

## 18. 핵심 인터페이스 스키마

### 18.1 Depth Summary JSON

```json
{
  "schema_version": "1.0",
  "timestamp_ns": 0,
  "camera_id": "D455-001",
  "frame_id": 12345,
  "roi_id": "chest_ap",
  "thickness_mm": 231.4,
  "motion_velocity_mm_s": 0.8,
  "motion_variance": 0.03,
  "frame_quality": 0.94,
  "confidence": 0.91,
  "calibration_id": "calib-20260624-001"
}
```

### 18.2 Recommendation JSON

```json
{
  "schema_version": "1.0",
  "session_id": "session-uuid",
  "timestamp_ns": 0,
  "body_part": "chest_ap",
  "measured_thickness_mm": 231.4,
  "recommended_kvp": 82,
  "recommended_mas": 15,
  "confidence": 0.88,
  "constraints_applied": ["max_mas_clamp", "device_profile_limit"],
  "requires_operator_approval": true,
  "model_id": "rule-lut-v1",
  "model_hash": "sha256:..."
}
```

### 18.3 Audit Event JSON

```json
{
  "schema_version": "1.0",
  "event_type": "operator_approved_recommendation",
  "event_time_utc": "2026-06-24T12:00:00Z",
  "session_id": "session-uuid",
  "operator_id_hash": "sha256:...",
  "camera_id": "D455-001",
  "calibration_id": "calib-20260624-001",
  "payload_hash": "sha256:...",
  "prev_hash": "sha256:...",
  "event_hash": "sha256:..."
}
```

---

## 19. V6 최종 권장 개발 방향

1. MVP는 **RealSense D455 + Raspberry Pi 5 또는 Jetson Orin Nano + Web UI + 규칙 기반 추천**으로 시작한다.
2. 실시간 처리 코어는 처음부터 서비스 경계를 나누고, Vendor SDK는 `camera_service` 안에 격리한다.
3. Raw Depth/RGB 저장은 기본 금지하고, 테스트 모드에서만 비식별 샘플을 제한 저장한다.
4. Phase 1에서는 X-ray 장비 직접 제어를 하지 않는다.
5. 제품화 후보 단계에서는 C++20, systemd, signed update, audit log, HIL test를 필수로 포함한다.
6. 온디바이스 지속 학습은 초기 제품 기능이 아니라 후속 연구/고도화 기능으로 분리한다.
7. 카메라 선택은 “스펙 최고”보다 “반복정확도, 장시간 안정성, 설치성, 장애 복구성, SDK 유지보수성” 기준으로 최종 결정한다.

---

## 20. 참고 자료

- NVIDIA JetPack 6.x / Jetson Linux / TensorRT 공식 문서
- Intel RealSense librealsense 공식 설치 문서
- Raspberry Pi AI HAT+ 공식 제품 문서
- Orbbec SDK / Femto Mega 공식 문서
- Luxonis DepthAI 공식 문서
- ROS 2 공식 문서
- IEC 62304, ISO 13485, ISO 14971, IEC 62366, IEC 60601 계열 표준
