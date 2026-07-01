# 카메라 추상화 & 멀티카메라

[← README로](../README.md)

상위 서비스(깊이 처리 등)는 벤더 SDK 타입을 **절대 보지 않습니다.** 카메라 교체는 코드 변경이 아니라 설정·런타임 선택입니다.

## `IDepthCamera` 인터페이스

[`camera/interface.py`](../smart-xray-assist/src/xray_assist/camera/interface.py) — 모든 어댑터가 구현하는 벤더 무관 계약:

```python
class IDepthCamera(ABC):
    def open(cfg) -> bool
    def close() -> None
    def get_frame(timeout_ms) -> Optional[DepthFrame]   # uint16 HxW
    def get_device_info() -> DeviceInfo
    def is_connected() -> bool
    def usb_speed() -> str                               # USB 2.0 폴백 감지
```

`DepthFrame`은 원시 Z16 배열 + 메타(width/height/depth_scale/frame_id)만 담습니다. 어느 벤더에서 왔는지 상위는 모릅니다.

## 어댑터 팩토리

[`camera/service.py`](../smart-xray-assist/src/xray_assist/camera/service.py)의 `build_camera(cfg)`가 provider 문자열 → 어댑터를 만듭니다:

| provider | 어댑터 | SDK (선택 설치) |
|---|---|---|
| `mock` | [`mock_camera.py`](../smart-xray-assist/src/xray_assist/camera/mock_camera.py) | 없음 — 합성 파이프라인 |
| `realsense` | [`realsense_adapter.py`](../smart-xray-assist/src/xray_assist/camera/realsense_adapter.py) | `pyrealsense2` |
| `orbbec` | [`orbbec_adapter.py`](../smart-xray-assist/src/xray_assist/camera/orbbec_adapter.py) | `pyorbbecsdk` |

**import 가드**: 하드웨어 SDK는 엣지 보드에만 설치됩니다. 어댑터의 SDK import는 `try/except`로 감싸져, SDK가 없는 개발 머신에서도 모듈 로드가 깨지지 않습니다(생성 시에만 명확한 에러).

## Discovery — 벤더별 실기기 열거

[`camera/discovery.py`](../smart-xray-assist/src/xray_assist/camera/discovery.py) — 벤더 SDK 프로빙을 한곳에 모아, 오케스트레이터·REST·콘솔이 "무슨 카메라가 있는가"에 대해 같은 답을 갖게 합니다.

```python
enumerate_all() -> [
  { id, label, available, detail, devices: [{serial, model}, ...] },
  ...
]
```

- `mock` — 항상 available, 합성 기기 1대
- `realsense` — `rs.context().query_devices()`로 연결된 각 기기의 시리얼·모델 열거
- `orbbec` — `Context().query_devices()`로 동일 열거
- SDK 없음 / 기기 없음 → `available: false` + 사유(`detail`)

**벤더 추가 = 레지스트리 항목 1개 + 어댑터 1개 + `build_camera` 분기 1개.**

## 런타임 연결 & 시리얼별 선택

```
POST /api/v1/devices/connect  { "provider": "...", "serial": "..." }
POST /api/v1/devices/disconnect
GET  /api/v1/devices          → { active:{provider,serial}, connected, providers:[...] }
```

오케스트레이터의 `connect_device(provider, serial)`는 `_cam_lock` 아래서:

1. 새 provider·serial로 `CameraService`를 만들고 `start()`
2. 실패 시 감사에 `device_connect_failed` 기록하고 기존 서비스 유지 (graceful)
3. 성공 시 기존 서비스 교체, 활성 `{provider, serial}` 갱신

콘솔 **설정 → 카메라** 셀렉트는 `/devices` 열거 결과로 채워집니다. 같은 벤더에 여러 대가 붙으면 `모델 · 시리얼 — 벤더` 형태로 개별 항목이 뜨고, 선택한 `provider|serial`로 정확히 그 기기에 연결합니다. 사용 불가 벤더는 사유와 함께 비활성 표시됩니다.

관련: [아키텍처 & 파이프라인](architecture.md) · [API & 실시간](api-and-realtime.md)
