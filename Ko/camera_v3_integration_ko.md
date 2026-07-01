# 3D Depth 카메라 하드웨어 선정 및 보드 연동 구현 가이드 (V3)

작성 대상: 스마트 호흡 연동 및 체형 측정 시스템 아키텍트 / 시니어 개발자 / 임베디드 개발자  
문서 목적: 임상 환경에서 사용할 3D Depth 카메라를 선정하고, 실제 임베디드 보드와의 물리 연결, 드라이버, SDK, 통신 방식, 데이터 파이프라인, 장애 대응 기준까지 구현 가능한 수준으로 정의한다.

> 본 문서는 초기 MVP를 `Operator Assist`, 즉 환자 두께/호흡 안정성 측정 및 촬영 파라미터 추천 보조 단계로 전제한다. X-ray 제너레이터 직접 제어, 자동 조사 트리거, 온디바이스 지속 학습은 후속 고도화 단계로 분리한다.

---

## 1. 최종 카메라 선정 방향

### 1.1 단계별 추천

| 단계 | 추천 카메라 | 연결 방식 | 추천 보드 | 목적 |
|---|---|---|---|---|
| MVP / 알고리즘 검증 | Intel RealSense D455 | USB 3.x | Raspberry Pi 5 또는 Jetson Orin Nano | 흉부 ROI Depth 추적, 호흡 파형 검출, 두께 산출 |
| 설치형 PoC | Orbbec Femto Mega / Femto Mega I | USB 3.0 또는 Ethernet/PoE | Jetson Orin Nano, 산업용 PC, Raspberry Pi 5 | 천장 마운트, 장거리 배선, 산업용 설치성 검증 |
| AI 오프로딩 PoC | Luxonis OAK-D Pro / OAK-D Pro PoE | USB 3.0 또는 PoE | Raspberry Pi 5, Jetson Orin Nano | 카메라 내부 ROI 검출, 저전력 보드 연동 |
| 제품화 후보 | 1종 최종 선정 | USB보다 Ethernet/PoE 우선 검토 | Jetson Orin Nano 또는 산업용 x86 | 장시간 안정성, 케이블 내구성, 장애 복구성, 보안 검증 |

### 1.2 결론

초기 개발은 **Intel RealSense D455 + Raspberry Pi 5 / Jetson Orin Nano** 조합을 추천한다. SDK 생태계가 넓고 USB 기반 검증이 빠르며, Depth 프레임 처리 구조를 만들기 쉽다.

병원 천장 설치, 장거리 배선, 케이블 안정성이 중요해지는 단계에서는 **Orbbec Femto Mega I 또는 OAK-D Pro PoE**처럼 Ethernet/PoE 기반 카메라로 전환하는 것을 권장한다.

---

## 2. 3D 센싱 방식 비교

| 기술 방식 | 동작 원리 | 장점 | 단점 | 본 시스템 적합성 |
|---|---|---|---|---|
| Active IR Stereo | IR 패턴을 투사하고 좌/우 IR 카메라의 시차를 계산 | 실내 조명 변화에 비교적 강함, 다수의 SDK/예제 풍부, 호스트에서 다루기 쉬움 | 환자복 주름, 무광/무특징 표면에서 Depth Hole 가능 | MVP 1순위 |
| ToF | 변조된 IR 광원을 방출하고 반사 위상차로 거리 계산 | 표면 텍스처 영향이 적고 균일한 Depth 확보에 유리 | 다른 IR/ToF 장비와 간섭 가능, 멀티 카메라 동시 운용 시 주의 | 설치형 PoC 1순위 |
| Edge AI Stereo | 스테레오 Depth와 카메라 내부 VPU 추론 결합 | 보드 부하 감소, ROI 좌표만 전송 가능 | 절대 Depth 정밀도와 의료용 반복정확도 별도 검증 필요 | 저전력 PoC 후보 |

---

## 3. 보드별 권장 구성

### 3.1 Raspberry Pi 5 기준

| 구성 | 권장 여부 | 설명 |
|---|---:|---|
| Raspberry Pi 5 8GB | 권장 | MVP용 Depth 수집, UI, 로깅, TCP/HTTP API 처리 가능 |
| Raspberry Pi AI HAT+ 13/26 TOPS | 선택 | Hailo 기반 추론 가속용. Depth 카메라 드라이버와 직접 관련은 없으며, ROI 검출 모델을 Hailo로 올릴 때 사용 |
| NVMe SSD | 권장 | SD 카드 장시간 기록은 불안정하므로 로그/테스트 데이터는 NVMe 사용 권장 |
| 공식 Active Cooler | 필수 권장 | 장시간 Depth 스트리밍 시 발열로 인한 성능 저하 방지 |
| USB 3.0 포트 | 필수 | RealSense D455, OAK-D USB 모델 연결 시 필요 |
| Gigabit Ethernet | PoE 카메라 사용 시 필수 | Orbbec/OAK PoE 모델 사용 시 데이터 통신용 |

Raspberry Pi 5는 Python 기반 프로토타이핑에는 적합하지만, 실시간 UI, Depth 처리, 로그 저장, AI 추론을 동시에 수행하면 부하가 커질 수 있다. 따라서 장시간 PoC부터는 Jetson Orin Nano 또는 산업용 x86 PC를 함께 검토한다.

### 3.2 Jetson Orin Nano 기준

| 구성 | 권장 여부 | 설명 |
|---|---:|---|
| Jetson Orin Nano 8GB / Orin Nano Super | 강력 권장 | CUDA, TensorRT, LibTorch, ROS 2 기반 확장에 유리 |
| NVMe SSD | 필수 권장 | JetPack, SDK, 로그, 샘플 데이터 저장 |
| USB 3.x | 필수 | RealSense/OAK USB 연결 |
| Gigabit Ethernet | 권장 | Orbbec/OAK PoE 또는 병원 내부 장비 연동 |
| 팬/방열 설계 | 필수 | 24시간 운용 시 Thermal Throttling 방지 |

Jetson은 단순 카메라 수집보다 후속 단계인 TensorRT 추론, ROS 2 연동, 실시간 C++ 파이프라인, 카메라 다중화에 적합하다.

---

## 4. 카메라별 물리 연결 방법

## 4.1 Intel RealSense D455

### 물리 연결

| 항목 | 권장 구성 |
|---|---|
| 데이터 | USB 3.1 Gen 1 이상, Type-C to USB-A/C 케이블 |
| 전원 | USB 버스 파워 |
| 케이블 길이 | 안정성을 위해 1~2m 권장, 3m 이상은 액티브 USB 리피터 또는 산업용 USB 케이블 검토 |
| 장착 | 촬영 테이블 상부 또는 측면 고정 브라켓 |
| 권장 보드 | Raspberry Pi 5, Jetson Orin Nano, 산업용 x86 |

### 연결 구조

```text
[Intel RealSense D455]
        │ USB 3.x
        ▼
[Raspberry Pi 5 / Jetson Orin Nano]
        │
        ├─ Depth Frame 수집
        ├─ RGB/Depth Alignment
        ├─ 흉부 ROI 추출
        ├─ 호흡 Z축 파형 계산
        └─ UI / 로그 / 추천 파라미터 출력
```

### 드라이버 / SDK

| 항목 | 사용 |
|---|---|
| SDK | Intel RealSense SDK 2.0, `librealsense` |
| Python | `pyrealsense2` |
| C++ | `librealsense2` |
| ROS 2 | `realsense2_camera` |
| Linux 설치 방식 | Ubuntu 계열은 패키지 또는 소스 빌드. Raspberry Pi OS/Jetson은 커널 호환성 때문에 RSUSB 백엔드 또는 소스 빌드 권장 |

### 권장 설치 메모

Raspberry Pi 5나 Jetson에서 RealSense를 사용할 때는 커널 패치 방식보다 **RSUSB backend 기반 소스 빌드**가 유지보수에 유리하다. 병원 장비에 들어갈 제품은 커널 패치를 최소화해야 OS 업데이트와 보안 패치 적용이 쉽다.

예시 설치 흐름:

```bash
sudo apt update
sudo apt install -y git cmake build-essential libssl-dev libusb-1.0-0-dev pkg-config libgtk-3-dev

git clone https://github.com/IntelRealSense/librealsense.git
cd librealsense
mkdir build && cd build
cmake .. -DBUILD_EXAMPLES=true -DBUILD_PYTHON_BINDINGS=true -DFORCE_RSUSB_BACKEND=true
make -j$(nproc)
sudo make install
```

Python 확인:

```bash
python3 - <<'PY'
import pyrealsense2 as rs
ctx = rs.context()
print('devices:', len(ctx.devices))
for d in ctx.devices:
    print(d.get_info(rs.camera_info.name), d.get_info(rs.camera_info.serial_number))
PY
```

### 통신 방식

RealSense D455는 보드와 **USB/UVC + librealsense API**로 통신한다. 일반 TCP/IP 카메라가 아니므로, 카메라 자체 IP 설정은 없다.

애플리케이션 내부에서는 다음 구조를 사용한다.

```text
USB Camera Stream
  → librealsense Frame Queue
  → Depth/RGB Alignment
  → ROI Crop
  → Depth Temporal Filter
  → Breath Signal Extractor
  → Local IPC 또는 TCP API
```

---

## 4.2 Orbbec Femto Mega / Femto Mega I

### 물리 연결

| 항목 | Femto Mega | Femto Mega I |
|---|---|---|
| 데이터 | USB 3.0 또는 Ethernet | Ethernet 중심 |
| 전원 | 어댑터 또는 PoE 구성 확인 | PoE/산업용 전원 구성 확인 |
| 케이블 길이 | USB는 짧게, Ethernet은 장거리 유리 | Ethernet 장거리 설치에 유리 |
| 장착 | 천장/벽면 고정에 유리 | 산업용 하우징/IP 등급 모델은 설치형 PoC에 유리 |
| 권장 보드 | Jetson, 산업용 x86, Raspberry Pi 5 | Jetson, 산업용 x86 |

### 연결 구조: Ethernet/PoE 권장

```text
[Orbbec Femto Mega I]
        │ Ethernet / PoE
        ▼
[PoE Switch 또는 PoE Injector]
        │ Ethernet
        ▼
[Jetson Orin Nano / Industrial PC]
        │
        ├─ Orbbec SDK Depth Stream 수신
        ├─ Timestamp 동기화
        ├─ ROI Depth 처리
        ├─ 호흡 파형 계산
        └─ UI / 로그 / PACS/HIS와 분리된 내부 API
```

### 드라이버 / SDK

| 항목 | 사용 |
|---|---|
| SDK | Orbbec SDK |
| Azure Kinect 호환 | K4A Wrapper 사용 가능 여부 검토 |
| Python | Orbbec SDK Python wrapper 또는 C++ 서비스 후 gRPC/TCP로 전달 |
| C++ | Orbbec SDK C/C++ API 권장 |
| ROS 2 | `OrbbecSDK_ROS2` 계열 패키지 검토 |

### 통신 방식

Orbbec Femto Mega 계열은 모델/펌웨어/SDK 구성에 따라 USB 또는 Ethernet 스트리밍을 사용한다.

권장 통신 구조:

| 구간 | 방식 |
|---|---|
| 카메라 → 보드 | USB 3.0 또는 Ethernet streaming |
| 보드 내부 모듈 간 | ZeroMQ, Unix Domain Socket, shared memory 중 선택 |
| 보드 → UI | WebSocket 또는 REST API |
| 보드 → 로그 서비스 | 로컬 SQLite/PostgreSQL 또는 append-only log |
| 보드 → 외부 시스템 | 초기 MVP에서는 비활성화, 후속 단계에서 mTLS 기반 제한 연결 |

### 네트워크 설정 원칙

PoE 카메라는 병원망에 직접 연결하지 않고, 반드시 **전용 카메라 VLAN 또는 완전 분리된 로컬 스위치**를 사용한다.

권장 구성:

```text
[Camera VLAN: 192.168.50.0/24]
  - Camera: 192.168.50.10
  - Edge Board: 192.168.50.2
  - Gateway: 없음 또는 차단

[Hospital Network]
  - MVP 단계에서는 미연결
  - 필요 시 방화벽/라우터를 거쳐 단방향 또는 제한 통신
```

---

## 4.3 Luxonis OAK-D Pro / OAK-D Pro PoE

### 물리 연결

| 항목 | USB 모델 | PoE 모델 |
|---|---|---|
| 데이터 | USB 3.0 | Ethernet/PoE |
| 전원 | USB 버스 파워 | PoE Switch 또는 PoE Injector |
| 장점 | 개발이 쉬움 | 장거리 설치, 케이블 안정성 우수 |
| 권장 보드 | Raspberry Pi 5, Jetson | Raspberry Pi 5, Jetson, 산업용 x86 |

### 연결 구조

```text
[OAK-D Pro / OAK-D Pro PoE]
        │ USB 3.0 또는 PoE Ethernet
        ▼
[Raspberry Pi 5 / Jetson Orin Nano]
        │
        ├─ DepthAI Pipeline 실행
        ├─ Stereo Depth 생성
        ├─ 카메라 내부 VPU에서 ROI 검출 가능
        ├─ ROI 3D 좌표만 호스트로 전송 가능
        └─ 호흡 파형 / 두께 계산 / UI 출력
```

### 드라이버 / SDK

| 항목 | 사용 |
|---|---|
| SDK | Luxonis DepthAI |
| Python | `depthai` pip 패키지 |
| C++ | DepthAI C++ API |
| ROS 2 | `depthai-ros` |
| AI 모델 | OpenVINO blob 변환 후 카메라 내부 Myriad X/RVC 계열에서 추론 |

예시 설치:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install depthai opencv-python
```

장치 확인 예시:

```bash
python3 - <<'PY'
import depthai as dai
print(dai.Device.getAllAvailableDevices())
PY
```

### 통신 방식

OAK-D는 호스트에서 DepthAI pipeline을 정의하고, 카메라 내부에서 Depth/AI 연산을 수행한 뒤 결과 queue를 호스트로 전달한다.

```text
Host Python/C++ App
  → DepthAI Pipeline 생성
  → Camera Device에 Pipeline 업로드
  → Device 내부 StereoDepth / NeuralNetwork 실행
  → OutputQueue로 Depth, RGB, ROI, NN 결과 수신
```

OAK-D Pro PoE 모델은 네트워크 장치로 동작하므로, RealSense보다 설치형 구조에 유리하다. 단, 병원망 연결 전에는 카메라 discovery, IP 고정, 방화벽, 포트 허용 정책을 별도 검증해야 한다.

---

## 5. 권장 시스템 아키텍처

### 5.1 MVP 기본 구조

```text
[3D Depth Camera]
        │ USB 3.x 또는 Ethernet/PoE
        ▼
[Edge Board: Pi 5 / Jetson]
        │
        ├─ camera_service
        │   ├─ 프레임 수집
        │   ├─ Timestamp 부여
        │   ├─ Depth 품질 필터링
        │   └─ ROI Depth publish
        │
        ├─ breath_service
        │   ├─ 흉부 ROI Z값 추적
        │   ├─ 호흡 파형 생성
        │   ├─ Peak / Plateau / 움직임 감지
        │   └─ 안정 구간 판정
        │
        ├─ body_measure_service
        │   ├─ Empty Bed 기준점 보정
        │   ├─ 환자 두께 계산
        │   └─ kVp/mAs 추천값 산출
        │
        ├─ ui_service
        │   ├─ 실시간 파형 표시
        │   ├─ 추천 파라미터 표시
        │   ├─ 작업자 최종 승인 기록
        │   └─ Abort / 재안내 표시
        │
        └─ audit_log_service
            ├─ 모델/알고리즘 버전
            ├─ 카메라 Serial/Firmware
            ├─ 캘리브레이션 버전
            ├─ 추천값/승인값
            └─ 장애/프레임 드롭 기록
```

### 5.2 내부 통신 방식 선택

| 방식 | 장점 | 단점 | 권장 용도 |
|---|---|---|---|
| Python Queue / multiprocessing | 구현 쉬움 | 프로세스 분리 약함 | 초기 MVP |
| ZeroMQ PUB/SUB | 가볍고 빠름 | 메시지 스키마 직접 관리 필요 | camera_service → breath_service |
| gRPC | 스키마 명확, 언어 독립 | 오버헤드 있음 | C++ 카메라 서비스 + Python UI |
| Shared Memory | 고속 프레임 전달 | 구현 복잡 | 고해상도 Depth 프레임 처리 |
| ROS 2 DDS | 센서/로봇 생태계 강함 | 의료기기 제품화 시 구성 복잡 | 연구/PoC/다중 센서 검증 |
| WebSocket | UI 실시간 표시 쉬움 | 내부 처리용으로는 부적합 | UI 파형 표시 |

MVP에서는 `camera_service → breath_service`는 ZeroMQ 또는 multiprocessing Queue, `backend → UI`는 WebSocket을 권장한다. 제품화 단계에서는 C++ camera_service와 gRPC/Shared Memory 조합을 검토한다.

---

## 6. 카메라 데이터 표준 스키마

카메라 제조사가 달라도 상위 알고리즘이 동일하게 동작하도록 내부 표준 메시지 구조를 정의한다.

```json
{
  "schema_version": "1.0",
  "camera_vendor": "realsense|orbbec|luxonis",
  "camera_model": "D455|FemtoMegaI|OAK-D-Pro-PoE",
  "serial_number": "string",
  "firmware_version": "string",
  "timestamp_ns": 0,
  "frame_id": 0,
  "depth_width": 640,
  "depth_height": 480,
  "depth_unit": "mm",
  "roi": {
    "x": 0,
    "y": 0,
    "w": 0,
    "h": 0
  },
  "roi_depth_stats": {
    "median_mm": 0.0,
    "mean_mm": 0.0,
    "std_mm": 0.0,
    "valid_pixel_ratio": 0.0
  },
  "quality": {
    "frame_drop": false,
    "ir_saturation": false,
    "motion_artifact": false,
    "depth_hole_ratio": 0.0
  }
}
```

상위 알고리즘은 원본 Depth 전체 프레임이 아니라 `roi_depth_stats`와 품질 지표를 우선 사용한다. 개인정보 보호 및 성능을 위해 원본 프레임 저장은 기본 비활성화한다.

---

## 7. 카메라별 권장 프레임 설정

| 목적 | Depth 해상도 | FPS | 비고 |
|---|---:|---:|---|
| 호흡 파형 추적 | 640×480 | 30 FPS | MVP 기준 권장 |
| 두께 측정 | 640×480 또는 1280×720 | 15~30 FPS | 정적 측정은 FPS보다 정확도 우선 |
| UI 표시 | 원본 축소 | 15~30 FPS | UI 렌더링 부하 제한 |
| 고정밀 검증 | 최대 해상도 | 15 FPS 이상 | 장시간 프레임 드롭 확인 필요 |

호흡 연동은 30 FPS 기준으로 설계하되, 병원 장비와의 트리거 연동 단계에서는 프레임 수신 시간, 처리 시간, UI 표시 시간을 분리 측정해야 한다.

---

## 8. 설치 및 배선 설계

### 8.1 USB 카메라 연결 원칙

- USB 3.x 포트에 직접 연결한다.
- 저가 USB 허브 사용을 금지한다.
- 케이블은 쉴드 처리된 산업용 케이블을 사용한다.
- 3m 이상 연장 시 액티브 리피터 또는 USB-over-Ethernet 장비를 검토하되, 의료기기 EMC 테스트 대상에 포함한다.
- 보드 전원과 카메라 전원이 불안정하면 프레임 드롭이 발생하므로 보드 전원 어댑터 여유 용량을 확보한다.

### 8.2 PoE 카메라 연결 원칙

- PoE Switch 또는 PoE Injector를 사용한다.
- 병원 내부망과 분리된 전용 카메라망을 구성한다.
- 카메라 IP를 고정한다.
- 카메라 discovery가 broadcast/multicast를 사용하는 경우 VLAN/방화벽에서 차단되지 않는지 확인한다.
- 장비실/촬영실 간 케이블은 Cat6 이상을 권장한다.
- 전원 차단 후 재부팅 시 카메라가 자동 복구되는지 테스트한다.

### 8.3 권장 네트워크 구성

```text
[Camera PoE Network]
  Camera: 192.168.50.10
  Edge Board eth0: 192.168.50.2
  Subnet: 255.255.255.0
  Gateway: none
  Internet: blocked

[Maintenance Network, optional]
  Edge Board eth1 or Wi-Fi: disabled by default
  Only enabled during signed offline update
```

---

## 9. 드라이버/SDK 선택 기준

| 카메라 | 1차 SDK | 2차/호환 SDK | ROS 2 | 제품화 권장 언어 |
|---|---|---|---|---|
| RealSense D455 | librealsense | pyrealsense2 | realsense2_camera | C++ camera_service + Python UI |
| Orbbec Femto Mega | Orbbec SDK | K4A Wrapper 가능성 검토 | OrbbecSDK_ROS2 | C++ camera_service |
| OAK-D Pro | DepthAI | OpenVINO blob pipeline | depthai-ros | Python MVP, C++ 제품화 |

### 9.1 제품화 시 공통 원칙

- 카메라 SDK는 애플리케이션 전체에 직접 퍼뜨리지 않고 `camera_service`에 격리한다.
- 상위 모듈은 제조사 SDK 타입을 직접 참조하지 않는다.
- SDK 버전, 펌웨어 버전, 카메라 Serial을 Audit Log에 남긴다.
- SDK 업데이트는 모델 업데이트와 동일하게 Signed Package로 관리한다.
- 특정 카메라 장애 시 대체 카메라를 연결할 수 있도록 내부 메시지 스키마를 고정한다.

---

## 10. 데이터 처리 파이프라인

### 10.1 Depth 전처리

```text
Raw Depth
  → Invalid Pixel 제거
  → Depth Range Gate 적용
  → Temporal Filter
  → Spatial Median Filter
  → ROI Crop
  → Outlier 제거
  → Median / IQR / Std 계산
  → Breath Signal 생성
```

### 10.2 호흡 파형 계산

- 흉부 ROI의 Depth median 값을 사용한다.
- 단순 mean은 환자복 주름과 Depth hole에 취약하므로 median 또는 trimmed mean을 기본값으로 한다.
- `valid_pixel_ratio`가 기준치 이하이면 해당 프레임은 호흡 판정에서 제외한다.
- `dZ/dt`와 `d²Z/dt²`를 함께 사용하여 기침, 움직임, 테이블 이동을 분리한다.

### 10.3 두께 계산

```text
Empty Bed Calibration Depth = Z_bed
Patient Surface Depth = Z_patient
Thickness = Z_bed - Z_patient
```

주의:

- 카메라 좌표계와 촬영 테이블 좌표계를 반드시 Extrinsic Calibration으로 정렬한다.
- 테이블 높이가 움직이는 장비라면 Empty Bed 기준만으로는 부족하고, 테이블 높이 센서 또는 주기적 재캘리브레이션이 필요하다.
- 두께값은 kVp/mAs 자동 입력값이 아니라 추천값의 근거 데이터로 사용한다.

---

## 11. 캘리브레이션 절차

### 11.1 설치 시 1회 캘리브레이션

| 항목 | 방법 |
|---|---|
| Intrinsic 확인 | SDK 제공 캘리브레이션 값 확인 |
| Extrinsic 보정 | 평판 보드/Calibration Plate로 테이블 평면과 카메라 좌표 정렬 |
| Depth Scale 검증 | 50mm, 100mm, 200mm 블록으로 실제 거리 오차 확인 |
| ROI 기준점 | 촬영 자세별 흉부 ROI 위치 템플릿 생성 |
| 조명 간섭 확인 | 촬영실 조명 ON/OFF, 주변 장비 ON/OFF 조건에서 Depth 품질 확인 |

### 11.2 매일 또는 장비 시작 시 캘리브레이션

- Empty Bed 상태에서 기준 Depth Plane을 측정한다.
- Depth hole ratio와 valid pixel ratio를 확인한다.
- 기준 오차가 허용범위를 벗어나면 장비 사용을 막고 재캘리브레이션을 요구한다.
- 캘리브레이션 결과와 버전을 Audit Log에 저장한다.

---

## 12. 장애 대응 및 Fail-safe

| 장애 | 감지 방법 | 대응 |
|---|---|---|
| 카메라 미연결 | SDK device count = 0 | UI에 사용 불가 표시, 일반 촬영 모드 전환 |
| USB 대역폭 부족 | FPS 저하, frame drop 증가 | 해상도/FPS 낮춤, 케이블/포트 점검 |
| Depth hole 증가 | valid_pixel_ratio 감소 | ROI 재설정, 환자복/조명 확인 |
| IR 포화 | SDK metadata 또는 depth 품질 지표 | IR emitter 조정, 조명 환경 점검 |
| 네트워크 카메라 끊김 | heartbeat timeout | 재연결 3회 시도 후 수동 모드 전환 |
| 보드 과열 | CPU/GPU 온도 임계치 초과 | 추론 중지, FPS 제한, 경고 표시 |
| 카메라 시간 불일치 | timestamp jump | 해당 구간 판정 제외, 로그 기록 |
| SDK crash | watchdog timeout | camera_service 재시작, 촬영 추천 기능 비활성화 |

중요: 카메라 장애가 발생해도 X-ray 장비 자체의 기본 수동 촬영 워크플로우를 방해하면 안 된다. 본 시스템은 MVP 단계에서 “보조 시스템”으로 동작해야 한다.

---

## 13. 보안 및 개인정보 처리

### 13.1 원본 프레임 저장 정책

- 기본값: 원본 RGB/Depth 프레임 저장 금지.
- 디버그 모드: 비식별화 후 제한 저장.
- 저장 시: 환자 식별자 제거, 얼굴/두부 ROI 제거, 저장 기간 제한, 암호화 저장.
- 운영 모드: ROI 통계값과 감사 로그만 저장.

### 13.2 카메라망 보안

- PoE 카메라는 병원망과 분리한다.
- 기본 관리자 비밀번호가 있는 장비는 즉시 변경한다.
- SSH, Telnet, Web Admin, Debug 포트는 비활성화한다.
- 펌웨어 업데이트는 서명 검증된 오프라인 패키지만 허용한다.
- 카메라 Serial, Firmware, SDK 버전을 로그에 기록한다.

---

## 14. 테스트 계획

### 14.1 정적 정확도 테스트

| 테스트 | 기준 예시 |
|---|---|
| 평판 거리 반복 측정 | 동일 거리 100회 측정 시 표준편차 기준 설정 |
| 두께 블록 측정 | 50/100/200mm 블록 오차 측정 |
| 테이블 높이 변화 | 높이별 Empty Bed 보정 정확도 확인 |
| ROI 위치 변화 | 환자 위치가 조금 바뀌어도 결과 안정성 확인 |

### 14.2 동적 호흡 팬텀 테스트

- 스텝모터 또는 리니어 액추에이터로 5~50mm 범위의 상하 움직임을 생성한다.
- 주기 2초, 4초, 6초, 불규칙 패턴을 재생한다.
- 알고리즘이 Peak, Plateau, 움직임 중단 시점을 올바르게 검출하는지 확인한다.
- 카메라별 latency와 frame jitter를 비교한다.

### 14.3 장시간 안정성 테스트

| 항목 | 기준 예시 |
|---|---|
| 연속 스트리밍 | 최소 8시간, 제품화 전 72시간 이상 |
| Frame drop | 기준치 이하 유지 |
| 온도 | 보드/카메라 온도 로그 |
| 메모리 누수 | camera_service RSS 증가량 확인 |
| 자동 복구 | 케이블 분리/재연결 후 복구 여부 |

---

## 15. 실제 개발 순서

### Step 1. D455 USB MVP

1. Raspberry Pi 5 또는 Jetson Orin Nano 준비
2. librealsense 설치
3. D455 연결 확인
4. Depth frame 수집
5. ROI median depth 계산
6. 호흡 파형 UI 표시
7. Empty Bed 캘리브레이션 구현
8. 추천 kVp/mAs는 UI에만 표시

### Step 2. 카메라 추상화 계층 구현

```python
class DepthCamera:
    def open(self): ...
    def close(self): ...
    def get_frame(self): ...
    def get_intrinsics(self): ...
    def get_device_info(self): ...
```

각 제조사 SDK는 이 인터페이스 뒤에 숨긴다.

### Step 3. PoE 카메라 PoC

1. Orbbec 또는 OAK-D PoE 설치
2. 전용 카메라 VLAN 구성
3. 고정 IP 설정
4. 장시간 스트리밍 테스트
5. USB 대비 latency/jitter 비교
6. 천장 마운트 환경에서 ROI 안정성 검증

### Step 4. 제품화 전환

1. C++ camera_service 분리
2. watchdog / systemd service 등록
3. SDK/펌웨어 버전 고정
4. Offline update 패키지 설계
5. 감사로그 무결성 적용
6. 의료기기 위험관리 문서와 연결

---

## 16. systemd 서비스 예시

```ini
[Unit]
Description=Depth Camera Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=smartxray
WorkingDirectory=/opt/smartxray
ExecStart=/opt/smartxray/venv/bin/python /opt/smartxray/services/camera_service.py
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

---

## 17. 권장 최종 구현 조합

### MVP 추천

```text
Camera: Intel RealSense D455
Board: Raspberry Pi 5 8GB 또는 Jetson Orin Nano 8GB
Connection: USB 3.x direct
SDK: librealsense + pyrealsense2
Internal IPC: Python multiprocessing Queue 또는 ZeroMQ
UI: Local Web UI + WebSocket
Storage: NVMe SSD
```

### 설치형 PoC 추천

```text
Camera: Orbbec Femto Mega I 또는 OAK-D Pro PoE
Board: Jetson Orin Nano / Industrial x86
Connection: PoE Ethernet through isolated camera switch
SDK: Orbbec SDK 또는 DepthAI
Internal IPC: C++ camera_service + gRPC/ZeroMQ
UI: Local Web UI
Storage: encrypted NVMe SSD
```

### 제품화 후보

```text
Camera: 장시간 테스트 후 1종 고정
Board: Jetson Orin Nano Industrial 또는 산업용 x86
Connection: Ethernet/PoE 우선
Service: C++ camera_service + watchdog
Security: Secure Boot, Signed Update, mTLS, RBAC
Validation: 팬텀 테스트 + 장시간 테스트 + 장애 주입 테스트
Regulatory: ISO 14971 위험관리, IEC 62304 소프트웨어 수명주기, ISO 13485 품질문서 연계
```

---

## 18. README V5에 반영할 요약 문구

본 시스템의 초기 카메라 구성은 Intel RealSense D455를 기준으로 하며, Raspberry Pi 5 또는 Jetson Orin Nano와 USB 3.x로 직접 연결한다. 카메라 드라이버는 librealsense SDK를 사용하되, 보드별 커널 호환성을 고려해 RSUSB backend 기반 소스 빌드를 우선 검토한다. 설치형 PoC 단계에서는 천장 마운트 및 장거리 배선을 고려하여 Orbbec Femto Mega I 또는 Luxonis OAK-D Pro PoE와 같은 Ethernet/PoE 기반 카메라를 검토한다. 모든 카메라 입력은 제조사 SDK에 직접 종속되지 않도록 `camera_service` 계층에서 표준 Depth 메시지로 변환하고, 상위 호흡 분석 및 체형 측정 모듈은 표준화된 ROI Depth 통계값만 사용한다.

