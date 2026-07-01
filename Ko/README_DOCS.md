# docs/README_DOCS.md — 상세 문서 인덱스

본 폴더는 스마트 호흡 연동 및 체형 맞춤형 촬영 보조 시스템의 상세 설계 문서 모음이다.

| 문서 | 역할 |
|---|---|
| `camera.md` | 3D Depth 카메라 선정, 연결, SDK/드라이버, 통신 방식 |
| `hardware.md` | 보드, 전원, 절연, 마운팅, X-ray 연동 하드웨어 |
| `regulatory.md` | 의료기기 규제, 품질시스템, 소프트웨어 생명주기 대응 |
| `risk-management.md` | 위험관리 파일 초안, hazard, risk control, safe state |
| `api-schema.md` | 내부 API, 메시지 스키마, WebSocket/gRPC/감사로그 계약 |
| `deployment.md` | 설치, systemd, 오프라인 업데이트, 롤백, 운영 Runbook |
| `verification-validation.md` | 테스트 전략, 팬텀 테스트, fault injection, acceptance criteria |

권장 루트 구조:

```text
project-root/
  README.md
  docs/
    README_DOCS.md
    camera.md
    hardware.md
    regulatory.md
    risk-management.md
    api-schema.md
    deployment.md
    verification-validation.md
```
