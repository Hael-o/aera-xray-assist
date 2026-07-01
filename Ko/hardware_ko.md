# hardware.md — 엣지 하드웨어, 센서, X-ray 연동 하드웨어 설계서

작성 대상: 시니어 개발자, 임베디드/하드웨어 엔지니어, 시스템 아키텍트  
관련 문서: `README.md`, `docs/camera.md`, `docs/deployment.md`, `docs/risk-management.md`

---

## 1. 목적

본 문서는 스마트 호흡 연동 및 체형 맞춤형 촬영 보조 시스템의 실제 하드웨어 구성, 보드 선정, 카메라 연결, 전기적 절연, 촬영 장비 연동, 전원/발열/배선 설계 기준을 정의한다.

초기 제품 범위는 X-ray 장비를 직접 제어하지 않는 `Operator Assist` 모드로 제한한다. 즉, 시스템은 환자 체형과 호흡 안정성에 기반한 추천값과 상태를 표시하고, 최종 촬영 파라미터 설정과 촬영 행위는 작업자가 승인한다.

---

## 2. 하드웨어 구성 개요

```text
[3D Depth Camera]
     │ USB 3.x 또는 PoE/Ethernet
     ▼
[Edge Compute Board]
     ├─ camera_service
     ├─ depth_processor
     ├─ respiration_gating
     ├─ exposure_recommender
     ├─ audit_logger
     └─ device_gateway(optional)
     │
     ├─ HDMI/DP → Operator Display
     ├─ USB Audio / 3.5mm Audio → Speaker
     ├─ GPIO / RS-422 / CAN / TCP → X-ray Integration(optional)
     └─ Ethernet → Workstation Agent(optional)
```

---

## 3. 권장 하드웨어 트랙

| 단계 | 목적 | 보드 | 카메라 | 연결 | 비고 |
|---|---|---|---|---|---|
| MVP | 알고리즘 검증 | Raspberry Pi 5 8GB 또는 Jetson Orin Nano | Intel RealSense D455 | USB 3.x | 빠른 개발, 낮은 비용 |
| PoC Advanced | 설치형 촬영실 검증 | Jetson Orin Nano 8GB | D455 / Orbbec Femto Mega I | USB 3.x / PoE | 천장 설치, 장시간 안정성 검증 |
| 제품 후보 | 준상용 안정화 | Jetson Orin Nano Industrial 또는 산업용 x86 | PoE Depth Camera | PoE/Ethernet | 전원, 발열, 장애 복구 중점 |
| AI 오프로딩 | 저전력 보드 구성 | Raspberry Pi 5 + AI HAT+ 또는 OAK-D Pro PoE | OAK-D Pro PoE | PoE | 카메라 내부 ROI 추론 |

---

## 4. 엣지 보드 선정 기준

### 4.1 Raspberry Pi 5

권장 용도:

- 초기 MVP
- RealSense D455 기반 Depth Map 수집
- 규칙 기반 호흡 게이팅
- Operator Assist UI
- AI 학습이 없는 경량 추론

권장 구성:

| 항목 | 권장값 |
|---|---|
| Board | Raspberry Pi 5 8GB |
| OS | Raspberry Pi OS 64-bit 또는 Ubuntu 22.04 ARM64 |
| Storage | NVMe SSD 권장, SD Card는 PoC 한정 |
| AI Acceleration | Raspberry Pi AI HAT+ 13 TOPS/26 TOPS optional |
| Camera | RealSense D455, OAK-D Pro, Orbbec USB 모델 |
| Cooling | Active Cooler 필수 |

주의사항:

- Raspberry Pi AI HAT+는 Depth 카메라 드라이버가 아니라 AI 추론 가속 보드다.
- Hailo 계열 NPU는 주로 추론용으로 설계되며, CUDA 기반 on-device training 대체재가 아니다.
- RealSense USB 대역폭 사용 시 저품질 USB 케이블이나 허브 사용을 금지한다.

### 4.2 Jetson Orin Nano

권장 용도:

- 실시간 Depth 처리 + TensorRT 추론
- ROS 2 기반 센서 파이프라인
- 장시간 촬영실 PoC
- 일부 로컬 경량 학습 연구
- TensorRT/ONNX Runtime 기반 고속 추론

권장 구성:

| 항목 | 권장값 |
|---|---|
| Board | Jetson Orin Nano 8GB / Orin Nano Super Developer Kit |
| OS/BSP | JetPack 6.x, Ubuntu 22.04 기반 |
| AI Runtime | TensorRT, CUDA, cuDNN, ONNX Runtime TensorRT EP |
| Storage | NVMe SSD 256GB 이상 |
| Cooling | PWM Fan + 방열판 + 온도 모니터링 |
| Power | 공식 전원 어댑터 또는 산업용 DC 전원 |

주의사항:

- Jetson Nano 구형 4GB는 신규 개발 기준으로 권장하지 않는다.
- JetPack 4.x 의존성은 유지보수 리스크가 크다.
- 장시간 구동 시 `nvpmodel`, `jetson_clocks`, thermal throttling 로그를 함께 수집해야 한다.

---

## 5. 카메라 하드웨어 연결

상세 카메라 비교와 SDK 설치는 `docs/camera.md`를 기준으로 한다. 본 문서에서는 보드와의 물리 연결만 요약한다.

### 5.1 Intel RealSense D455 — USB 3.x

```text
[D455]
  └─ USB-C to USB-A/C 3.x Cable
       └─ Edge Board USB 3.x Port
```

권장사항:

- USB 3.x 포트에 직접 연결한다.
- USB 2.0 fallback 발생 여부를 부팅 시 로그로 확인한다.
- 케이블 길이는 가능한 1m 이하를 권장한다.
- 의료 장비 주변에서는 차폐 케이블과 고정 브라켓을 사용한다.
- 카메라 전원이 불안정하면 별도 powered USB hub를 검토하되, 제품화에서는 허브 사용을 최소화한다.

확인 명령 예시:

```bash
lsusb
rs-enumerate-devices
rs-depth-quality
```

### 5.2 Orbbec Femto Mega / Femto Mega I — USB 또는 PoE

USB 연결:

```text
[Orbbec Femto]
  └─ USB 3.x
       └─ Edge Board
```

PoE/Ethernet 연결:

```text
[Orbbec Femto Mega I]
  └─ Ethernet
       └─ PoE Switch 또는 PoE Injector
            └─ Edge Board Ethernet Port
```

권장사항:

- 천장 설치형은 PoE 모델을 우선 검토한다.
- 카메라망은 병원망/HIS/PACS망과 물리 또는 VLAN으로 분리한다.
- DHCP보다 static IP를 권장한다.
- 프레임 드롭, 패킷 손실, 링크 재협상 로그를 수집한다.

네트워크 예시:

```text
Camera VLAN: 10.20.30.0/24
Camera IP:   10.20.30.10
Edge Board:  10.20.30.2
Gateway:     none 또는 isolated router
```

### 5.3 Luxonis OAK-D Pro / OAK-D Pro PoE

USB 연결:

```text
[OAK-D Pro]
  └─ USB 3.x
       └─ Edge Board
```

PoE 연결:

```text
[OAK-D Pro PoE]
  └─ Ethernet
       └─ PoE Switch
            └─ Edge Board
```

권장사항:

- DepthAI SDK로 카메라 내부 pipeline을 구성한다.
- ROI 검출 모델을 카메라 내부 VPU에 배치하면 Edge Board 부하를 줄일 수 있다.
- 절대 거리 측정 정밀도는 별도 팬텀 테스트로 검증해야 한다.

---

## 6. 오디오 출력 하드웨어

호흡 안내 음성은 지연 시간이 촬영 타이밍에 영향을 주므로 일반 OS mixer 경로를 최소화한다.

권장 구성:

| 구성 | 권장 수준 | 비고 |
|---|---|---|
| USB Audio DAC | 권장 | 노이즈 감소, 교체 용이 |
| 3.5mm analog | PoC 가능 | 보드별 노이즈 주의 |
| HDMI audio | 비권장 | 디스플레이 의존성 큼 |
| ALSA direct | 권장 | 지연 최소화 |
| PulseAudio/PipeWire | PoC 가능 | 지연 변동성 검증 필요 |

권장 소프트웨어 경로:

```text
respiration_gating → audio_cue_service → GStreamer/ALSA → Speaker
```

GStreamer 예시:

```bash
gst-launch-1.0 filesrc location=hold_breath.wav ! wavparse ! audioconvert ! audioresample ! alsasink device=hw:1,0
```

---

## 7. X-ray 장비 연동 하드웨어

### 7.1 Phase 1 — Operator Assist

직접 전기 연결 없음.

```text
[Edge Board UI]
  └─ 추천 kVp/mAs 표시
       └─ 작업자가 X-ray console에 수동 입력
```

권장 이유:

- 의료기기 제어 리스크 최소화
- 장비 제조사 API 의존성 없음
- 초기 임상 workflow 관찰 가능
- 인허가 난이도 완화

### 7.2 Phase 2 — Workstation Agent

```text
[Edge Board]
  └─ TCP/gRPC/WebSocket
       └─ [Workstation Agent]
             └─ X-ray Console Software API 또는 UI Autofill
```

주의사항:

- 자동 입력이더라도 최종 촬영 전 작업자 승인 필요
- UI automation은 장비 SW 업데이트에 취약하므로 제품화에는 부적합할 수 있음
- API 사용 가능 여부를 장비 제조사와 계약/기술문서로 확보해야 함

### 7.3 Phase 3 — Generator Direct Control

```text
[Edge Board]
  └─ Isolated Interface Board
       ├─ RS-422 / CAN / Ethernet / GPIO Relay
       └─ X-ray Generator Interface
```

필수 조건:

- 장비 제조사 프로토콜 문서 확보
- 전기적 절연 회로 설계
- fail-safe 기본값 정의
- watchdog / interlock / emergency abort
- 의료기기 전기안전/EMC 시험 계획 수립
- 최종 촬영 전 작업자 승인 또는 독립 안전 인터락

---

## 8. 절연 및 인터페이스 보드 설계

직접 릴레이 연결은 개발 장비에서만 제한적으로 사용한다. 제품 후보 단계에서는 별도 interface board를 설계한다.

필수 설계 항목:

| 항목 | 요구사항 |
|---|---|
| Galvanic Isolation | 제어부와 X-ray 장비 회로 분리 |
| Opto-isolator / Digital Isolator | 신호 절연 |
| Relay / Solid-state Relay | 장비 입력 사양에 맞춤 |
| Surge Protection | TVS diode, fuse, current limit 검토 |
| Fail-safe Default | 전원/프로세스 장애 시 open 상태 |
| Watchdog | heartbeat 미수신 시 출력 차단 |
| Manual Override | 작업자 수동 모드 우선 |
| EMC | 노이즈 방출/내성 시험 계획 |

금지 표현:

- “100% 절연”
- “무조건 안전”
- “의료기기 인증 불필요”

권장 표현:

- “절연 내압, 누설전류, creepage/clearance, EMC 요구사항을 만족하도록 설계한다.”

---

## 9. 전원 설계

### 9.1 권장 전원 구성

```text
[Medical Grade AC Adapter or Isolated DC Supply]
  ├─ Edge Board
  ├─ Camera / PoE Switch
  ├─ Audio Amplifier
  └─ Interface Board(optional)
```

권장사항:

- Edge Board와 카메라 전원은 안정적인 전원 공급 장치를 사용한다.
- PoE 카메라 사용 시 PoE switch/injector의 전력 등급을 검증한다.
- 전원 차단/복구 시 서비스 자동 복구를 검증한다.
- UPS는 병원 정책과 장비 설치 조건에 따라 검토한다.

### 9.2 전원 이벤트 테스트

| 테스트 | 기대 결과 |
|---|---|
| 전원 순간 차단 | 안전 상태 복귀, 트리거 미발생 |
| PoE 링크 재협상 | 카메라 서비스 자동 재연결 |
| USB 전압 저하 | 오류 로그, UI 경고, 수동 모드 전환 |
| Edge Board 재부팅 | systemd 서비스 자동 복구 |

---

## 10. 기구/마운팅 설계

### 10.1 카메라 설치 위치

권장 위치:

- 촬영 테이블 상단 고정 마운트
- 환자 흉부 ROI가 안정적으로 들어오는 높이
- X-ray 조사 경로와 물리적으로 간섭하지 않는 위치
- 카메라가 환자 또는 작업자와 충돌하지 않는 위치

설치 시 체크:

- 카메라 광축과 테이블 평면의 각도
- ROI 영역 커버리지
- 케이블 장력/낙하 방지
- 알코올 소독 내성 또는 보호 하우징
- 열 배출 공간

### 10.2 캘리브레이션 마커

제품화 전에는 다음 중 하나를 준비한다.

- 평판 calibration plate
- known-height phantom block
- 체스트 호흡 팬텀
- 테이블 원점 측정 jig

---

## 11. 발열/환경 조건

장시간 촬영실 구동 기준:

| 항목 | 권장 기준 |
|---|---|
| Edge Board 온도 | 70°C 이하 유지 목표 |
| Camera 온도 | 제조사 권장 범위 유지 |
| Fan 제어 | PWM 기반 고정/자동 제어 |
| 온도 로그 | 1분 주기 이상 수집 |
| Thermal Throttling | 발생 시 UI 경고 및 로그 |

Jetson 확인 명령:

```bash
tegrastats
sudo nvpmodel -q
sudo jetson_clocks --show
```

Raspberry Pi 확인 명령:

```bash
vcgencmd measure_temp
vcgencmd get_throttled
```

---

## 12. 하드웨어 Bring-up 체크리스트

| 단계 | 체크 항목 | 완료 기준 |
|---|---|---|
| 1 | 보드 부팅 | OS 정상 부팅, SSH/로컬 콘솔 접근 |
| 2 | 카메라 인식 | SDK tool에서 device enumerate |
| 3 | Depth stream | 30 FPS 이상 안정 수신 |
| 4 | 오디오 출력 | 지연 측정, 음량 확인 |
| 5 | UI 출력 | HDMI/Display 정상 표시 |
| 6 | 저장소 | SQLite WAL 정상 기록 |
| 7 | Watchdog | 서비스 crash 후 자동 복구 |
| 8 | 네트워크 | PoE 카메라 static IP 연결 |
| 9 | 캘리브레이션 | 빈 베드 원점 측정 성공 |
| 10 | 안전 모드 | 카메라 오류 시 추천/트리거 비활성화 |

---

## 13. 제품화 전 하드웨어 검증 항목

- 8시간 이상 장시간 프레임 드롭 테스트
- 24시간 burn-in 테스트
- USB/PoE 케이블 탈착 테스트
- 보드 재부팅/카메라 재연결 테스트
- 온도 상승 테스트
- 조명 간섭 테스트
- X-ray 장비 주변 EMI 영향 관찰
- 환자복/시트/금속성 물체 반사 영향 검증
- 기구 고정 후 재캘리브레이션 반복성 검증

---

## 14. 하드웨어 선정 결론

초기 MVP는 `Raspberry Pi 5 또는 Jetson Orin Nano + Intel RealSense D455` 조합을 권장한다. 설치형 PoC에서는 천장 배선과 안정성을 고려하여 `Jetson Orin Nano + PoE Depth Camera` 구성을 검토한다. X-ray 장비 직접 제어는 초기 범위에서 제외하고, 별도 interface board와 위험관리 문서가 완료된 후 Phase 3로 분리한다.
