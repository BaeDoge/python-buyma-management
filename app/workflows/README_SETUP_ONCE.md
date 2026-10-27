# 1회성 설정 / 신규 상품 처리

이 절차는 최초 설치 또는 신규 상품이 추가되었을 때만 사용합니다. 매주 실행하지 않습니다.

## 준비

1. `config.example.yaml`을 `config.yaml`로 복사하고 Google Sheets URL, 시트 이름, URL 컬럼, BestShip 판매자 ID를 확인합니다.
2. Google 서비스 계정 JSON을 `secrets/service_account.json`에 둡니다.
3. 필요한 환경 변수를 `.env`에 설정합니다. OAuth는 `BUYMA_CLIENT_ID`, `BUYMA_CLIENT_SECRET`, `BUYMA_REDIRECT_URI`가 필요합니다. payload 조사에는 `BUYMA_LOGIN_ID`, `BUYMA_LOGIN_PASSWORD`가 필요할 수 있습니다.
4. 최초 실행은 `uv sync`로 환경을 준비한 뒤 `uv run setup_once.py`를 실행하거나 Windows에서 `setup_once.bat`을 실행합니다.

## 메뉴 순서

- **1 OAuth 승인**: 최초 1회 또는 토큰이 폐기/재승인된 경우. BUYMA 계정 로그인이 브라우저에서 필요합니다. 이후 정상 API 호출 때마다 웹 로그인하지 않습니다.
- **2 상품 ID 수집**: 신규 URL/상품이 있을 때. Google Sheets와 비로그인 공개 BUYMA 페이지를 읽고 `data/buyma_product_ids.json`을 갱신합니다. 공식 API는 사용하지 않습니다.
- **3 payload 수집 시도**: 상품이 API용 full payload를 갖고 있지 않을 때만 수동 실행합니다. BUYMA 웹 로그인 및 편집 페이지 조회가 발생할 수 있고, API 가격 변경 요청은 보내지 않습니다.

## payload 확인 게이트

`data/buyma_products.json`에 해당 ID의 `product` 객체가 있고 공식 API 필수 필드가 모두 존재하며 `has_full_payload=true`일 때만 실제 변경 테스트를 진행합니다. `source_product_data`만 저장된 상태는 full payload가 아닙니다. 이 상태에서 반복 로그인을 해도 필드 매핑이 자동으로 해결된다는 보장은 없으므로, 원본 데이터의 실제 구조를 분석해 매핑을 구현해야 합니다.

## 초기 API 검증

1. `uv run refresh_prices.py --product-id <상품ID> --price-delta 10 --max-change 100` 으로 DRY RUN합니다.
2. payload가 검증된 테스트 상품 하나에만 `uv run refresh_prices.py --apply --product-id <상품ID> --price-delta 10 --max-change 100` 을 실행합니다.
3. `request_uid`를 보관하고 BUYMA 상품 화면에서 실제 반영을 확인합니다. HTTP 요청 접수 성공은 최종 반영 완료와 같지 않습니다.

## 신규 상품

1. `uv run migration.py` 또는 `setup_once.py` 메뉴 2로 새 ID를 수집합니다.
2. 신규 ID의 payload가 미확보인 경우에만 메뉴 3을 수동 시도합니다.
3. 기존 상품의 full payload는 보존하고, 정기 실행에서는 이 메뉴를 호출하지 않습니다.
