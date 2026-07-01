# 노출 추천 & 안전

[← README로](../README.md)

## 노출 추천 (LUT + 가드레일)

[`exposure/recommender.py`](../smart-xray-assist/src/xray_assist/exposure/recommender.py) · [`configs/exposure_lut.yaml`](../smart-xray-assist/configs/exposure_lut.yaml)

안정적인 호흡 정지가 검출되면, **추정 두께 + 부위 + 환자 모드**로 서명된 룩업 테이블에서 kVp/mAs를 조회합니다.

```
두께(mm) + body_region(chest_pa) + mode(adult|pediatric|bariatric)
        └→ LUT 행 조회 → kVp/mAs → 가드레일 클램프 → 추천
```

### LUT (v1.3.0, 서명됨)

| 모드 | 두께 범위(mm) | kVp | mAs | 비고 |
|---|---|---|---|---|
| adult | 0–180 | 70 | 8.0 | |
| adult | 181–240 | 82 | 15.0 | |
| adult | 241–320 | 90 | 22.0 | |
| pediatric | 0–120 | 60 | 4.0 | 임상 검토 대기 |
| bariatric | 321–450 | 100 | 40.0 | 임상 검토 대기 |

- **서명(`signed: true`)**: LUT는 QA 승인·서명 대상. 무결성이 보장된 표만 사용.
- **임상 검토 대기 행**: 해당 두께가 검토 대기 행에 걸리면 **자동 추천 없음** → `manual_review_required=true`. kVp/mAs 대신 "수동 검토 필요" 메시지만 표시.

### 가드레일 클램프

LUT 값이라도 물리적 안전 범위를 벗어나지 않도록 클램프합니다:

```
kVp ∈ [60, 120]      mAs ∈ [1.0, 80.0]
```

클램프가 일어나면 추천에 `within_min_max=false`가 실려 콘솔에 "클램프됨" 배지가 뜹니다.

---

## 안전 모델

### Reference-only (참고 전용)

추천은 **제안일 뿐** 자동 적용되지 않습니다. 흐름:

```
추천 발행 → 작업자 검토 → 명시적 승인(POST /operator/approve) → 감사 기록
                                                    └→ 실제 적용은 X선 장비 수동 워크플로에서 작업자가 수행
```

시스템은 X선을 발사하지도, 장비 파라미터를 설정하지도 않습니다. 승인은 "이 참고 값을 봤고 수용한다"는 감사 기록일 뿐입니다.

### Fail-to-manual (safe-state)

결함 발생 시 즉시 수동 모드로 전락하고 추천을 비활성화합니다. 트리거·코드는 [아키텍처 문서의 safe-state 표](architecture.md#safe-state-수동-모드) 참고. 핵심은:

- **X선 장비 고유의 수동 워크플로는 절대 건드리지 않음** — 이 시스템이 죽어도 촬영은 평소대로 가능
- transient 결함(일시적 저신뢰 등)은 좋은 프레임 복귀 시 자동 해제

### 승인 게이팅

- 추천이 `manual_review_required`이면 승인 버튼 비활성화
- safe-state에서는 모든 승인 차단
- 승인된 `recommendation_id`만 `is_approved()`로 인정

관련: [감사 해시 체인](audit-chain.md) · [깊이 처리 & 게이팅](depth-and-gating.md)
