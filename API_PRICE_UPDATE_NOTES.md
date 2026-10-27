# API 가격 변경 패치 안내

## 변경점
- `--apply`는 더 이상 BUYMA 웹 로그인/편집 버튼을 사용하지 않습니다.
- `BuymaClient`를 통해 BUYMA Personal Shopper API의 `POST /api/v1/products.json`로 가격 변경 요청을 전송합니다.
- 대상 상품의 전체 API payload가 없거나 필수 필드가 빠진 경우 요청을 보내지 않고 오류를 기록합니다.
- `request_uid`와 접수 시각을 CSV/Google Sheets 이력 및 로컬 저장소에 기록합니다.
- API가 HTTP 201로 요청을 접수해도 실제 반영은 비동기이므로 BUYMA 상품 페이지에서 최종 가격을 확인해야 합니다.

## 단일 상품 테스트
프로젝트 루트에서:

```bash
uv run main.py --apply --product-id 137992656 --price-delta 10 --max-change 100
```

## 필수 파일
- `secrets/tokens.json`: BUYMA OAuth access token 포함
- `data/buyma_products.json`: 상품 ID별 `product` 객체에 공식 Product API 필수 필드가 모두 있어야 함
- `data/buyma_product_ids.json`: 공개 상품 검색으로 수집한 상품 인덱스 (선택적 로그/이력용)

이 ZIP에는 OAuth 토큰, 서비스 계정 키, 로컬 `data/` payload를 포함하지 않습니다. 기존 로컬 파일은 백업 후 그대로 유지하세요.

## 중요한 제한
`payload_migration.py`가 `source_product_data`만 수집했다면 그것은 API 요청용 전체 payload가 아닙니다. 이 패치는 해당 데이터를 임의로 변환하거나 누락 필드를 추측하지 않습니다. 이 경우 API 변경을 시도하지 않고 어떤 payload가 부족한지 알려줍니다.
