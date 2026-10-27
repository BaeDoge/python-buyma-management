# BUYMA payload migration v2

## 목적

기존 `payload_migration.py`는 공식 API payload에 필요한 필드가 한 JSON 객체에 모두 존재해야만 수집 성공으로 판단했습니다. 하지만 관측된 `GET /rorapi/sell/products/{id}` 응답은 `{ "data": {...}, "meta": ... }` 형태이며 필드 구조가 달라 기존 판별식에서 누락됐습니다.

v2는 이 응답을 `source_product_data`로 저장합니다. **이 데이터는 공식 Product API에 바로 전송 가능한 payload가 아닙니다.** 특히 `control`, `buying_area_id`, `shipping_area_id`, `options`, `variants` 등의 정확한 매핑은 검증하지 않았으므로 임의로 생성하지 않습니다.

## 적용

1. 프로젝트 루트에서 기존 `payload_migration.py`를 백업합니다.
2. 이 파일을 프로젝트 루트의 `payload_migration.py`로 복사/이름 변경합니다.
3. 프로젝트 루트에서 실행합니다.

```bash
uv run payload_migration.py
```

## 저장 결과

- 기존 설정의 `settings.product_payloads` 파일: 상품별 `source_product_data`, `source_summary`, `migration_status`를 체크포인트 저장
- `data/migration_debug/source_product_{상품ID}.json`: 원본 `data` 객체만 별도 저장
- 추출 실패 시 `data/migration_debug/payload_{상품ID}.json` 및 HTML 진단 파일 저장
- `buyma_product_ids.json`: 원본 데이터 확보 여부는 `has_source_data`, 공식 payload 스키마 검증 여부는 `has_full_payload`로 분리

## 안전성

이 스크립트는 BUYMA 상품을 수정하거나 가격 업데이트 API를 호출하지 않습니다. 로그인 후 편집 페이지에서 읽기 전용 응답을 수집합니다. `has_source_data`는 `has_full_payload`로 취급되지 않습니다.
