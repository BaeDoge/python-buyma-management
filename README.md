# BUYMA 최저가 관리 프로그램

BESTSHIP(seller ID `12217668`)의 Google Sheet 상품 URL을 기준으로 BUYMA 공개 페이지의 가격을 비교하고, 조건에 맞으면 BUYMA Product API로 가격 변경 요청을 보내는 Windows용 Python 프로그램입니다.

## 실행 파일은 하나

개발 환경에서 프로젝트 루트에서 실행합니다.

```powershell
uv sync
uv run buyma_price_manager.py
```

일반 사용자는 루트의 `buyma_price_manager.py`만 실행합니다. 별도의 BAT 파일, `refresh_prices.py`, `setup_once.py` 루트 래퍼는 제공하지 않습니다.

메뉴:

- `1`: 가격 비교 결과 확인(DRY RUN). 가격 변경 API를 호출하지 않습니다.
- `2`: 가격 비교 후 조건에 맞는 상품의 가격 변경 요청. 전체 payload 검사와 명시적인 확인 문구가 필요합니다.
- `3`: OAuth 복구 또는 선택적 상품 데이터 준비가 필요한 경우에만 사용하는 유지보수 메뉴.
- `0`: 종료.

## 초기 설정

1. `config.example.yaml`을 `config.yaml`로 복사합니다.
2. Google Sheet URL과 시트/URL 컬럼 설정을 확인합니다.
3. Google 서비스 계정 JSON을 `secrets/service_account.json`에 저장하고 해당 계정에 대상 시트를 공유합니다.
4. 기존 BUYMA OAuth 토큰을 `secrets/tokens.json`에 둡니다.
5. 개발 환경에서 `uv sync`를 실행합니다.

`config.yaml`, `.env`, `secrets/`, `data/`, `logs/`, `reports/`는 로컬 설정/고객 데이터이므로 Git에 커밋하거나 다른 구매자와 공유하지 마세요. OAuth는 토큰이 존재하고 유효한 한 일반 가격 비교를 위해 매번 다시 실행하지 않습니다.

## Google Sheet 변경

프로그램은 매 실행마다 Google Sheet URL 컬럼을 새로 읽습니다. URL을 추가하거나 삭제하기 위해 별도 migration을 실행할 필요가 없습니다. 빈 URL과 중복 URL은 건너뜁니다.

## 가격 계산

기본값은 경쟁 최저가보다 10원 낮은 가격이며, 현재가에서 100원을 초과해 인하해야 하는 상품은 건너뜁니다. 실행 메뉴에서 값을 입력할 수 있습니다.

경쟁 매장 가격 비교는 BUYMA 공개 상품 페이지를 사용합니다. 공개 Personal Shopper API에서 경쟁 매장 가격 검색 endpoint를 확인하지 못했기 때문입니다. 가격 변경은 BUYMA 공식 Product API로만 요청합니다.

## 중요한 API payload 제한

BUYMA Product API는 가격만 받는 단순 수정 endpoint가 아닙니다. `data/buyma_products.json`에 API 필수 필드를 갖춘 전체 `product` 객체가 있어야 합니다. `source_product_data`만 있거나 필수 필드가 빠진 상품은 가격 변경에서 제외합니다. 빠진 값을 임의로 추측해 보내지 않습니다.

실제 API 요청 접수(예: HTTP 201 / `request_uid`)는 최종 가격 반영 완료와 다를 수 있으므로 BUYMA 상품 화면이나 공식 webhook 결과를 확인해야 합니다.

공식 문서: [BUYMA Product API](https://specification.personal-shopper-api.buyma.com/en/api/products_json/)

## 프로젝트 구조

```text
.
├── buyma_price_manager.py       # 유일한 사용자 실행 진입점
├── config.example.yaml          # 설정 템플릿
├── pyproject.toml               # 의존성
├── app/
│   ├── manager.py               # 통합 메뉴
│   ├── setup_once.py            # 메뉴 3의 유지보수 메뉴
│   ├── oauth_server.py          # OAuth 서버
│   ├── migration.py             # 선택적 상품 ID 수집
│   ├── payload_migration.py     # 선택적 payload 수집 시도
│   └── src/buyma_price_competitor/
│       ├── runner.py            # 비교/변경 실행 흐름
│       ├── buyma_api.py         # 공식 API 클라이언트
│       ├── google_sheets.py     # Google Sheet 연동
│       └── pricing.py           # 가격 결정
├── tools/                       # 개발/유지보수 도구
├── secrets/                     # 로컬 인증정보(무시됨)
├── data/                        # 로컬 상품 payload(무시됨)
├── logs/                        # 실행 로그
└── reports/                     # 실행별 CSV 결과
```

루트에는 진입점 하나만 두고 기능 구현은 `app/` 아래에 둡니다. OAuth/상품 데이터 준비는 정상적인 가격 비교 경로와 분리되어 있으며, 일반 실행에서 자동으로 호출되지 않습니다.

## 배포

PyInstaller를 통한 Windows EXE 패키징은 별도 검증 단계입니다. 현재 저장소는 개발 실행 흐름을 단순화한 상태이며, EXE가 실제 Windows 환경에서 빌드/실행되는지 확인하기 전에는 완성된 설치 패키지로 간주하지 않습니다. EXE 안에 OAuth 토큰이나 Google 서비스 계정 키를 포함하지 않습니다.
