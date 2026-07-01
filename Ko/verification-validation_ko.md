# verification-validation.md — 검증 및 밸리데이션 계획서

작성 대상: 시니어 개발자, QA, 테스트 엔지니어, RA  
관련 문서: `README.md`, `docs/risk-management.md`, `docs/hardware.md`, `docs/api-schema.md`

---

## 1. 목적

본 문서는 스마트 호흡 연동 및 체형 맞춤형 촬영 보조 시스템의 소프트웨어/하드웨어 검증, 팬텀 테스트, 장시간 안정성 테스트, fault injection, 사용적합성 검증의 기준을 정의한다.

---

## 2. 테스트 레벨

| 레벨 | 대상 | 목적 |
|---|---|---|
| Unit Test | 개별 함수/클래스 | 룰, 필터, LUT, schema 검증 |
| Integration Test | 서비스 간 통신 | API/IPC 계약 검증 |
| Playback Test | 저장 Depth stream | 알고리즘 회귀 테스트 |
| Hardware Test | 실제 카메라/보드 | 프레임, 온도, 연결 안정성 |
| HIL Test | 인터페이스 보드/팬텀 | 실제 시나리오 검증 |
| Usability Test | 작업자 UI | 오조작 방지, workflow 검증 |
| Long-run Test | 전체 시스템 | 장시간 안정성 검증 |

---

## 3. 필수 테스트 항목

### 3.1 카메라 정적 정확도

| 항목 | 기준 |
|---|---|
| 대상 | known-height phantom block |
| 거리 | 0.6m, 1.0m, 1.5m, 2.0m |
| 반복 | 각 30회 이상 |
| 기록 | median, mean, std, valid pixel ratio |
| 합격 기준 | 프로젝트별 별도 허용오차 정의 |

### 3.2 동적 호흡 팬텀

| 항목 | 기준 |
|---|---|
| 장치 | step motor breathing phantom |
| 진폭 | 5mm, 10mm, 20mm, 50mm |
| 주기 | 2s, 4s, 6s |
| 검증 | peak detection, plateau detection, abort detection |
| 출력 | gating latency, false positive, false negative |

### 3.3 카메라 장시간 안정성

| 항목 | 기준 |
|---|---|
| 기간 | 8시간, 제품화 전 24시간 |
| 지표 | FPS, dropped frame, temperature, reconnect count |
| 조건 | 실제 촬영실 조명/배선 환경 |
| 합격 | 기준 초과 시 safe state 동작 |

---

## 4. 소프트웨어 테스트

### 4.1 Unit Test 예시

| Test ID | 대상 | 기대 결과 |
|---|---|---|
| UT-LUT-001 | LUT 경계값 | min/max clamp 정상 |
| UT-GATE-001 | dz/dt 계산 | 안정/불안정 분류 정상 |
| UT-SCHEMA-001 | JSON schema | 필수 필드 누락 감지 |
| UT-AUDIT-001 | hash chain | 변조 감지 |
| UT-CONFIG-001 | config validation | 잘못된 설정 차단 |

### 4.2 Integration Test 예시

| Test ID | 대상 | 기대 결과 |
|---|---|---|
| IT-CAM-CORE-001 | camera→depth | frame_meta 수신 정상 |
| IT-CORE-UI-001 | core→WebSocket | UI 상태 갱신 정상 |
| IT-AUDIT-001 | action→audit | 작업자 이벤트 기록 |
| IT-SAFE-001 | error→safe state | 추천 비활성화 |

---

## 5. Fault Injection 테스트

| Test ID | 장애 | 기대 결과 |
|---|---|---|
| FI-001 | 카메라 분리 | safe state, UI 경고 |
| FI-002 | Depth frame drop | confidence 하락, 추천 제한 |
| FI-003 | DB full | audit 오류, 수동 모드 |
| FI-004 | config 변조 | 서비스 시작 차단 |
| FI-005 | model 변조 | fallback model 적용 |
| FI-006 | API process crash | systemd restart |
| FI-007 | 오디오 장치 없음 | UI 안내 대체 |
| FI-008 | thermal throttling | 경고 및 성능 제한 |

---

## 6. Acceptance Criteria

초기 MVP 합격 기준 예시:

| 항목 | 기준 |
|---|---|
| Depth FPS | 30 FPS target, drop 기준 이내 |
| UI latency | 상태 변화 500ms 이내 표시 |
| Gating state | 팬텀 기준 안정/불안정 분류 재현성 확보 |
| Safe state | 주요 장애에서 추천 비활성화 |
| Audit log | 세션/추천/승인/오류 이벤트 기록 |
| Manual mode | 모든 오류 상태에서 접근 가능 |
| Calibration | 시작 시 빈 베드 원점 캘리브레이션 가능 |

---

## 7. 테스트 산출물

```text
test-results/
  unit-test-report.xml
  integration-test-report.xml
  camera-static-accuracy.csv
  breathing-phantom-result.csv
  long-run-8h-report.json
  fault-injection-report.md
  usability-observation.md
  release-test-summary.md
```

---

## 8. 결론

검증의 핵심은 단순 알고리즘 정확도보다 `오류 시 안전하게 실패하는가`이다. 모든 테스트는 위험관리 문서의 Risk Control과 연결되어야 하며, 릴리즈 승인 전 추적성 매트릭스를 완료해야 한다.
