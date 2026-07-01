# Smart X-ray Assist — 구현 진행상황 (Phase 1 MVP)

기준일: 2026-06-25 · 소스: `en/files/*.md` (영어 설계문서). Ko 폴더는 1:1 번역 아님(버전 상이/누락 있음 — 아래 참고).

## 무엇을 만들고 있나
`en/` 설계문서 기반 Phase 1 "Operator Assist" MVP. Python 모노레포. 목 카메라로 하드웨어 없이 전체 파이프라인 동작 + 테스트 가능.
파이프라인: camera → depth → gating → exposure recommender → audit, 이벤트버스 경유. FastAPI REST+WS 게이트웨이. X-ray 절대 발사 안 함, 추천은 참고용+오퍼레이터 승인 게이트, 장애 시 safe state.

## 완료 (동작 확인됨)
- 스캐폴드: `configs/` (device/camera/gating/exposure_lut + calib_room_a.json), `schemas/` (7개 JSON Schema), `migrations/001_init.sql`, `pyproject.toml`, `requirements.txt`
- `src/xray_assist/common/`: clock, messages, errors(safe-state 정책), event_bus(드롭 카운트), config(서명 게이트), validation(JSON Schema)
- `src/xray_assist/camera/`: interface(IDepthCamera), mock_camera(합성 호흡파형+기침/홀드 주입), realsense_adapter(pyrealsense2 guarded import), service(USB/프레임드롭 장애처리)
- `src/xray_assist/depth/`: calibration(서명+드리프트), processor(camera.md 9단계 파이프라인, median 기반 두께)
- `src/xray_assist/gating/respiration.py`: dZ/dt + d²Z/dt² 상태머신, 기침 abort
- `src/xray_assist/exposure/recommender.py`: LUT 조회 + 가드레일 클램프 + 승인게이트 + manual_review
- `src/xray_assist/audit/logger.py`: SQLite WAL + SHA-256 해시체인 (verify_chain 통과 확인)
- `src/xray_assist/app.py`: Orchestrator (전체 와이어링, 세션/safe-state/오퍼레이터 액션)
- `src/xray_assist/api/gateway.py`: FastAPI REST(/health /state /sessions /operator/approve /operator/action) + WS(/ws/v1/events)
- `scripts/run_mvp.py`: 엔트리포인트 (--headless 또는 :8080 서버+UI)

스모크 결과: 부팅 OK, 감사 해시체인 OK.

## ✅ 2026-06-25 CLI 세션 완료분
- **게이팅 #1 버그 수정 완료.** 원인 3개: (1) median이 Z16 1mm 양자화로 계단 → 게이팅 신호를 mean(유효픽셀)로 교체, (2) 타임스탬프 dt 지터 ±25% → dt EMA 평활, (3) z·dz/dt EMA 평활 + 워밍업 가드. 결과: 정상호흡 d2z≈20<25(오탐 없음), 기침 d2z>1000(정상 abort). measurement raw 정밀 유지, 반올림은 `DepthSummary.to_message()` 표시용만.
- **테스트 42개 그린** (`pytest tests/`). unit: UT-LUT/GATE/SCHEMA/AUDIT/CONFIG/CONF-001, integration: IT-CAM-CORE/CORE-UI/AUDIT/SAFE-001. `tests/conftest.py`로 audit DB tmp 격리.
- **scripts/calibrate_empty_bed.py** — 빈침대 캘리브+드리프트+--write-signature 재서명 (GTS-002).
- **ui/operator-console/index.html** — 키오스크, WS 지수백오프 재연결, Manual Mode 오버레이, breath-cue/approve/abort.
- **app.py**: operator_action `play_breath_cue` 와이어링(목 hold_breath 시뮬), abort 시 호흡 재개.
- **README.md** 구현 문서 작성.

전체 데모: Start Session → Play Breath Cue → stable_breath_hold → 추천 kvp82/mas15 → Approve/Abort 동작 확인.

## 주의 / Phase 2
- 게이팅은 설정 fps(camera.yaml) 기준 튜닝. 루프가 fps보다 빠르면 d2z 노이즈 증폭으로 오탐 가능 — run_mvp/테스트는 1/fps 케이던스 구동. 실보드 버스트 프레임 강건화는 Phase 2.
- FI-*/GTS 하드웨어 테스트는 실보드 필요(범위 외).

## (해결됨, 기록) 과거 1순위 버그
**게이팅 미분 채널 노이즈 폭주.** 30fps에서도 max d2z ≈ 956 mm/s² (임계 25). 원인: ROI median이 프레임마다 holes/IQR/반올림(0.1mm)으로 흔들려 d²Z/dt² 폭발 → 매 프레임 cough abort 오탐. breathing 신호 자체는 정상(진폭8mm/주기4s).

**수정 방향 (작업 중단 지점):**
1. `depth/processor.py`: measurement 값 raw(미반올림) 유지, 반올림은 `common/messages.py` `DepthSummary.to_message()`에서 표시용으로만.
2. `gating/respiration.py`: 미분 전에 z에 EMA 스무딩(alpha~0.3) + dz_dt에도 EMA → d²Z/dt² 노이즈 억제. camera.md 파이프라인 step-7 temporal filter에 해당.
3. `app.py` `_on_frame`: DepthSummary 객체 유지해 gating엔 raw median 전달, 퍼블리시는 반올림 메시지.
4. 검증: 기침 주입(+30mm)은 여전히 d2z>25 트리거해야 함 (UT-GATE-002). 목 노이즈 0.5mm/홀 5%는 유지하고 알고리즘을 robust하게.

빠른 재현:
```
cd smart-xray-assist
PYTHONPATH=src python3 -c "
from xray_assist.app import Orchestrator; import time
o=Orchestrator(); o.start()
for i in range(300): o.tick(5); time.sleep(0.033)
print(o.state_snapshot()); print(o.last_recommendation)
o.stop()"
```
목표: 몇 초 내 `stable_breath_hold` 도달 + 추천 kVp/mAs 생성(adult chest_pa 230mm → kvp82/mas15 부근).

## 미착수 (TODO)
- 위 게이팅 버그 수정
- 테스트: `tests/unit/` (UT-LUT-001, UT-GATE-001/002, UT-SCHEMA-001, UT-AUDIT-001, UT-CONFIG-001, UT-CONF-001), `tests/integration/` (IT-CAM-CORE-001, IT-CORE-UI-001, IT-AUDIT-001, IT-SAFE-001) — V&V 문서 기준
- `scripts/calibrate_empty_bed.py` (빈 침대 캘리브레이션 + 서명)
- `ui/operator-console/index.html` (키오스크, WS 지수백오프 재연결 + Manual Mode 화면)
- `README.md` (구현 README, 빌드문서 README와 별개)
- pytest 전체 실행 + 그린

## 의존성
numpy, PyYAML, jsonschema, fastapi, uvicorn, pydantic, websockets, httpx, pytest — 모두 설치됨(Python 3.14.5). pyrealsense2는 선택(엣지보드 전용).

## en vs Ko 폴더 비교 결론
1:1 번역 아님. README/camera는 다른 버전 문서, verification-validation(ko)는 축약(Golden Test Suite·audio-latency 누락), fault-injection ID 재매핑, pediatric/bariatric LUT 행 누락 등 사실 드리프트 존재. tech-stack-assessment.md는 양쪽 동일(둘 다 한국어). **구현은 en 기준.**
