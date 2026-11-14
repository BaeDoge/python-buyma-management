# BUYMA 최저가 관리

Google Sheets에 등록한 상품 URL을 기준으로 BUYMA의 경쟁 가격을 비교하고, 조건에 맞는 BestShip 상품을 BUYMA Personal Shopper Product API로 변경하는 프로그램입니다.

## 실행 방법

프로젝트 폴더에서 처음 한 번 실행합니다.

```bat
uv sync
```

메뉴형 프로그램:

```bat
uv run buyma_price_manager.py
```

정해진 시간에 자동으로 실행하려면 별도 예약 실행기를 실행합니다.

```bat
uv run buyma_price_scheduler.py
```

## 메뉴

| 메뉴 | 내용 |
|---|---|
| 1 | 전체 상품 가격 비교 미리보기 |
| 2 | 상품 ID 하나를 선택해 미리보기 후 가격 변경 |
| 3 | 조건에 맞는 전체 상품 가격 변경 |
| 0 | 종료 |

전체 변경은 화면에서 Y/N으로 시작 여부를 결정합니다. 숫자나 긴 확인 문구를 입력할 필요는 없습니다.

## Google Sheets 탭

| 탭 이름 | 용도 |
|---|---|
| `[2]최저가` | 비교할 BUYMA URL 입력. 실행 때마다 다시 읽습니다. |
| `api 가격변경 시트` | 가장 최근 실행 결과. 매 실행마다 덮어씁니다. |
| `api 가격변경 시트 이력` | 프로그램 실행 1회당 한 줄씩 실행 시각, 실행 방식, URL/상품 수, 변경 요청 수, 변경된 상품 URL, 가격 기준을 기록합니다. 예전 상품별 기록은 새 요약 형식으로 바뀌며 이후 실행 내역은 계속 누적됩니다. |
| `[6] 최저가 적용이력-공식API` | CSV 보고서와 같은 열과 행으로 전체 실행 결과를 누적합니다. |
| `[5] 최저가 적용이력` | 기존 탭. 프로그램은 이 탭을 변경하지 않습니다. |

이름은 `config.yaml`의 `google` 항목에서 조정할 수 있습니다. 탭이 없으면 실행 중 자동 생성합니다.

## 가격 계산

`config.yaml`에서 기본 값을 설정합니다.

```yaml
app:
  price:
    delta: 10
    max_change: 50
```

- `delta`: 경쟁 최저가보다 몇 엔 낮출지 지정합니다.
- `max_change`: 현재 가격에서 한 번에 인하할 수 있는 최대 금액입니다.

타임세일 상품은 `.env`의 `BUYMA_ALLOW_TIMESALE_PRICE_UPDATE`로 제어합니다. false면 제외하고, true면 판매자 편집 화면의 실제 상품 기본 가격을 다시 확인한 뒤 변경 후보로 처리합니다.

## 예약 실행 설정

`.env`에 아래 값을 지정합니다.

```env
BUYMA_SCHEDULE_TIMES=06:00,12:00,18:00,00:00
BUYMA_SCHEDULE_PRICE_DELTA=10
BUYMA_SCHEDULE_MAX_CHANGE=50
BUYMA_SCHEDULE_HEADLESS=true
```

예약 시각은 PC 현지 시간입니다. `BUYMA-Scheduler.exe` 또는 `buyma_price_scheduler.py`는 실행 상태로 계속 켜 두어야 합니다. 같은 시간에 중복 실행되지 않도록 실행 기록을 `data/scheduler_runs.json`에 저장합니다. 예약 실행 중 로그인 추가 인증이 필요하면 키보드 입력을 기다리지 않고 해당 회차를 중단합니다.

## Windows EXE 빌드

Windows에서 아래 파일을 실행합니다.

```bat
build_exe.bat
```

`dist/`에 `BUYMA-Manager.exe`와 `BUYMA-Scheduler.exe`가 만들어집니다. GitHub Actions의 **Build Windows executables** 작업도 수동 실행하거나 main에 반영된 코드가 바뀔 때 실행 파일을 빌드하고, `BUYMA-Windows-Executables` 아티팩트로 30일간 제공합니다. 빌드 및 배포 방법은 [사용 매뉴얼](docs/USER_MANUAL.md)과 [EXE 빌드 안내](docs/BUILD_EXE.md)를 참고하세요.

## 설정 파일과 인증정보

- `config.yaml`: BestShip 판매자 정보, Google Sheets 주소, 가격 기준과 Chrome 경로
- `.env`: BUYMA 로그인, 타임세일 설정 및 예약 실행 시간
- `.env.oauth.example`: BUYMA OAuth 토큰을 새로 발급할 때만 사용하는 별도 설정 예시
- `secrets/service_account.json`: Google 서비스 계정 키
- `secrets/tokens.json`: BUYMA OAuth 토큰

실제 `.env`, `config.yaml`, `secrets/`는 저장소에 커밋하지 않습니다.

## 테스트

```bat
uv run pytest app/tests -q
```

테스트는 가짜 HTTP 응답과 모의 Google Sheets 객체를 사용하며 실제 BUYMA 상품 가격을 변경하지 않습니다.

## 주요 파일

```text
.
├── buyma_price_manager.py              # 메뉴형 프로그램 시작점
├── buyma_price_scheduler.py             # 상시 예약 실행 시작점
├── build_exe.bat                        # Windows EXE 빌드
├── config.example.yaml
├── .env.example
├── docs/
│   ├── USER_MANUAL.md                   # BestShip 사용자 안내
│   └── BUILD_EXE.md                     # EXE 생성/업데이트 절차
└── app/
    ├── manager.py                       # 메뉴 및 실행 제어
    ├── scheduler.py                     # 시간표에 따른 반복 실행
    ├── migration.py                     # 상품 ID 일괄 수집 도구
    ├── payload_migration.py             # BUYMA 로그인/판매자 데이터 수집
    ├── tests/
    └── src/buyma_price_competitor/
        ├── runner.py                    # 가격 비교 및 변경 처리
        ├── reporting.py                 # CSV 및 Google Sheets 보고서
        ├── buyma_api.py                 # BUYMA Product API
        ├── google_sheets.py              # Google Sheets 입출력
        ├── config.py                    # 설정 로딩
        ├── browser.py                   # Chrome/Playwright 실행
        ├── public_products.py           # 공개 상품 정보 수집
        ├── payload_mapper.py            # 판매자 데이터 변환
        ├── payload_store.py             # 수집 데이터 저장
        └── pricing.py                   # 가격 계산
```

로컬 실행 결과는 `logs/`, `reports/`, `data/`에 저장됩니다.
