# BUYMA 가격 경쟁 자동화 (Windows + uv)

이 패키지는 루트에서 `uv` 가상환경을 관리하고, 애플리케이션 소스는 `app/` 안에 두는 구조입니다. `.env`, `config.yaml`, `secrets/`, `data/`에는 실제 계정 정보가 들어갈 수 있으므로 공유 ZIP에 포함하지 않았습니다.

## 판매자/API 승인 후 재개 순서

1. BUYMA Partners에서 앱이 승인/활성 상태인지 확인하고 Client ID/Secret이 현재 앱 값인지 확인합니다.
2. `.env.example`을 `.env`로 복사해 `BUYMA_CLIENT_ID`, `BUYMA_CLIENT_SECRET`, `BUYMA_REDIRECT_URI`를 입력합니다. API는 운영 환경 기준입니다.
3. ngrok 계정 토큰을 Windows CMD에 `set NGROK_AUTHTOKEN=...`으로 설정합니다. 토큰을 소스코드에 저장하지 마세요.
4. 첫 번째 CMD에서 `run_ngrok_tunnel.bat`을 실행하고 출력된 HTTPS 주소를 확인합니다. 주소에 `/callback`을 붙여 BUYMA Partners의 Callback Redirect URL과 `.env`의 `BUYMA_REDIRECT_URI`에 정확히 동일하게 등록합니다. 주소가 바뀌면 양쪽도 갱신합니다. 터널은 켜 둡니다.
5. 두 번째 CMD에서 `run_oauth.bat`을 실행합니다. 브라우저에서 `http://127.0.0.1:8000/login`을 열어 BUYMA 로그인/앱 설치 승인을 완료합니다. 성공 화면이 나와야 토큰이 `secrets/tokens.json`에 저장됩니다.
6. `run_api_check.bat`으로 주문 조회 GET만 테스트합니다. 이 테스트는 상품을 변경하지 않습니다. HTTP 200이면 주문 조회 API 인증 성공입니다. 401이면 OAuth 토큰/환경/헤더, 403이면 판매자 권한이나 앱 권한을 확인합니다.
7. 가격 자동화는 기본 DRY RUN입니다. 실제 가격 변경은 payload가 검증되고 한 상품 테스트를 별도로 승인한 후에만 `--apply`로 수행하세요.

> OAuth 승인 성공과 API 권한은 별도로 검증해야 합니다. 이 패키지는 상품 변경을 자동으로 실행하지 않습니다.

---


현재는 Python 스크립트로 개발/검증하고, 기능 검증이 끝난 뒤에만 Windows용 PyInstaller 프로그램으로 패키징합니다. 지금은 exe를 만들지 않습니다.

## 실행 프로그램 2개

### 1. `setup_once.py` — 최초 1회 / 신규 상품 처리

```bash
uv sync
uv run setup_once.py
```

Windows에서는 `setup_once.bat`을 실행합니다.

| 메뉴 | 작업 | BUYMA 웹 로그인 | 공식 API |
|---|---|---|---|
| 1 | OAuth 권한 승인 및 토큰 발급 | 브라우저 인증 필요 | OAuth 토큰 endpoint 사용 |
| 2 | 공개 페이지에서 BestShip 상품 ID 수집 | 불필요 | 사용하지 않음 |
| 3 | 상품 payload 수집 시도 | 필요할 수 있음, 상품 편집 페이지 방문 | 가격 변경 API는 호출하지 않음 |

메뉴 1은 최초 1회 또는 토큰 재승인 시, 메뉴 2는 새 URL/상품이 있을 때, 메뉴 3은 full payload가 없을 때만 수동으로 실행합니다. 정기 실행에는 포함하지 않습니다.

### 2. `refresh_prices.py` — 정기 최저가 갱신

기본은 실제 변경을 하지 않는 DRY RUN입니다.

```bash
uv run refresh_prices.py --price-delta 10 --max-change 100
```

상품 하나만 비교:

```bash
uv run refresh_prices.py --product-id 137992656 --price-delta 10 --max-change 100
```

실제 변경은 payload 검증 및 단일 상품 반영 확인 후에만 실행합니다.

```bash
uv run refresh_prices.py --apply --product-id 137992656 --price-delta 10 --max-change 100
```

검증 후 전체 대상에 적용:

```bash
uv run refresh_prices.py --apply --price-delta 10 --max-change 100
```

Windows 배치 파일:
- `run_recurring_dry_run.bat`: DRY RUN
- `run_recurring_apply.bat`: 실제 API 요청 전 `APPLY` 입력 확인

## 정확한 최초 실행 순서

1. `config.example.yaml`을 `config.yaml`로 복사하고 시트 URL, 시트 이름, URL 컬럼, BestShip 판매자 ID를 확인합니다.
2. Google 서비스 계정 파일을 `secrets/service_account.json`에 둡니다.
3. OAuth 환경변수 `BUYMA_CLIENT_ID`, `BUYMA_CLIENT_SECRET`, `BUYMA_REDIRECT_URI`를 `.env`에 설정합니다.
4. `uv sync`를 실행합니다.
5. `uv run setup_once.py`의 메뉴 1에서 OAuth 승인/토큰 발급을 진행합니다. BUYMA 계정 인증은 이 초기 승인 때 필요합니다.
6. 메뉴 2에서 상품 ID를 수집합니다. BUYMA 웹 로그인은 하지 않고 공개 페이지를 읽습니다.
7. `data/buyma_product_ids.json`에서 대상 ID가 있는지 확인합니다.
8. `data/buyma_products.json`에 API 필수 필드가 포함된 `product` 객체가 실제로 존재하고 `has_full_payload=true`인지 확인합니다. 없다면 메뉴 3으로 payload 수집을 수동 시도할 수 있지만, 성공을 보장하지 않습니다.
9. `uv run refresh_prices.py --product-id <상품ID> --price-delta 10 --max-change 100` 으로 DRY RUN 결과를 확인합니다.
10. payload가 검증된 테스트 상품 하나만 `--apply`로 요청하고, BUYMA 상품 화면에서 실제 가격 반영을 확인합니다. `request_uid`와 로그를 보관합니다.

## 매주 2회 정기 실행 순서

1. `uv run refresh_prices.py --price-delta 10 --max-change 100` 으로 DRY RUN을 실행합니다.
2. 가격 변경 후보, 신규 가격, payload 상태, 오류 로그를 검토합니다.
3. API 실제 반영이 검증된 뒤에만 `--apply`를 사용합니다.
4. 정기 실행에는 `setup_once.py`, `migration.py`, `payload_migration.py`를 포함하지 않습니다. 신규 상품을 추가했을 때만 최초 1회 작업으로 돌아갑니다.

## 로그인 / 공개 조회 / API 사용 구분

| 기능 | BUYMA 웹 로그인 | 비로그인 공개 페이지 조회 | 공식 API |
|---|---|---|---|
| Google Sheets 읽기 | 아니오 | 아니오 | 아니오 |
| 상품 ID 발견 (`migration.py`) | 아니오 | 예 | 아니오 |
| 경쟁 최저가 비교 (`refresh_prices.py`) | 아니오 | 예 | 아니오 |
| DRY RUN | 아니오 | 가격 비교 과정에서 사용 | 아니오 |
| 실제 가격 변경 | 아니오 | 가격 비교 과정에서 사용 | 예 |
| payload 수집 (`payload_migration.py`) | 예/로그인 필요 가능 | 아니오, 편집 페이지 | 가격 변경 API는 호출하지 않음 |

중요: 현재 공식 API로 처리되는 것은 가격 변경 요청입니다. 경쟁 가격을 가져오는 부분은 여전히 로그인 없는 공개 페이지 조회이며, API로 완전히 대체되지 않았습니다. 비로그인 조회도 무제한으로 해도 된다는 뜻은 아닙니다. 요청 빈도를 적절히 제한하고 BUYMA 이용 조건을 준수하세요.

## Payload의 현재 한계

BUYMA Product API는 가격만으로 수정 요청을 만들 수 없고, `control`, `name`, `comments`, `brand_id`, `category_id`, `price`, `available_until`, `buying_area_id`, `shipping_area_id`, `images`, `shipping_methods`, `options`, `variants` 등 필수 정보가 필요합니다.

현재 `payload_migration.py`가 일부 상품에서 `source_product_data`만 확보할 수 있습니다. 이것은 API용 full payload가 아닙니다. 누락 필드를 추측해서 채우지 않습니다. `has_full_payload=true`와 실제 필드 검증을 통과하지 못한 상품은 `--apply` 대상에서 제외됩니다. 이 데이터 매핑이 완성되기 전까지 자동 가격 변경이 모든 상품에서 가능한 것은 아닙니다.

## 데이터 및 비밀정보

- `data/buyma_product_ids.json`: 발견한 상품 ID 및 메타데이터
- `data/buyma_products.json`: API용 payload 또는 수집한 source data
- `secrets/tokens.json`: BUYMA API 토큰
- `secrets/service_account.json`: Google 서비스 계정
- `logs/`, `reports/`: 실행 기록

`secrets/`와 실제 payload/개인정보 파일을 공개 저장소나 공유 ZIP에 넣지 마세요.

## PyInstaller — 나중에 수행

아직 패키징하지 않습니다. 최종 기능 검증이 끝나면 Windows에서 `build_windows_exe.bat`을 실행합니다. 스크립트는 `refresh_prices.py`를 진입점으로 `--onedir` 패키지를 만들도록 준비되어 있습니다. Windows exe는 Windows에서 빌드해야 합니다. `config.yaml`, `secrets`, `data`는 별도로 배치하고 exe에 토큰이나 서비스 계정 파일을 내장하지 마세요.
