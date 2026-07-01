# tech-stack-assessment.md — 기술스택 현황, 준비물, 문제점 분석

작성 대상: 시니어 개발자, 시스템 아키텍트, 임베디드 엔지니어, RA/QA  
작성 기준일: 2026-06-24  
관련 문서: `README.md`, `docs/camera.md`, `docs/hardware.md`, `docs/deployment.md`, `docs/regulatory.md`

> **목적**: 본 시스템에 사용되는 하드웨어와 소프트웨어 스택의 현재 공급/유지보수 상태, 이 프로젝트에 직접 영향을 주는 알려진 기술적 문제점, 의료기기 제품화 리스크, 권장 조치를 한 곳에서 추적한다. 정기 검토 주기: **분기 1회**. 이 문서의 내용은 `risk-management.md`와 연동한다.

---

## 목차

1. [하드웨어 — 3D Depth 카메라](#1-하드웨어--3d-depth-카메라)
2. [하드웨어 — 엣지 보드](#2-하드웨어--엣지-보드)
3. [소프트웨어 — 카메라 SDK](#3-소프트웨어--카메라-sdk)
4. [소프트웨어 — AI 추론 런타임](#4-소프트웨어--ai-추론-런타임)
5. [소프트웨어 — IPC / 프로세스 간 통신](#5-소프트웨어--ipc--프로세스-간-통신)
6. [소프트웨어 — API 게이트웨이 / 백엔드](#6-소프트웨어--api-게이트웨이--백엔드)
7. [소프트웨어 — 데이터베이스 / 감사로그](#7-소프트웨어--데이터베이스--감사로그)
8. [소프트웨어 — Operator UI 런타임](#8-소프트웨어--operator-ui-런타임)
9. [리스크 종합 매트릭스](#9-리스크-종합-매트릭스)
10. [단계별 결정 사항](#10-단계별-결정-사항)
11. [검토 이력](#11-검토-이력)

---

## 상태 범례

| 아이콘 | 의미 |
|---|---|
| ✅ | 안정, 활발 유지보수, 의료기기 사용 권장 |
| ⚠️ | 주의 필요, 조건부 사용 가능 |
| 🔴 | 고위험, 사용 전 대안 검토 필수 |
| 🔁 | 대전환 진행 중, 버전 고정 필수 |
| 📌 | MVP 한정 사용, 제품화 전 교체 검토 |

---

## 1. 하드웨어 — 3D Depth 카메라

---

### 1.1 Intel RealSense D455

**상태**: ⚠️ **2025.07 Intel에서 분사, 독립 회사 전환**  
**역할**: MVP 기준 카메라  
**연결**: USB 3.x (Type-C)  
**측심 방식**: Active IR Stereo (구조광 스테레오)

#### 준비물 및 구성

| 항목 | 사양 |
|---|---|
| Depth 해상도 | 최대 1280×720 @ 30 FPS (Z16) |
| RGB 해상도 | 1280×800 @ 30 FPS (선택적 사용) |
| 시야각 (Depth) | 87° × 58° |
| 깊이 범위 | 0.6m ~ 6.0m |
| 연결 | USB 3.1 Gen 1 이상, Type-C |
| IMU | 내장 (6-DoF) |
| 전원 | USB 버스 파워 (~2.1W) |
| 케이블 권장 길이 | 1m 이내 안정, 3m 이상 시 액티브 리피터 필요 |

#### 알려진 문제점 및 기술적 리스크

1. **분사 리스크**: 2025년 7월 11일 Intel에서 독립, 시리즈 A $50M 유치(약 130명 규모 신생사). 단기 안정성은 확보되었으나 장기 공급(7~10년)은 불확실. GitHub 저장소도 `IntelRealSense/librealsense` → `realsenseai/librealsense`로 이전됨(빌드 스크립트의 clone URL 갱신 필요).

2. **JetPack 6.x USB 메타데이터 버그**: JetPack 6.0/6.1 환경에서 USB 3.x 연결 시 프레임 메타데이터(하드웨어 타임스탬프, 센서 온도)가 누락되는 버그가 보고됨. JetPack 6.2 + librealsense 최신 빌드에서 수정 확인. **JetPack 6.2 미만 환경에서는 반드시 검증 필요.**

3. **USB 2.0 폴백 무감지**: librealsense가 USB 3.x 포트에 연결되어 있어도 케이블/허브 품질에 따라 USB 2.0 모드로 폴백될 수 있으며, 이 경우 해상도/FPS가 크게 제한됨에도 오류 없이 동작. **부팅 시 `rs-enumerate-devices -s`로 USB 속도 확인 필수.**

4. **환자복/무광 표면에서 Depth Hole**: 면/기능성 의류는 Active IR Stereo의 구조광 패턴을 흡수해 valid_pixel_ratio 저하 유발. 임상 조건에서 실측 검증 필요.

5. **멀티 카메라 IR 간섭**: 동일 공간에 D455 2대 이상 운용 시 IR 패턴 간 간섭. 본 시스템은 단일 카메라 구성이므로 직접 영향은 없으나, 인접 촬영실에 동일 카메라가 있으면 검증 필요.

6. **케이블 길이 제약 (천장 설치)**: 천장 마운트 설치 시 2m 이상 USB 케이블이 필요할 수 있음. 3m 이상에서는 전력 공급 불안정으로 프레임 드롭 발생. 산업용 USB 액티브 리피터 또는 PoE 카메라 전환 검토.

#### 의료기기 제품화 리스크

| 리스크 항목 | 수준 | 대응 |
|---|---|---|
| 장기 공급 불확실 | ⚠️ 중간 | 카메라 추상화 계층(HAL) 설계, 대안 카메라 병행 검증 |
| SDK 저장소 이전 | ⚠️ 낮음 | 빌드 URL 업데이트, vendoring |
| USB 폴백 무감지 | ⚠️ 중간 | 시작 시 USB 속도 검증 로직 필수 구현 |
| 환자복 Depth Hole | ⚠️ 중간 | valid_pixel_ratio 임계값으로 캘리브레이션 보정 |

#### 권장 조치

- librealsense를 `realsenseai/librealsense` 기준으로 클론 URL 업데이트.
- JetPack 6.2 + librealsense 최신 릴리스로 SDK 버전 고정 후 vendoring.
- 시작 시 USB 속도 자동 검증(`rs-enumerate-devices`) 로직을 `camera_service` 초기화에 포함.
- D555 PoE 신규 모델 평가(천장 설치형 PoC 단계에서 전환 검토).

---

### 1.2 Orbbec Femto Mega / Femto Mega I

**상태**: ✅ **활발 유지보수, 설치형 PoC 1순위 후보**  
**역할**: 설치형 PoC, 천장 마운트  
**연결**: USB 3.0 또는 Ethernet/PoE  
**측심 방식**: iToF (indirect Time-of-Flight)

#### 준비물 및 구성

| 항목 | Femto Mega | Femto Mega I |
|---|---|---|
| Depth 해상도 | 최대 1024×1024 @ 15 FPS | 동일 |
| RGB 해상도 | 3840×2160 (4K) | 동일 |
| 연결 | USB 3.0 또는 Ethernet | Ethernet 중심 (PoE 지원) |
| 방진·방수 | 없음 | IP65 등급 |
| 내장 보드 | Jetson Nano (구형) | - |
| SDK | Orbbec SDK v2 (공식 지원) | 동일 |
| Azure Kinect 호환 | K4A Wrapper 제공 | 동일 |

#### 알려진 문제점 및 기술적 리스크

1. **Orbbec SDK v1 → v2 단절**: SDK v2(2024년 10월 공개)는 v1과 OpenNI 프로토콜이 호환되지 않음. Gemini 335Lg 이후 신규 제품은 v2 전용. **레거시 코드나 예제가 v1 기준이면 v2로 포팅 필요.**

2. **K4A Wrapper 제약**: Azure Kinect SDK 호환 래퍼(OrbbecSDK-K4A-Wrapper)는 원본 SDK와 별도 저장소·릴리스 주기로 관리됨. 마이크 어레이 제거, 일부 고급 기능 미지원. **제품화 기준으로는 네이티브 Orbbec SDK v2 직접 사용 권장, K4A Wrapper는 레거시 파이프라인 재사용 목적에만 한정.**

3. **iToF IR 간섭**: 동일 공간에 ToF 장비(다른 Femto, RealSense L-시리즈 등)가 있으면 crosstalk 발생 가능. X-ray 장비 주변 IR 노이즈 환경에서 별도 검증 필요.

4. **PoE 카메라 네트워크 지연/패킷 손실**: Ethernet 스트리밍은 USB 대비 네트워크 지연·jitter 발생 가능. 전용 카메라 VLAN 구성과 HIL 테스트에 reconnect 시나리오 포함 필수.

5. **Femto Mega 내장 Jetson Nano (구형) 독립 운용**: Femto Mega는 Jetson Nano를 내장해 온디바이스 처리가 가능하나, 내장 보드는 구형 Jetson Nano 4GB(JetPack 4.x 계열)임. **본 시스템의 엣지 보드(Orin Nano)와 별개로 보고, 내장 보드 기능은 사용하지 않는 것을 기본으로 한다.**

#### 의료기기 제품화 리스크

| 리스크 항목 | 수준 | 대응 |
|---|---|---|
| SDK v1/v2 혼용 | ⚠️ 중간 | v2 전용으로 고정 |
| K4A Wrapper 의존 | ⚠️ 낮음 | 네이티브 v2 API 사용 |
| IR crosstalk | ⚠️ 중간 | 설치 환경 실측 검증 |
| PoE reconnect | ⚠️ 낮음 | HIL 테스트 포함 |

#### 권장 조치

- Orbbec SDK v2 특정 릴리스로 고정, `configs/camera_profile.orbbec.yaml`에 버전 기록.
- PoE 연결 reconnect 시나리오를 HIL 테스트(FI-002)에 포함.
- Femto Mega I (IP65) 는 천장 마운트 설치형 제품화 후보로 우선 평가.

---

### 1.3 Luxonis OAK-D Pro / OAK-D Pro PoE

**상태**: 🔁 **SDK v2 → v3 대전환 진행 중 (2025.09 v3 정식 출시)**  
**역할**: AI 오프로딩 PoC (카메라 내부 ROI 추론)  
**연결**: USB 3.0 또는 Ethernet/PoE  
**측심 방식**: Active Stereo (Structured Light + Neural Depth)

#### 준비물 및 구성

| 항목 | OAK-D Pro | OAK-D Pro PoE |
|---|---|---|
| Depth 방식 | Active IR Stereo (Pro IR 프로젝터) | 동일 |
| AI 가속 | Intel Myriad X VPU (RVC2, 4 TOPS) | 동일 |
| 연결 | USB 3.0 | Ethernet/PoE (IEEE 802.3af) |
| SDK | depthai-core v3 (2025.09~) | 동일 |
| 모델 포맷 | .superblob (Myriad X FP16) | 동일 |

#### 알려진 문제점 및 기술적 리스크

1. **DepthAI SDK v2 → v3 브레이킹 체인지**: v3.0.0이 2025년 9월 8일 정식 출시. `ColorCamera`·`MonoCamera` 노드가 통합 `Camera` 노드로 교체. v2 기반 파이프라인 코드는 v3와 호환되지 않음. **v2 기반 검증된 코드는 `v2_stable` 브랜치로 고정, 신규 개발은 v3 기준.**

2. **depthai-sdk 라이브러리는 v3 비호환**: 고수준 헬퍼 라이브러리인 `depthai-sdk`(pip)는 v3 API와 호환되지 않으며 v3 API로 통합 예정. **`depthai-sdk`와 `depthai-core` 혼용 금지, v3에서는 `depthai-core` 단독 사용.**

3. **OpenVINO blob 포맷 제약**: OAK-D Pro(RVC2/Myriad X)는 `.superblob` 포맷 사용. blobconverter(이전 변환 도구)는 deprecated 예정이며 `modelconverter` + HubAI SDK로 대체됨. **HubAI SDK는 클라우드 서비스 의존 → 폐쇄망 환경에서는 x86 개발 머신에서 오프라인 변환 후 산출물 반입 필요.**

4. **RVC4(OAK4) vs RVC2(OAK-D Pro) 세대 혼동**: OAK4 시리즈(RVC4, Qualcomm NPU 기반)는 전혀 다른 아키텍처임. OAK-D Pro는 RVC2(Myriad X) 기반이며 두 세대의 모델 포맷(.superblob vs 새 포맷)이 호환되지 않음. **문서와 코드에서 세대를 명시적으로 구분.**

5. **Depth 절대 정확도 의료용 검증 필요**: VPU 기반 신경망 Depth는 절대 거리 정확도가 가변적임. 흉부 두께 측정 용도에서 반복정확도와 절대 오차는 별도 팬텀 테스트로 검증 필수.

#### 의료기기 제품화 리스크

| 리스크 항목 | 수준 | 대응 |
|---|---|---|
| SDK 대전환 | 🔴 높음 | v2 고정 또는 v3 신규 채택 후 전체 재검증 |
| 클라우드 의존 변환 도구 | ⚠️ 중간 | x86 오프라인 변환 파이프라인 구축 |
| Depth 절대 정확도 | ⚠️ 중간 | 팬텀 테스트 필수 |

#### 권장 조치

- v2 기반 검증이 완료된 경우 `v2_stable` 고정 vendoring.
- 신규 채택 시 v3 기준으로 시작하되, 첫 통합 전 모든 파이프라인 노드 재검증.
- 오프라인 blob/superblob 변환 파이프라인을 x86 CI 환경에 구축, 산출물만 장비 반입.

---

## 2. 하드웨어 — 엣지 보드

---

### 2.1 Raspberry Pi 5 8GB

**상태**: ✅ **안정, MVP 기준**  
**역할**: Phase 1 MVP 엣지 보드

#### 준비물 및 구성

| 항목 | 사양 |
|---|---|
| CPU | Cortex-A76 4-core @ 2.4GHz |
| RAM | 8GB LPDDR4X |
| USB | USB 3.0 × 2 (900mA per port) |
| 스토리지 | NVMe SSD 권장 (SD Card PoC 한정) |
| AI 가속 | Raspberry Pi AI HAT+ (Hailo-8L 13 TOPS / Hailo-8 26 TOPS, 선택) |
| 전원 | USB-C PD 5V/5A (27W) |
| 냉각 | Active Cooler 필수 (장시간 구동) |
| OS 권장 | Raspberry Pi OS 64-bit Bookworm 또는 Ubuntu 22.04 ARM64 |

#### 알려진 문제점 및 기술적 리스크

1. **GIL 제약 (Python 멀티코어 활용 불가)**: Python 3.11 기준 GIL은 CPU 연산을 단일 코어로 제한. Depth 처리 + WebSocket + 로그 저장 + AI 추론을 동시에 Python 단일 프로세스로 구동하면 부하 집중. **multiprocessing 또는 C++ 서비스 분리로 대응.**

2. **USB 3.0 포트 전력 공급 한계**: Pi 5의 USB 3.0 포트는 포트당 최대 600mA. RealSense D455는 피크 전류 ~900mA 요구 가능. 전원 어댑터 여유 용량 부족 시 프레임 드롭·연결 불안정 발생. **보드 전원 어댑터 27W 이상, 필요 시 외부 전원 공급 허브 사용.**

3. **AI HAT+ (Hailo)는 Depth 카메라 드라이버가 아님**: AI HAT+는 Hailo NPU로 AI 추론만 가속. librealsense, Orbbec SDK, DepthAI SDK와 직접적인 관계 없음. **문서에서 카메라 연결과 AI 가속을 혼동하지 말 것.**

4. **Hailo 모델 변환 도구 x86 전용**: Hailo Dataflow Compiler(HDF)는 x86 Linux 전용. Raspberry Pi에서 직접 모델을 컴파일할 수 없음(HEF 파일은 x86 개발 머신에서 생성 후 배포). 폐쇄망 환경에서 x86 CI/빌드 서버 확보 필요.

5. **Chromium 키오스크 Wayland 버그**: Raspberry Pi OS Bookworm 기본 컴포지터(labwc)에서 HDMI 신호 끊김/해상도 변경 시 Chromium 전체화면이 풀리는 버그 보고. **키오스크 UI 사용 시 `cage` 컴포지터 권장.**

6. **NVMe SSD 없이 장시간 기록 불안정**: SD Card는 기록 내구성이 낮고, 감사로그 연속 기록 환경에서 TBW(Total Bytes Written) 초과 위험. **NVMe SSD 필수.**

#### 의료기기 제품화 리스크

| 리스크 항목 | 수준 | 대응 |
|---|---|---|
| USB 전력 한계 | ⚠️ 중간 | 전원 어댑터 용량 확인, 외부 허브 검토 |
| Hailo x86 전용 컴파일 | ⚠️ 중간 | x86 CI 빌드 서버 확보 |
| Wayland 키오스크 버그 | ⚠️ 낮음 | cage 컴포지터 사용 |
| 제품화 연산 한계 | 📌 낮음 | Phase 2 이상은 Jetson 전환 |

---

### 2.2 NVIDIA Jetson Orin Nano 8GB / Orin Nano Super

**상태**: ✅ **안정, JetPack 6.2 기준 제품화 권장**  
**역할**: Phase 2 이상 기준 보드, 실시간 추론 + 고속 Depth 처리

#### 준비물 및 구성

| 항목 | Orin Nano 8GB | Orin Nano Super |
|---|---|---|
| CPU | Cortex-A78AE 6-core | 동일 |
| GPU | Ampere, 1024 CUDA cores | 동일 (클럭 업) |
| AI TOPS | 40 TOPS (기본 모드) | 67 TOPS (Super Mode, JetPack 6.2) |
| RAM | 8GB LPDDR5 (CPU/GPU 공유) | 동일 |
| JetPack 권장 | 6.2 | 6.2 (Super Mode 활성화) |
| TensorRT | 10.3 | 동일 |
| 스토리지 | NVMe SSD 256GB 이상 권장 | 동일 |

#### 알려진 문제점 및 기술적 리스크

1. **TensorRT 10.x 브레이킹 체인지 (가장 중요)**: JetPack 6.x는 TensorRT 10.x 기반. TRT 8.x → 10.x 마이그레이션 시 **다음 변경 사항이 코드 수정을 강제**함:
   - Implicit batch 완전 제거 → Explicit batch 전용
   - `enqueueV2` 제거 → `enqueueV3` 사용
   - 바인딩 인덱스 API 제거 → 이름 기반 텐서 API(`getIOTensorName`, `setTensorAddress`)
   - `Dims` 타입이 int32 → int64 변경
   - IPluginV2 계열 deprecated(TRT 11.0에서 완전 제거) → IPluginV3 마이그레이션 권장
   - 기존 `.engine` 파일 재빌드 필수(버전·아키텍처 간 호환 없음)

2. **ONNX Runtime TensorRT EP 의존성 정합**: JetPack 6.x + `onnxruntime-gpu` pip wheel 설치 시 CUDA EP만 노출되고 TensorRT EP가 활성화되지 않는 사례 다수 보고. **JetPack 버전, TensorRT 버전, ONNX Runtime 버전을 매트릭스로 관리하고 소스 빌드 적용 필요.**

3. **jetson_clocks는 제품화에 부적합**: `jetson_clocks`로 클럭을 고정하면 발열 및 팬 소음이 증가. 병원 촬영실 24시간 운용 환경에서는 `nvpmodel` 기반 프로파일을 사전 검증 후 고정. 성능 측정은 개발 환경에서만 `jetson_clocks` 사용.

4. **공유 메모리(CPU + GPU)**: Orin Nano는 CPU와 GPU가 동일 LPDDR5 풀을 공유. camera_service + depth_processor + TensorRT 추론이 동시에 메모리를 할당하면 peak 사용량이 8GB 한계에 접근할 수 있음. **메모리 사용량 프로파일링 및 max_workspace_size(TensorRT) 튜닝 필요.**

5. **Super Mode는 별도 하드웨어가 아님**: Orin Nano Super는 기존 Orin Nano 8GB에 JetPack 6.2 Super Mode 펌웨어를 적용한 것. 기존 Orin Nano 8GB 보드도 JetPack 6.2 플래싱으로 Super Mode 활성화 가능.

#### 의료기기 제품화 리스크

| 리스크 항목 | 수준 | 대응 |
|---|---|---|
| TRT 10.x 코드 마이그레이션 | 🔴 높음 | 신규 코드는 TRT 10.x API로 작성, 기존 엔진 재빌드 |
| ONNX Runtime TRT EP 설치 | ⚠️ 중간 | 소스 빌드, 버전 매트릭스 문서화 |
| jetson_clocks 제품 사용 | ⚠️ 중간 | nvpmodel 프로파일로 대체 |
| 메모리 한계 | ⚠️ 중간 | 메모리 프로파일링, TRT workspace 튜닝 |

#### 권장 조치

- TensorRT 엔진 빌드 파이프라인을 자동화하고 `.engine` 파일은 JetPack/TRT 버전 태그와 함께 `models/manifest.json`에 등록.
- `nvpmodel` 프로파일을 결정하고 `configs/device.yaml`에 고정값으로 기록.
- 메모리 피크 측정: `tegrastats`로 camera_service + depth_processor + 추론 동시 구동 시 RSS 측정.

---

## 3. 소프트웨어 — 카메라 SDK

---

### 3.1 librealsense (Intel RealSense SDK 2.0)

**상태**: ⚠️ **저장소 이전 완료, 유지보수 지속 중**  
**역할**: D455 기반 Depth 프레임 수집

#### 준비물 및 구성

| 항목 | 내용 |
|---|---|
| 저장소 (신) | `github.com/realsenseai/librealsense` |
| 저장소 (구) | `github.com/IntelRealSense/librealsense` → 리다이렉트(유지 보장 불가) |
| 권장 백엔드 | RSUSB (커널 패치 없음, 의료기기 OS 업데이트 안정성 유리) |
| Python | `pyrealsense2` (PoC), C++ `librealsense2` (제품화) |
| ROS 2 | `realsense2_camera` (Humble 지원) |
| 최근 릴리스 | JetPack 7.0 지원 강화, D555 PoE 지원 추가 (2025.10) |

#### 알려진 문제점 및 기술적 리스크

1. **저장소 URL 변경**: 빌드 스크립트, Dockerfile, CI 파이프라인에 `IntelRealSense` 하드코딩된 URL이 있으면 향후 리다이렉트 만료 시 빌드 실패. **모든 참조를 `realsenseai/librealsense`로 업데이트.**

2. **비-LTS 커널에서 수동 패치 필요**: RSUSB 백엔드를 사용해도 비-LTS 커널에서는 일부 USB 드라이버 호환성 패치가 필요. 의료기기 배포는 LTS 커널만 사용하고 커널 버전을 고정.

3. **pyrealsense2 버전과 librealsense2 버전 불일치**: pip로 설치한 `pyrealsense2`와 소스 빌드한 `librealsense2`의 버전이 다르면 런타임 크래시. **소스 빌드 시 Python 바인딩도 함께 빌드(`-DBUILD_PYTHON_BINDINGS=ON`).**

#### 권장 조치

```bash
# 빌드 시 버전 고정 예시
git clone https://github.com/realsenseai/librealsense.git
git checkout v2.xx.x  # 검증된 버전으로 고정
```

---

### 3.2 Orbbec SDK v2

**상태**: ✅ **활발 유지보수, v2 신규 채택 권장**  
**역할**: Orbbec Femto Mega/Mega I 연동

#### 알려진 문제점 및 기술적 리스크

1. **v1 / v2 병존 저장소**: SDK 저장소에 v1(OpenNI 프로토콜)과 v2(UVC 표준) 브랜치가 공존. Gemini 305, 335 이후 신규 디바이스는 v2 전용. **Femto Mega 계열은 v2 전용으로 고정.**

2. **K4A Wrapper 릴리스 주기 분리**: 본 SDK와 K4A Wrapper는 독립 릴리스. K4A Wrapper가 Orbbec SDK v2 최신 버전을 즉시 지원하지 않을 수 있음. **제품화에서는 K4A Wrapper 미사용.**

---

### 3.3 DepthAI SDK / depthai-core

**상태**: 🔁 **v3 대전환 완료 (2025.09), v2 코드는 재사용 불가**

#### 알려진 문제점 및 기술적 리스크

1. **v2 → v3 포팅 필수**: `ColorCamera`, `MonoCamera` 노드 제거, `StereoDepth` API 변경. v2 예제/튜토리얼은 대부분 동작하지 않음.

2. **클라우드 변환 도구 의존**: 카메라 내부 VPU용 모델 변환이 HubAI(클라우드)에 의존. 오프라인 환경에서는 사전 변환된 `.superblob` 배포만 가능.

3. **`depthai-sdk` pip 패키지 v3 비호환**: `pip install depthai-sdk`와 `pip install depthai`(core)를 혼용하면 v3 환경에서 import 오류.

---

## 4. 소프트웨어 — AI 추론 런타임

---

### 4.1 TensorRT (JetPack 6.x 기준 TRT 10.3)

**상태**: ⚠️ **TRT 10.x 브레이킹 체인지, 신규 API로 작성 필수**  
**역할**: Jetson에서 호흡 안정성 모델, ROI 검출 모델 추론 가속

#### 준비물 및 구성

| 항목 | 내용 |
|---|---|
| JetPack 6.2 포함 버전 | TensorRT 10.3 |
| CUDA | 12.6 |
| 모델 포맷 | ONNX opset 9~20 입력, `.engine` 출력 |
| 빌드 도구 | `trtexec` 또는 TensorRT C++ Builder API |

#### API 변경 요약 (TRT 8.x → 10.x)

| 항목 | TRT 8.x | TRT 10.x |
|---|---|---|
| Batch 모드 | Implicit batch 지원 | Explicit batch 전용 |
| 실행 함수 | `enqueueV2()` | `enqueueV3()` |
| 텐서 접근 | `getBindingDimensions(int)` | `getTensorShape(name)` |
| 인덱스 타입 | int32 | int64 |
| 커스텀 플러그인 | IPluginV2 (deprecated) | IPluginV3 (`addPluginV3`) |
| INT8 캘리브레이터 | IInt8Calibrator (deprecated) | 명시적 Q/DQ 양자화 |
| 기존 `.engine` 파일 | — | **재빌드 필수, 역호환 없음** |

#### 권장 조치

- ONNX 모델 export 시 opset 17 이상 권장(LayerNorm, GroupNorm 지원).
- `.engine` 파일은 JetPack/TRT/CUDA 버전 태그를 포함한 파일명으로 관리 (`stable_breathhold_jp62_trt103_fp16.engine`).
- TRT 버전 업그레이드 전 전체 엔진 재빌드 + Golden Test Suite 실행을 자동화 파이프라인에 포함.

---

### 4.2 ONNX Runtime

**상태**: ✅ **ARM64 지원, JetPack 정합성 주의**  
**역할**: Raspberry Pi 5(CPU EP), Jetson(TensorRT EP), 모델 런타임 추상화

#### 알려진 문제점 및 기술적 리스크

1. **JetPack + TensorRT EP 설치 불일치**: `pip install onnxruntime-gpu`로 설치한 wheel이 JetPack 내 CUDA/TRT와 버전이 맞지 않으면 TensorRT EP가 비활성화됨. 이 경우 오류 없이 CPU EP로 폴백됨(성능 저하 무감지).

2. **소스 빌드 필요**: JetPack 6.x 환경에서 TRT EP를 활성화하려면 TensorRT TAR 패키지 지정 소스 빌드 필요:
   ```bash
   cmake ... --use_tensorrt \
     --cuda_home /usr/local/cuda \
     --tensorrt_home /usr/lib/aarch64-linux-gnu
   ```

3. **symbolic_shape 없으면 TRT EP 오류**: 입력 shape 정보가 없는 ONNX 모델에서 TRT EP가 실패. `onnxruntime.tools.symbolic_shape_infer`로 전처리 필요.

---

### 4.3 Hailo Runtime (AI HAT+ — Raspberry Pi 5 선택 옵션)

**상태**: ⚠️ **폐쇄망 모델 변환 제약 있음**  
**역할**: Raspberry Pi 5에서 ROI 검출 추론 가속

#### 알려진 문제점 및 기술적 리스크

1. **Dataflow Compiler (DFC)는 x86 Linux 전용**: Raspberry Pi에서 `.onnx` → `.hef` 컴파일 불가. x86 개발 환경에서 변환 후 `.hef` 파일만 배포.

2. **ONNX Runtime의 EP가 아님**: HailoRT는 독립 라이브러리. 추론 코드에서 `hailo_platform` API를 별도 경로로 구현해야 하며, ONNX Runtime과 통합 추론 불가.

3. **일부 모델 아키텍처 미지원**: YOLO11 등 최신 아키텍처는 DFC에서 직접 변환이 되지 않는 경우 있음. 사용 모델의 DFC 호환성 사전 확인 필수.

4. **INT8 캘리브레이션 데이터 필요**: HEF 변환 시 대표 이미지 500~1000장 필요. 의료 임상 데이터 사용 시 비식별화·동의 절차 필요.

---

## 5. 소프트웨어 — IPC / 프로세스 간 통신

---

### 5.1 ZeroMQ (libzmq)

**상태**: ✅ **유지보수 중, 사용 시 dropslient 정책 명시 필수**  
**역할**: camera_service → depth_processor 이벤트 전달 (Depth 요약값, 상태 이벤트)

#### 알려진 문제점 및 기술적 리스크

1. **PUB/SUB slow subscriber 무음 드롭**: ZeroMQ PUB/SUB는 구독자가 HWM(High Water Mark)에 도달하면 **조용히 메시지를 드롭**함(경고/에러 없음). 실시간 의료 시스템에서 추천 이벤트나 호흡 상태 이벤트가 소리 없이 사라질 수 있음. **HWM 정책과 드롭 감지 방법을 명시적으로 구현 필요.**

2. **Depth 원본 프레임 전달 금지**: 30 FPS 1280×720 Z16 프레임(~3.5MB/frame, ~100MB/s)을 ZeroMQ 메시지로 복사하면 성능 문제. **원본 프레임은 Shared Memory, 이벤트/요약값만 ZeroMQ.**

3. **inproc 소켓 bind/connect 순서 제약**: ZeroMQ inproc은 bind가 connect보다 먼저여야 함. 서비스 시작 순서가 달라지면 연결 실패. **서비스 시작 순서를 systemd `After=`/`Requires=`로 명시.**

#### 대안: NNG (nanomsg-next-generation)

| 항목 | ZeroMQ | NNG |
|---|---|---|
| 스레드 안전 | 소켓 공유 제한 | API 전반 스레드 안전 |
| C++ 런타임 의존 | 있음 | 없음 (C 구현) |
| 활발 개발 | 유지보수 수준 | 활발 |
| 셧다운 복잡도 | 높음 | 낮음 |
| inproc bind순서 | 제약 있음 | 자유 |

**권장**: 신규 서비스 간 이벤트 채널은 NNG 검토. 기존 ZeroMQ 사용 시 dropslient 정책 + HWM 모니터링 필수.

---

### 5.2 Shared Memory (Depth 프레임 IPC)

**상태**: ✅ **설계 패턴 확정 필요**  
**역할**: camera_service → depth_processor Raw Depth 프레임 전달

#### POSIX shm_open vs memfd_create

| 항목 | shm_open | memfd_create |
|---|---|---|
| 경로 노출 | `/dev/shm/` 파일 생성 | 파일시스템 경로 없음 |
| 정리 책임 | 명시적 `shm_unlink` 필요 | FD 닫히면 자동 정리 |
| 비정상 종료 시 누수 | 발생 가능 | 없음 |
| File sealing | 불가 | `F_ADD_SEALS` 지원 |
| 이식성 | POSIX 표준 | Linux 3.17+ 전용 |
| 권장 | 이식성 필요 시 | 단일 Linux 디바이스 권장 |

**권장**: 단일 Linux 디바이스(Jetson/RPi)이므로 `memfd_create` + `F_SEAL_WRITE` sealing 사용.

#### Ring Buffer C++20 Atomic 설계 원칙

```cpp
// SPSC Ring Buffer 슬롯 상태
enum class SlotState : uint32_t {
  EMPTY = 0, WRITING = 1, READY = 2, READING = 3
};

struct Slot {
  alignas(64) std::atomic<SlotState> state;  // false sharing 방지
  int64_t timestamp_ms;
  int64_t monotonic_ms;
  uint64_t frame_id;
  uint8_t data[DEPTH_FRAME_BYTES]; // W * H * 2 (Z16)
};

// Producer: EMPTY → WRITING → READY (release store)
// Consumer: READY → READING → EMPTY (acquire load)
// Memory order: store(release) + load(acquire) 조합으로 충분
// seq_cst는 불필요한 메모리 펜스 오버헤드
```

---

## 6. 소프트웨어 — API 게이트웨이 / 백엔드

---

### 6.1 FastAPI (Python)

**상태**: 📌 **MVP 한정 사용, 제품화 전 교체 검토**  
**역할**: REST/WebSocket API 게이트웨이

#### 알려진 문제점 및 기술적 리스크

1. **단일 워커 처리량 한계**: 기본 uvicorn 단일 워커 기준 ~200 req/s 수준. 동시 요청이 적은 Operator UI 환경에서는 충분하지만, 다중 모니터/다중 UI 클라이언트 연결 시 병목 가능.

2. **ARM 저전력 환경 GIL 오버헤드**: Python GIL로 인해 camera_service와 api_gateway를 동일 프로세스에서 운용하면 멀티코어 활용 불가. **api_gateway는 별도 프로세스로 분리.**

3. **asyncio + 블로킹 DB 호출 혼용**: `sqlite3` 표준 라이브러리는 동기 API. FastAPI async 핸들러에서 직접 호출하면 이벤트 루프 블로킹. **`aiosqlite` 또는 별도 thread pool executor 사용.**

---

### 6.2 Go (Fiber / net/http)

**상태**: ✅ **임베디드 의료기기 API 게이트웨이 권장**  
**역할**: FastAPI 대체, Phase 2 이후 제품화 API 게이트웨이

#### 장점 요약

| 항목 | 특성 |
|---|---|
| 바이너리 | 단일 정적 바이너리, 즉시 시작 (systemd ready 빠름) |
| 메모리 | FastAPI 대비 절반 이하 |
| 처리량 | Fiber 기준 FastAPI 대비 7~11배 처리량 |
| 배포 | 의존성 없음, 오프라인 배포 적합 |
| GC | Go GC로 tail latency 다소 변동 가능 (실시간 임계는 아님) |

---

### 6.3 Rust (Axum / Actix)

**상태**: ✅ **IEC 62304 Class C 인증 컴파일러 (Ferrocene) 존재**  
**역할**: 안전 임계 서비스(device_gateway, exposure_recommender) 장기 후보

#### 주요 포인트

- Ferrous Systems의 Ferrocene(Rust 컴파일러)이 2025년 1월 TÜV SÜD IEC 62304 Class C(최고 등급) 인증 취득. x86-64 Linux, AArch64(Armv8-A) 지원.
- Axum은 Tokio 팀 공식 백킹, Tower 미들웨어 생태계. 의료기기 최고 안전 등급 Rust 코드 작성의 규제 근거 확보.
- **현실적 채택 시점**: Phase 3 이상 device_gateway 또는 exposure_recommender. MVP에서 강제할 이유 없음.

---

## 7. 소프트웨어 — 데이터베이스 / 감사로그

---

### 7.1 SQLite WAL + Application-level Hash Chain

**상태**: ✅ **단일 디바이스 감사로그 권장 구성**  
**역할**: 감사로그, 캘리브레이션 프로파일, 세션 기록

#### 알려진 문제점 및 기술적 리스크

1. **WAL 자체는 Tamper-Evident가 아님**: WAL 모드는 동시성을 개선하지만, DB 파일 접근 권한이 있는 프로세스는 UPDATE/DELETE 가능. **Hash chain은 반드시 Application-level로 구현** (SQLite trigger는 정규화·키 관리·이식성 불리).

2. **hash chain의 한계 — 삭제 감지 불가**: Hash chain은 변조·순서 조작을 탐지하지만, 전체 DB 삭제 후 재생성은 감지하지 못함. **일 1회 이상 외부 앵커링** (원격 syslog 서버, USB 내보내기 + 해시 검증) 권장.

3. **wall clock 기반 순서 보장 불가**: 시스템 시간이 조정되면 timestamp 순서가 뒤집힐 수 있음. **`audit_id`는 서버 할당 단조 증가 시퀀스(AUTOINCREMENT)로 순서 보장, timestamp는 참고 목적.**

4. **synchronous=FULL vs WAL+NORMAL**: `FULL`은 OS 버퍼 플러시까지 대기(전원 차단 내구성 최고, 쓰기 느림). WAL + `NORMAL`은 대부분의 장애에서 안전하나 극단적 전원 차단 시 마지막 트랜잭션 손실 가능. **전원 차단 시나리오 테스트 후 정책 결정, `power-loss test`를 FI-008로 포함.**

#### Hash Chain 구현 원칙

```python
import hashlib, json

def compute_event_hash(event_data: dict, prev_hash: str) -> str:
    # 정규화된 JSON (키 정렬, 공백 없음)
    canonical = json.dumps(event_data, sort_keys=True, separators=(',', ':'))
    payload = prev_hash + canonical
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
```

---

## 8. 소프트웨어 — Operator UI 런타임

---

### 8.1 React/TypeScript + Chromium 키오스크

**상태**: 📌 **MVP 가능, 제품화 전 키오스크 안정성 검증 필수**  
**역할**: Operator UI (웹 기반)

#### 알려진 문제점 및 기술적 리스크

1. **Wayland/labwc 전체화면 해제 버그**: Raspberry Pi OS Bookworm 기본 컴포지터 `labwc`에서 HDMI 신호 끊김/해상도 변경 시 Chromium 전체화면이 풀려 창 모드로 전환되는 버그 보고. X11에서는 발생 안 함. **해결: `cage` 컴포지터 사용 (키오스크 전용 Wayland 컴포지터).**

2. **WebSocket 자동 재연결 없음**: 브라우저 native WebSocket은 연결 끊김 시 자동 재연결을 제공하지 않음. **지수 백오프 재연결 로직 + heartbeat/ping-pong + 메시지 시퀀스 번호 클라이언트 구현 필수.**

3. **메모리 증가**: 장시간 운용 시 Chromium 메모리 사용량이 증가할 수 있음. **주기적 새로고침 또는 Chromium `--max-old-space-size` 설정.**

---

### 8.2 Qt/QML

**상태**: ✅ **의료기기 임베디드 UI 제품화 권장**  
**역할**: Phase 2 이상 제품화 Operator UI

#### 장점 요약

| 항목 | 특성 |
|---|---|
| 임베디드 실적 | Boot2Qt, 의료·산업 장비 다수 실적 |
| 결정성 | 렌더링 엔진이 브라우저 엔진 의존 없음 |
| 장기 지원 | Qt LTS 3년, 상용 지원 가능 |
| 키오스크 | Qt Wayland Compositor 직접 통합 가능 |
| 단점 | 개발자 풀 좁음, 상용 라이선스 비용 |

---

### 8.3 Tauri

**상태**: ⚠️ **경량 대안, Linux WebKitGTK 렌더링 일관성 주의**  
**역할**: React UI를 경량 네이티브 앱으로 패키징 (선택 옵션)

#### 알려진 문제점

- Linux는 WebKitGTK를 시스템 WebView로 사용. 배포판/버전마다 렌더링 차이 발생 가능.
- Rust 기반 백엔드로 공격 표면 최소화·메모리 안전은 강점.
- 의료기기 임베디드 실적이 Qt 대비 적음.

---

## 9. 리스크 종합 매트릭스

| 항목 | 리스크 | 심각도 | 발생도 | 권장 대응 |
|---|---|---|---|---|
| Intel RealSense 분사 | 장기 공급 불확실 | S3 | O2 | HAL 설계, 대안 병행 검증 |
| librealsense 저장소 이전 | 빌드 실패 | S2 | O3 | URL 업데이트, vendoring |
| TensorRT 10.x 브레이킹 체인지 | 엔진 재빌드, API 수정 필수 | S3 | O4 | 신규 API 기준 작성, 재빌드 자동화 |
| DepthAI SDK v2→v3 대전환 | 파이프라인 코드 전면 재작성 | S3 | O5 | v2 고정 또는 v3 신규 채택 |
| ZeroMQ slow subscriber dropslient | 이벤트 소리 없이 소실 | S4 | O3 | HWM 설정, dropslient 모니터링 |
| ONNX Runtime TRT EP 미활성화 | 성능 저하 무감지 CPU 폴백 | S2 | O3 | 소스 빌드, 버전 매트릭스 |
| Hailo DFC x86 전용 | 폐쇄망 모델 변환 불가 | S2 | O4 | x86 빌드 서버 확보 |
| RPi5 Wayland 키오스크 버그 | UI 전체화면 해제 | S2 | O3 | cage 컴포지터 |
| SQLite Tamper-Evident 미보장 | 감사로그 변조 감지 불가 | S4 | O2 | App-level hash chain + 외부 앵커링 |
| TRT `.engine` 버전 비호환 | 업데이트 후 추론 실패 | S3 | O3 | 엔진 재빌드 자동화 파이프라인 |
| Jetson 공유 메모리 한계 | 8GB RAM OOM 위험 | S3 | O2 | 메모리 프로파일링, TRT workspace 튜닝 |

> **심각도(S) / 발생도(O)**: `risk-management.md` §3 척도 기준.

---

## 10. 단계별 결정 사항

### Phase 1 MVP (현재)

| 결정 항목 | 권장 선택 | 비고 |
|---|---|---|
| 카메라 | RealSense D455 | URL을 realsenseai로 업데이트 |
| 보드 | Raspberry Pi 5 또는 Jetson Orin Nano | CUDA/TRT 필요 시 Jetson |
| Camera SDK | librealsense RSUSB 소스 빌드 (버전 고정) | |
| AI 추론 | ONNX Runtime CPU EP (규칙 기반 우선) | |
| IPC | ZeroMQ (HWM 명시) + Python multiprocessing Queue | |
| API 게이트웨이 | FastAPI (단일 워커) | |
| DB | SQLite WAL + app-level SHA-256 hash chain | |
| UI | React + Chromium (cage 컴포지터) | |

### Phase 2 PoC (설치형)

| 결정 항목 | 권장 선택 | 비고 |
|---|---|---|
| 카메라 | Orbbec Femto Mega I PoE | D455 HAL 유지 |
| 보드 | Jetson Orin Nano Super (JetPack 6.2) | |
| TensorRT | 10.3, Explicit batch, enqueueV3 | 엔진 재빌드 파이프라인 구축 |
| IPC | memfd_create + SPSC Ring Buffer (Depth 프레임) + NNG (이벤트) | |
| API 게이트웨이 | Go (Fiber 또는 net/http) | |
| UI | Qt/QML 평가 시작 | |

### Phase 3 제품화

| 결정 항목 | 권장 선택 | 비고 |
|---|---|---|
| 카메라 | 1종 최종 고정 (장시간 테스트 통과 기준) | |
| 안전 임계 서비스 | Rust (Axum) 검토 (Ferrocene IEC 62304 Class C) | device_gateway, exposure_recommender |
| 감사로그 앵커링 | 외부 타임스탬프 서비스 또는 USB 주기 내보내기 | |
| SDK 고정 | 모든 SDK 버전 vendoring, SBOM 작성 | |

---

## 11. 검토 이력

| 날짜 | 버전 | 변경 내용 | 작성자 |
|---|---|---|---|
| 2026-06-24 | 1.0.0 | 최초 작성 | — |

> **정기 검토 주기**: 분기 1회 이상. 각 항목의 GitHub 릴리스 노트, 공식 블로그, 취약점 공시(CVE)를 기준으로 업데이트.
