# BUYMA BESTSHIP 최저가 관리

Google Sheet의 `[2]최저가` 탭에 등록된 URL에서 BESTSHIP 상품과 경쟁 판매자의 가격을 비교합니다. 가격 변경은 BUYMA Product API로 요청합니다. 통화 단위는 JPY(엔)입니다.

## 실행

프로젝트 루트에서 최초 1회:

```powershell
uv sync
```

이후 매번 아래 명령 하나만 실행합니다.

```powershell
uv run buyma_price_manager.py
```

## 메뉴

| 메뉴 | 기능 |
|---|---|
| 1 | 전체 상품 가격 비교 미리보기. 실제 가격 변경 없음 |
| 2 | 상품 ID 하나를 입력해 미리보기 후 해당 상품 하나만 실제 변경 테스트 |
| 3 | 조건에 맞는 전체 상품 가격 변경 |
| 0 | 종료 |

Google Sheets의 `[2]최저가` 탭에서 URL을 매번 새로 읽습니다. 처음에는 1번으로 비교 결과를 확인하고, 2번으로 단일 상품 변경을 테스트한 뒤 3번 전체 변경을 사용하세요.

### 단일 상품 테스트 (메뉴 2)

1. 테스트할 BUYMA 상품 ID를 입력합니다.
2. 프로그램이 해당 ID만 공개 상품 페이지에서 찾아 현재가/경쟁 최저가/변경 예정가를 계산합니다.
3. 화면에 표시된 변경 예정가를 확인합니다.
4. 실제 변경 확인 질문에 Y를 입력합니다.
5. 프로그램은 API 요청 직전에 가격을 다시 계산합니다. 미리보기 가격과 달라졌다면 요청을 중단합니다.

다른 상품은 단일 테스트의 API 변경 대상이 되지 않습니다. 단일 테스트는 해당 상품의 공식 API 전체 payload가 준비되어 있어야 하며, payload가 없거나 필수 필드가 빠져 있으면 요청하지 않습니다.

### 전체 변경 (메뉴 3)

전체 변경은 별도 확인 문구 `APPLY-ALL-변경금액-최대인하폭`를 입력해야 진행됩니다. 단일 상품 테스트를 먼저 완료한 뒤 사용하세요.

## Google Sheets 보고서

가격 비교/변경 실행이 끝나면 결과 CSV와 동일한 컬럼 및 행을 Google Sheets에 기록합니다.

- `api 가격변경 시트`: 가장 최근 실행 결과로 덮어씁니다.
- `[6] 최저가 적용이력-공식API`: 가격 비교/변경 실행 보고서를 실행할 때마다 아래로 누적합니다. 탭이 없으면 자동 생성합니다.
- `[5] 최저가 적용이력`: 기존 데이터와 탭을 보존합니다. 공식 API 보고서는 이 탭에 추가하지 않습니다.
- 로컬 CSV 보고서는 `reports/`에 실행별 파일로 저장됩니다.

새 이력 탭 이름은 `config.yaml`의 `google.api_history_sheet`에서 변경할 수 있습니다. 기본값은 `[6] 최저가 적용이력-공식API`입니다.

## 가격 규칙

기본값은 경쟁 최저가보다 10엔 낮게 설정하고, 현재가에서 최대 100엔을 초과해 인하해야 하면 건너뜁니다. 실행할 때 값을 변경할 수 있습니다.

- 가격 비교: BUYMA 공개 상품 페이지
- 실제 가격 변경: BUYMA Personal Shopper Product API
- API의 HTTP 201 및 `request_uid`는 요청 접수이며 최종 가격 반영 완료를 뜻하지 않습니다. BUYMA 상품 화면에서 반영 여부를 확인해야 합니다.

## 설정 파일

- `config.yaml`: `config.example.yaml`을 복사해 Google Sheet URL과 시트 설정을 입력
- `secrets/service_account.json`: Google 서비스 계정 키
- `secrets/tokens.json`: BUYMA OAuth 토큰
- `.env`: OAuth 및 BUYMA 웹 로그인 환경변수

인증정보와 실제 상품 데이터는 Git에 올리지 않습니다.

## 테스트

```powershell
uv run pytest app/tests -q
```

이 테스트는 가짜 HTTP 응답을 사용하는 자동화 테스트입니다. BUYMA에 실제 가격 변경 요청을 보내지 않습니다.

## 폴더 구조

```text
.
├── buyma_price_manager.py             # 프로젝트 실행 진입점
├── config.example.yaml                # 설정 예시
├── pyproject.toml / uv.lock           # 의존성
└── app/
    ├── manager.py                     # 메뉴 및 실행 제어
    ├── migration.py                   # 상품 ID 수집 도구
    ├── payload_migration.py           # 판매자 로그인/원본 데이터 수집
    └── src/buyma_price_competitor/
        ├── runner.py                  # 가격 비교 및 변경 흐름
        ├── reporting.py               # CSV 및 Google Sheets 보고서 저장
        ├── buyma_api.py               # BUYMA 공식 API 통신
        ├── google_sheets.py           # Google Sheets 입출력
        ├── config.py                  # 설정 로딩
        ├── browser.py                 # Chrome/Playwright 실행
        ├── public_products.py         # 공개 상품/판매자 정보 수집
        ├── payload_mapper.py          # 판매자 데이터 → API payload 변환
        ├── payload_store.py           # 상품 데이터 저장
        ├── source_to_api.py           # 원본 데이터 변환 보조
        └── pricing.py                 # 가격 결정 규칙
```

실행 결과는 `logs/`와 `reports/`, 상품 데이터는 `data/`에 저장됩니다. 이 폴더들은 실행 시 자동 생성되며 저장소에는 포함하지 않습니다.
