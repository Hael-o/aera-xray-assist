# regulatory.md — 의료기기 규제, 품질시스템, 소프트웨어 생명주기 대응 문서

작성 대상: 시니어 개발자, RA/QA 담당자, 제품 책임자, 시스템 아키텍트  
관련 문서: `README.md`, `docs/risk-management.md`, `docs/deployment.md`, `docs/api-schema.md`

---

## 1. 목적

본 문서는 스마트 호흡 연동 및 체형 맞춤형 촬영 보조 시스템의 국내외 의료기기 규제 대응 방향, 품질문서 체계, 소프트웨어 생명주기, 위험관리, 변경관리, 임상/비임상 검증 전략을 정리한다.

본 문서는 법률 자문 또는 최종 인허가 판단이 아니다. 실제 등급과 심사 전략은 사용목적, 제어 범위, 임상적 의사결정 개입 수준, X-ray 장비와의 통합 방식에 따라 RA 전문가 및 시험기관과 별도로 확정해야 한다.

---

## 2. 제품 범위와 규제 리스크

### 2.1 Phase별 규제 관점

| Phase | 기능 | X-ray 직접 제어 | 규제 리스크 | 권장 설명 |
|---|---|---:|---|---|
| Phase 1 | Operator Assist | 없음 | 낮음~중간 | 체형/호흡 측정 보조 및 추천 표시 |
| Phase 2 | Workstation Agent | 간접 입력 | 중간~높음 | 작업자 승인 전제의 반자동 파라미터 입력 |
| Phase 3 | Generator Direct Control | 있음 | 높음 | 의료기기 구성품 또는 제어 SW 가능성 큼 |
| Phase 4 | On-device Learning | 기능에 따라 상이 | 높음 | 변경관리/성능검증/모델관리 부담 증가 |

초기 제품 정의는 Phase 1로 제한한다.

권장 사용목적 문구:

```text
본 시스템은 3D Depth 센서를 이용하여 환자의 체형 및 호흡 안정성을 측정하고, X-ray 촬영 전 작업자에게 참고용 추천값과 호흡 상태 정보를 제공하는 보조 시스템이다. 최종 촬영 조건 설정과 촬영 수행은 자격을 갖춘 작업자가 승인한다.
```

금지 또는 주의 문구:

```text
자동으로 최적 선량을 결정한다.
작업자 개입 없이 촬영을 수행한다.
모든 환자에게 최적 kVp/mAs를 보장한다.
재촬영을 완전히 방지한다.
```

---

## 3. 적용 검토 표준

| 표준/규정 | 적용 목적 | 본 시스템 적용 포인트 |
|---|---|---|
| ISO 13485 | 의료기기 품질경영시스템 | 요구사항, 설계관리, 변경관리, CAPA |
| ISO 14971 | 의료기기 위험관리 | 위해요인 식별, 위험통제, 잔여위험 평가 |
| IEC 62304 | 의료기기 소프트웨어 생명주기 | SW 요구사항, 아키텍처, 구현, 검증, 유지보수 |
| IEC 62366 | 사용적합성 공학 | 작업자 UI, 경고, 승인, 수동전환 |
| IEC 60601-1 | 의료용 전기기기 안전 | 전원, 절연, 누설전류 검토 |
| IEC 60601-1-2 | EMC | 촬영실 전자파 환경 검토 |
| IEC 62366-1 | usability engineering | 오조작 방지 및 사용자 workflow 검증 |
| 개인정보보호법 | 개인정보/민감정보 보호 | RGB/Depth 저장 제한, 비식별화, 접근통제 |
| 의료기기 사이버보안 가이드 | 보안 설계 | 인증, 암호화, 로그, 업데이트 무결성 |

---

## 4. 소프트웨어 안전 등급 접근

IEC 62304 관점에서 소프트웨어 안전 등급은 제품이 실패했을 때 발생 가능한 위해 정도에 따라 결정된다. 본 시스템은 Phase 1에서는 직접 촬영을 수행하지 않지만, 잘못된 추천으로 작업자가 잘못된 조건을 입력할 가능성이 있으므로 안전 등급을 낮게 단정하지 않는다.

권장 접근:

| 모듈 | 잠재 영향 | 안전 등급 접근 |
|---|---|---|
| camera_service | 측정 실패/오측정 | 중간 이상 검토 |
| depth_processor | 두께 계산 오류 | 중간 이상 검토 |
| respiration_gating | 호흡 안정성 오판단 | 중간 이상 검토 |
| exposure_recommender | 부적절한 추천값 | 중간 이상 검토 |
| operator_ui | 오인/오조작 | 중간 이상 검토 |
| audit_logger | 추적성 상실 | 품질/보안 중요 모듈 |
| device_gateway | 장비 제어 오류 | 높음 |

제품화 전 RA/QA와 최종 안전 등급을 확정한다.

---

## 5. 설계관리 문서 체계

권장 문서 세트:

```text
docs/
  requirements.md
  architecture.md
  hardware.md
  camera.md
  risk-management.md
  regulatory.md
  api-schema.md
  deployment.md
  verification-validation.md
  cybersecurity.md
  usability.md
  clinical-evaluation-plan.md
```

필수 추적성:

```text
User Need
  → System Requirement
    → Software Requirement
      → Architecture Component
        → Test Case
          → Test Result
            → Risk Control Evidence
```

---

## 6. 요구사항 ID 체계

| Prefix | 의미 | 예시 |
|---|---|---|
| UN | User Need | UN-001 작업자는 환자 호흡 안정 상태를 확인할 수 있어야 한다 |
| SYS | System Requirement | SYS-001 시스템은 Depth 기반 흉부 움직임을 실시간 측정해야 한다 |
| SW | Software Requirement | SW-001 camera_service는 30 FPS Depth stream을 제공해야 한다 |
| HW | Hardware Requirement | HW-001 카메라는 촬영 테이블 ROI를 95% 이상 커버해야 한다 |
| RISK | Risk Control | RISK-001 카메라 오류 시 추천값을 비활성화해야 한다 |
| TC | Test Case | TC-001 카메라 연결 해제 시 UI 경고 표시 검증 |

---

## 7. 주요 규제 리스크와 대응 방향

### 7.1 자동 선량 결정 오해

리스크:

- 시스템이 의료적 의사결정을 직접 수행하는 것으로 해석될 수 있음
- 잘못된 kVp/mAs 추천 시 과다/과소 피폭 가능성

대응:

- 추천값은 참고용임을 UI에 명시
- 최종 승인은 작업자가 수행
- 추천값의 최대/최소 범위 제한
- 추천 근거와 모델/룰 버전 로그 저장

### 7.2 X-ray 직접 제어

리스크:

- 장비 제어 소프트웨어로 분류될 가능성
- 전기안전/EMC/상호운용성 시험 필요

대응:

- Phase 1 범위에서 제외
- Phase 2/3는 별도 제품 버전으로 분리
- 장비 제조사 API 문서와 계약 확보
- 장비 제어 failure mode 분석

### 7.3 자가학습/지속학습

리스크:

- 배포 후 모델 성능 변화
- 검증되지 않은 모델이 임상 workflow에 영향

대응:

- 초기 제품 범위 제외
- 오프라인 검증된 signed model만 적용
- 로컬 학습은 연구/고도화 기능으로 분리
- 신규 모델은 golden test suite 통과 후 적용

---

## 8. 사이버보안 규제 대응

기본 원칙:

- 원본 RGB/Depth 저장 금지
- 최소 권한 접근
- 오프라인 업데이트 패키지 서명 검증
- 감사로그 무결성 보장
- 유지보수 계정 통제

권장 보안 요구사항:

| 영역 | 요구사항 |
|---|---|
| Authentication | 관리자 계정, 역할 기반 접근제어 |
| Authorization | 작업자/관리자/서비스 계정 권한 분리 |
| Update | signed package, rollback, version pinning |
| Data Protection | disk encryption, sensitive data minimization |
| Network | camera VLAN 분리, mTLS optional |
| Logging | append-only audit log, hash chain |
| Hardening | USB 제한, SSH 기본 차단 또는 key-only |

---

## 9. 사용적합성 고려

Operator Assist UI에서 반드시 검토해야 할 요소:

- 추천값과 실제 설정값 구분
- 작업자 승인 버튼 명확화
- 경고/Abort 상태 색상 및 음성 안내
- Manual Override 접근성
- 환자 호흡 불안정 시 재안내 workflow
- 카메라 오류 시 추천값 숨김 또는 비활성화
- 소아/성인/고도비만 등 모드 전환 시 경고

사용적합성 테스트 시나리오:

| 시나리오 | 검증 포인트 |
|---|---|
| 카메라 인식 실패 | 작업자가 오류를 인지하고 수동 촬영으로 전환 가능한가 |
| 호흡 정지 실패 | 재안내/Abort 절차가 명확한가 |
| 추천값 표시 | 참고값과 확정값이 혼동되지 않는가 |
| 응급 촬영 | 시스템을 우회하고 즉시 수동 모드로 갈 수 있는가 |

---

## 10. 검증 및 밸리데이션 전략

### 10.1 비임상 검증

- 정적 거리 정확도 테스트
- 동적 호흡 팬텀 테스트
- 장시간 프레임 드롭 테스트
- 추천값 LUT 경계값 테스트
- 카메라 오류/프레임 누락/전원 차단 fault injection
- UI 승인/Abort workflow 테스트

### 10.2 임상 workflow 검증

초기에는 임상 진단 성능을 주장하지 않고 workflow 보조 성능을 관찰한다.

관찰 지표:

- 촬영 전 준비 시간
- 재촬영률 변화
- 작업자 입력 오류 감소 여부
- 호흡 안내 성공률
- 작업자 만족도
- 카메라 측정 실패율

---

## 11. 변경관리

변경 영향도 분류:

| 변경 | 영향도 | 요구 조치 |
|---|---|---|
| UI 문구 수정 | 낮음~중간 | 사용적합성 영향 검토 |
| 카메라 SDK 버전 변경 | 중간 | regression test 필요 |
| 추천 LUT 변경 | 높음 | 위험분석, 검증, 승인 필요 |
| AI 모델 변경 | 높음 | 모델 검증, signed release 필요 |
| X-ray 제어 모듈 추가 | 매우 높음 | 별도 인허가 전략 필요 |

---

## 12. 릴리즈 승인 기준

릴리즈 전 필수 산출물:

- 요구사항 명세서
- 소프트웨어 아키텍처 문서
- 위험관리 파일
- 검증 테스트 결과
- known issue 목록
- 설치/운영 매뉴얼
- 사이버보안 체크리스트
- 소프트웨어 버전 및 SBOM
- rollback 계획

---

## 13. 결론

초기 제품은 Phase 1 Operator Assist로 정의하고, X-ray 직접 제어와 on-device continual learning은 후속 고도화 범위로 분리한다. 규제 문서에서는 등급을 단정하지 않고, 사용목적과 위험도에 따른 별도 판단이 필요하다는 구조를 유지한다. 개발팀은 README와 본 문서를 기준으로 요구사항-위험관리-테스트 추적성을 확보해야 한다.
