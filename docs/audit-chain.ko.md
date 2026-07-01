# 감사 해시 체인

[← README로](../README.md)

[`audit/logger.py`](../smart-xray-assist/src/xray_assist/audit/logger.py) · 스키마 [`migrations/001_init.sql`](../smart-xray-assist/migrations/001_init.sql)

의료 시스템에서 "무엇을, 언제, 누가 승인했는가"는 사후 변조가 불가능해야 합니다. 이를 위해 **append-only SQLite + 애플리케이션 레벨 SHA-256 해시 체인**을 씁니다.

## 원리 — 블록체인식 링크

각 이벤트의 해시는 **직전 이벤트의 해시**를 포함합니다. 그래서 중간의 어떤 레코드든 바꾸면 그 이후 모든 해시가 어긋납니다.

```
event_hash(n) = SHA-256( event_hash(n−1) + canonical(payload(n)) )

genesis ──► e1 ──► e2 ──► e3 ──► … ──► eN
            │      │      │
         prev=g  prev=h1 prev=h2   (각 링크가 이전 해시를 봉인)
```

- `canonical(payload)` = `json.dumps(payload, sort_keys=True, separators=(",",":"))` — 키 정렬로 재현 가능한 직렬화
- `GENESIS_HASH = "sha256:" + "0"*64`
- 순서는 `timestamp_ms`가 아니라 **`id`(AUTOINCREMENT)** 기준. NTP가 벽시계를 되돌릴 수 있기 때문.

## 검증

`verify_chain()`은 genesis부터 전체를 재계산합니다:

```python
prev = GENESIS_HASH
for row in rows_ordered_by_id:
    if row.prev_hash != prev:            return False   # 링크 끊김
    if event_hash(payload, prev) != row.event_hash: return False  # 페이로드 변조
    prev = row.event_hash
return True
```

콘솔의 **"체인 무결성 검증"** 버튼은 `GET /api/v1/audit/verify`로 이 실제 서버 체인을 검증하고 `✓ N links verified`를 표시합니다.

## 내구성 & 동시성

- `PRAGMA journal_mode=WAL` + `synchronous=FULL` — 전원 손실 내구성(FI-008)
- 감사 DB 쓰기 실패는 `DB_WRITE_FAILED` → safe-state (조용히 삼키지 않음)
- 드라이버 스레드(파이프라인)와 FastAPI 스레드풀(REST)이 같은 연결을 공유하므로 `RLock`으로 append·조회를 직렬화. read-modify-write(seq·prev_hash·insert)가 원자적이라 동시 append가 인터리브되지 않음.

## 테이블 스키마 (요약)

```sql
audit_events(
  id INTEGER PK AUTOINCREMENT,   -- 순서의 기준
  audit_id, timestamp_ms, device_id, session_id,
  event_category, event_name, severity, actor_type, actor_id,
  payload_json,                  -- 정규화 직렬화
  payload_hash, prev_hash, event_hash   -- 해시 체인
)
```

## 기록되는 이벤트 예

세션 시작/종료, 기기 연결/해제, 추천 생성(`recommendation_generated`), 작업자 액션(승인·큐·중단·수동전환·기침), 에러 코드. 콘솔의 감사 패널은 `GET /api/v1/audit`로 이 실데이터를 렌더합니다.

관련: [API & 실시간](api-and-realtime.md)
