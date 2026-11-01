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
| 1 | Google Sheet URL에서 BESTSHIP 상품 ID 수집 |
| 2 | BUYMA 로그인 후 상품 payload 수집 시도 |
| 3 | 전체 상품 가격 비교 미리보기. 실제 가격 변경 없음 |
| 4 | 상품 ID 하나를 입력해 미리보기 후 해당 상품 하나만 실제 변경 테스트 |
| 5 | 조건에 맞는 전체 상품 가격 변경 |
| 0 | 종료 |

**처음 실행할 때:** 1 → 2 → 3 순서로 진행합니다. 이후에는 시트 URL을 매번 새로 읽으므로 평소에는 3번(비교) 또는 4번(단일 테스트), 검증 완료 후 5번(전체 변경)만 사용하면 됩니다.

### 단일 상품 테스트 (메뉴 4)

1. 테스트할 BUYMA 상품 ID를 입력합니다.
2. 프로그램이 해당 ID만 공개 상품 페이지에서 찾아 현재가/경쟁 최저가/변경 예정가를 계산합니다.
3. 화면에 표시된 변경 예정가를 확인합니다.
4. 실제 변경할 때만 `CHANGE-상품ID-변경예정가`를 입력합니다.
5. 프로그램은 API 요청 직전에 가격을 다시 계산합니다. 미리보기 가격과 달라졌다면 요청을 중단합니다.

다른 상품은 단일 테스트의 API 변경 대상이 되지 않습니다. 단일 테스트는 해당 상품의 공식 API 전체 payload가 준비되어 있어야 하며, payload가 없거나 필수 필드가 빠져 있으면 요청하지 않습니다.

### 전체 변경 (메뉴 5)

전체 변경은 별도 확인 문구 `APPLY-ALL-변경금액-최대인하폭`를 입력해야 진행됩니다. 단일 상품 테스트를 먼저 완료한 뒤 사용하세요.

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
├── buyma_price_manager.py
├── config.example.yaml
├── pyproject.toml
├── uv.lock
└── app/
    ├── manager.py
    ├── migration.py
    ├── payload_migration.py
    ├── setup_once.py
    └── src/buyma_price_competitor/
        ├── runner.py
        ├── buyma_api.py
        ├── config.py
        ├── google_sheets.py
        ├── payload_mapper.py
        ├── payload_store.py
        ├── pricing.py
        └── public_products.py
```

실행 결과는 `logs/`와 `reports/`, 상품 데이터는 `data/`에 저장됩니다. 이 폴더들은 실행 시 자동 생성되며 저장소에는 포함하지 않습니다.
