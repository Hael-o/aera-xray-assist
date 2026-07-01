# risk-management.md — 위험관리 파일 초안

작성 대상: 시니어 개발자, QA/RA, 시스템 아키텍트, 테스트 엔지니어  
관련 문서: `README.md`, `docs/regulatory.md`, `docs/hardware.md`, `docs/api-schema.md`

---

## 1. 목적

본 문서는 스마트 호흡 연동 및 체형 맞춤형 촬영 보조 시스템의 주요 위해요인, 위험 상황, 위험통제, 검증 방법, 잔여위험 관리 방안을 정의한다.

위험관리 기준은 ISO 14971 접근을 따른다. 본 문서는 초기 위험관리 파일의 초안이며, 실제 제품화 전에는 RA/QA, 임상 사용자, 하드웨어 엔지니어, 소프트웨어 엔지니어가 함께 검토해야 한다.

---

## 2. 제품 범위 기준

초기 위험분석 대상:

```text
Phase 1 Operator Assist
- 3D Depth 기반 환자 체형/두께 측정
- 호흡 안정성 감지
- 추천 kVp/mAs 표시
- 작업자 최종 승인
- 감사로그 저장
```

초기 범위 제외:

```text
- X-ray generator direct control
- 작업자 승인 없는 자동 촬영
- 진단 판독 보조
- 배포 후 자동 self-learning 모델 적용
```

---

## 3. 위험평가 척도

### 3.1 심각도 Severity

| 등급 | 의미 | 예시 |
|---|---|---|
| S1 | 경미 | 일시적 UI 혼동, 재시도 필요 |
| S2 | 낮음 | 촬영 지연, workflow 불편 |
| S3 | 중간 | 재촬영 가능성 증가, 영상 품질 저하 |
| S4 | 높음 | 과다/과소 피폭 가능성, 임상 workflow 영향 |
| S5 | 치명 | 비의도 촬영, 중대한 안전사고 가능성 |

### 3.2 발생도 Occurrence

| 등급 | 의미 |
|---|---|
| O1 | 거의 없음 |
| O2 | 드묾 |
| O3 | 가끔 발생 가능 |
| O4 | 빈번 가능 |
| O5 | 매우 빈번 |

### 3.3 탐지가능성 Detectability

| 등급 | 의미 |
|---|---|
| D1 | 자동 탐지 매우 쉬움 |
| D2 | 대부분 탐지 가능 |
| D3 | 일부 탐지 가능 |
| D4 | 탐지 어려움 |
| D5 | 탐지 불가에 가까움 |

위험 우선순위 참고값:

```text
RPN = Severity × Occurrence × Detectability
```

RPN은 보조 지표이며, S4 이상 위험은 RPN과 무관하게 별도 검토한다.

---

## 4. Hazard 목록

| Hazard ID | 위해요인 | 원인 | 잠재 결과 |
|---|---|---|---|
| H-001 | 환자 두께 오측정 | 카메라 캘리브레이션 오류, 의복 노이즈 | 부적절한 추천값 |
| H-002 | 호흡 안정성 오판단 | Depth 프레임 누락, 기침, 움직임 | 재촬영, 영상 품질 저하 |
| H-003 | 과다 선량 추천 | LUT 오류, 비만/소아 보정 실패 | 불필요한 피폭 가능성 |
| H-004 | 과소 선량 추천 | 두께 과소 측정, 센서 hole | 노이즈 증가, 재촬영 가능성 |
| H-005 | 작업자 UI 오해 | 추천값/확정값 혼동 | 잘못된 장비 설정 |
| H-006 | 카메라 장애 | USB/PoE 끊김, SDK crash | 측정 불가, 지연 |
| H-007 | 오디오 안내 지연 | ALSA/mixer latency 변동 | 호흡 타이밍 불일치 |
| H-008 | 감사로그 누락 | DB 장애, 전원 차단 | 사후 추적성 상실 |
| H-009 | 개인정보 노출 | RGB/Depth 저장, 얼굴 영역 표시 | 개인정보 침해 |
| H-010 | 모델 성능 저하 | 잘못된 업데이트, 지속학습 오류 | 오판단 증가 |
| H-011 | 비의도 촬영 신호 | Phase 3 릴레이/통신 오류 | 안전사고 가능성 |
| H-012 | 수동 모드 전환 실패 | UI/서비스 hang | 응급 workflow 방해 |

---

## 5. 주요 위험통제 매트릭스

| Hazard | 초기 S/O/D | 위험통제 | 검증 방법 | 잔여위험 |
|---|---:|---|---|---|
| H-001 두께 오측정 | 4/3/3 | 빈 베드 캘리브레이션, 평판 보정, 측정 신뢰도 표시 | static phantom test | 허용 가능 여부 검토 |
| H-002 호흡 오판단 | 3/3/3 | dZ/dt 안정성 검증, 최소 안정 시간, Abort | breathing phantom test | 허용 가능 |
| H-003 과다 선량 추천 | 4/2/3 | 추천값 상한, 작업자 승인, 소아/비만 모드 | LUT boundary test | RA 검토 필요 |
| H-004 과소 선량 추천 | 3/3/3 | 추천값 하한, confidence 낮을 때 비활성화 | phantom + replay test | 허용 가능 여부 검토 |
| H-005 UI 오해 | 4/2/3 | “추천값” 라벨, 승인 버튼, 경고 문구 | usability test | 사용자 교육 필요 |
| H-006 카메라 장애 | 2/3/1 | watchdog, reconnect, safe mode | fault injection | 허용 가능 |
| H-007 오디오 지연 | 3/2/2 | ALSA direct, latency calibration | latency measurement | 허용 가능 |
| H-008 로그 누락 | 3/2/3 | SQLite WAL, fsync, hash chain | power-loss test | 허용 가능 |
| H-009 개인정보 노출 | 4/2/3 | RGB 기본 비활성화, Depth ROI masking | privacy review | 정책 검토 필요 |
| H-010 모델 성능 저하 | 4/2/4 | signed model, golden test, rollback | regression test | 초기제품 제외 권장 |
| H-011 비의도 촬영 | 5/1/4 | Phase 1 제외, 절연, interlock, manual approval | HIL safety test | Phase 3 별도 관리 |
| H-012 수동 전환 실패 | 4/2/2 | always-available manual mode, hardware bypass | usability + fault test | 허용 가능 여부 검토 |

---

## 6. 안전 상태 정의

시스템은 다음 조건에서 반드시 Safe State로 전환한다.

```text
Safe State:
- 추천 kVp/mAs 표시 비활성화 또는 “신뢰도 낮음” 표시
- 자동/반자동 입력 비활성화
- 작업자에게 수동 촬영 안내
- Audit Event 기록
- 필요 시 오디오 안내 중단
```

Safe State 진입 조건:

- 카메라 연결 끊김
- Depth 프레임 연속 N회 누락
- 캘리브레이션 미완료
- ROI 검출 실패
- 측정 confidence 임계값 미만
- 환자 움직임/기침 감지
- 추천 엔진 예외
- 모델/설정 파일 서명 검증 실패
- DB 쓰기 실패 또는 저장소 full

---

## 7. 위험통제 요구사항

### 7.1 카메라/Depth 측정

| ID | 요구사항 |
|---|---|
| RC-CAM-001 | 카메라가 인식되지 않으면 시스템은 추천값을 표시하지 않아야 한다 |
| RC-CAM-002 | Depth frame timestamp가 역전되거나 누락되면 해당 frame은 폐기해야 한다 |
| RC-CAM-003 | ROI confidence가 임계값보다 낮으면 수동 모드로 전환해야 한다 |
| RC-CAM-004 | 캘리브레이션 파일이 없거나 버전이 맞지 않으면 촬영 보조 기능을 차단해야 한다 |

### 7.2 호흡 게이팅

| ID | 요구사항 |
|---|---|
| RC-GATE-001 | 호흡 안정성 판단에는 최소 안정 유지 시간 조건을 포함해야 한다 |
| RC-GATE-002 | 기침/돌발 움직임 감지 시 Abort 상태로 전환해야 한다 |
| RC-GATE-003 | Timeout 발생 시 재안내 또는 수동 전환 workflow를 제공해야 한다 |
| RC-GATE-004 | 오디오 안내와 실제 안정 구간 사이 latency offset을 설정값으로 관리해야 한다 |

### 7.3 추천 엔진

| ID | 요구사항 |
|---|---|
| RC-EXP-001 | 추천값은 사전에 승인된 LUT/룰 범위를 벗어나면 안 된다 |
| RC-EXP-002 | 추천값에는 confidence와 근거 값을 함께 표시해야 한다 |
| RC-EXP-003 | 소아/성인/비만 모드 전환 시 UI 경고를 표시해야 한다 |
| RC-EXP-004 | 최종 촬영 조건은 작업자가 확인해야 한다 |

### 7.4 UI/사용자

| ID | 요구사항 |
|---|---|
| RC-UI-001 | 추천값과 실제 장비 설정값을 시각적으로 구분해야 한다 |
| RC-UI-002 | Manual Override는 항상 접근 가능해야 한다 |
| RC-UI-003 | 오류 상태는 색상, 텍스트, 필요 시 음성으로 명확하게 표시해야 한다 |
| RC-UI-004 | 작업자 승인 이벤트는 감사로그에 기록해야 한다 |

---

## 8. Fault Injection 테스트

| Test ID | 주입 장애 | 기대 결과 |
|---|---|---|
| FI-001 | 카메라 USB 분리 | 2초 내 오류 표시, 추천 비활성화 |
| FI-002 | PoE 링크 끊김 | reconnect 시도, safe state 유지 |
| FI-003 | Depth frame timestamp 오류 | frame 폐기, 로그 기록 |
| FI-004 | SDK process crash | systemd 재시작, UI 경고 |
| FI-005 | DB write failure | 로그 오류 표시, 촬영 보조 기능 제한 |
| FI-006 | 설정 파일 변조 | 서명 검증 실패, 서비스 시작 차단 |
| FI-007 | 모델 파일 변조 | safe model rollback |
| FI-008 | Audio output failure | UI 안내로 대체, 로그 기록 |
| FI-009 | CPU/GPU 과열 | 성능 저하 경고, safe mode |
| FI-010 | 작업자 승인 없이 진행 시도 | 제어 차단 |

---

## 9. 잔여위험 관리

잔여위험은 다음 방식으로 관리한다.

- 사용자 매뉴얼에 한계 명시
- 추천값은 작업자 확인 필요 문구 표시
- 소아/비만/특수환자 모드 사용 시 주의 문구 표시
- 카메라 미신뢰 상태에서는 수동 촬영 workflow 제공
- 임상 도입 전 병원별 캘리브레이션 검증 수행
- 배포 후 현장 로그 기반 post-market surveillance 수행

---

## 10. 위험관리와 테스트 추적성 예시

| Risk ID | Requirement | Test Case | Evidence |
|---|---|---|---|
| H-001 | RC-CAM-004 | TC-CAL-001 | calibration_report.json |
| H-002 | RC-GATE-002 | TC-GATE-003 | breathing_phantom_result.csv |
| H-003 | RC-EXP-001 | TC-LUT-002 | lut_boundary_test.xml |
| H-005 | RC-UI-001 | TC-UI-004 | usability_test_report.pdf |
| H-008 | RC-UI-004 | TC-AUDIT-001 | audit_log_integrity.txt |

---

## 11. 위험관리 결론

초기 MVP는 X-ray 장비 직접 제어를 제외하고 Operator Assist로 제한해야 한다. 가장 중요한 통제는 `작업자 최종 승인`, `추천값 상하한 제한`, `카메라/캘리브레이션 오류 시 safe state`, `감사로그`, `수동 모드 전환`이다. Phase 3의 generator direct control은 별도 위험관리 파일과 HIL 테스트를 완료한 뒤 진행해야 한다.
