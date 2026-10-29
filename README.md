# BUYMA 최저가 관리 프로그램

Windows + Python/uv 기반 개발 버전입니다. 현재는 기능 검증용이며, 고객에게 바로 배포할 수 있는 상용 패키지 상태는 아닙니다. 이 문서는 **일반 가격 비교 실행**과 **초기 연결/상품 데이터 준비**를 분리해 설명합니다.

## 일반 실행: 하나의 명령

프로젝트 루트에서 실행합니다.

```bat
uv sync
uv run refresh_prices.py --price-delta 10 --max-change 100
```

기본 동작은 DRY RUN입니다. BUYMA 가격 변경 API를 호출하지 않고, 비교 결과를 CSV로 저장하며 설정된 구글 시트 이력 탭에도 결과를 기록합니다.

- `--price-delta 10`: 다른 매장의 최저가보다 10원 낮은 가격을 계산합니다.
- `--max-change 100`: 현재 가격에서 100원을 초과해 인하해야 하는 상품은 건너뜁니다.
- 구글 시트의 현재 URL 목록을 **매 실행마다 새로 읽습니다.** URL을 추가·삭제·교체하기 위해 `setup_once.py`나 `migration.py`를 실행할 필요는 없습니다.
- 각 URL의 BUYMA 공개 페이지에서 BestShip 상품과 경쟁 상품을 읽고 가격을 비교합니다. 경쟁 가격 조회는 현재 공식 API가 아닌 공개 페이지 조회를 사용합니다.

Windows에서는 `run_recurring_dry_run.bat`을 사용할 수 있습니다.

## 초기 연결: 최초 1회 또는 재인증이 필요할 때

### 1. 설정 파일 준비

1. `config.example.yaml`을 복사해 `config.yaml`을 만듭니다.
2. Google Sheets URL, 시트명(`[2]최저가`), URL 컬럼명(`URL`), 본인 판매자 이름/ID를 확인합니다.
3. Google 서비스 계정 JSON을 `secrets/service_account.json`에 둡니다. 해당 서비스 계정에 대상 시트를 공유해야 합니다.
4. `.env.example`을 복사해 `.env`를 만들고 BUYMA OAuth 값을 설정합니다.

Google 서비스 계정 JSON과 BUYMA 비밀값은 프로그램이나 Git 저장소에 넣어 배포하면 안 됩니다.

### 2. BUYMA OAuth

OAuth는 최초 연결 때 한 번 승인하면 됩니다. 토큰이 무효화되거나 재승인이 필요한 경우에만 다시 진행합니다.

현재 OAuth 콜백 흐름은 ngrok 터널과 등록된 Redirect URL 설정을 사용합니다. `run_ngrok_tunnel.bat`과 `run_oauth.bat`을 이용해 승인하고, 성공하면 토큰이 `secrets/tokens.json`에 저장됩니다. `run_api_check.bat`은 주문 조회 GET을 이용한 읽기 권한 점검이며 상품 수정 권한을 증명하지는 않습니다.

이미 OAuth 연결을 마쳤다면 일반 가격 비교를 위해 다시 실행할 필요가 없습니다.

## 상품 ID와 API payload의 구분

### 상품 ID 수집은 일반 실행에 필요하지 않습니다

`migration.py`와 `setup_once.py` 메뉴 2는 공개 페이지에서 상품 ID를 별도 JSON에 기록하는 과거/진단용 도구입니다. 현재 `refresh_prices.py`는 URL마다 공개 페이지에서 상품 ID를 직접 확인하므로 일반 실행에 이 저장소가 필요하지 않습니다. ID가 `data/buyma_product_ids.json`에 없다는 경고도 더 이상 가격 비교 실패로 취급하지 않습니다.

### 실제 가격 변경에는 전체 상품 payload가 필요합니다

BUYMA Product API는 `POST /api/v1/products.json`으로 등록/수정 요청을 받으며, 가격만 보내는 방식이 아닙니다. 공개 API 문서의 필수 항목과 현재 검증 코드에 맞는 전체 `product` 객체가 `data/buyma_products.json`에 있어야 합니다.

- `payload_migration.py` 또는 `setup_once.py` 메뉴 3은 기존 상품의 데이터를 가져올 수 있는지 수동으로 시도하는 도구입니다. BUYMA 웹 로그인 정보가 필요할 수 있으며, 모든 상품에서 성공하지 않습니다.
- `source_product_data`는 API용 전체 payload와 다릅니다. 빠진 상품 필드를 추측해 만들어 보내지 않습니다.
- URL을 구글 시트에 새로 추가하면 가격 **비교**에는 즉시 포함됩니다. 그러나 해당 상품의 전체 payload가 저장되어 있지 않다면 실제 가격 **변경**은 건너뜁니다.
- 새 상품을 API로 등록하는 별도 기능을 나중에 만든다면, 등록 요청에 사용한 완전한 payload를 그 시점에 저장해 이후 가격 변경에서 재사용하는 구조가 바람직합니다.

공식 문서: https://specification.personal-shopper-api.buyma.com/en/api/products_json/

## 실제 가격 변경

**현재는 DRY RUN으로 결과를 검증하세요.** 실제 변경은 대상 상품의 payload를 확인하고, BUYMA API 상품 수정이 단일 상품에서 정상 반영되는지 검증한 후에만 명시적으로 실행해야 합니다.

상품 하나만 DRY RUN:

```bat
uv run refresh_prices.py --product-id 137992656 --price-delta 10 --max-change 100
```

상품 하나에 실제 변경 요청을 보내는 명령(검증 및 별도 승인 이후에만 사용):

```bat
uv run refresh_prices.py --apply --product-id 137992656 --price-delta 10 --max-change 100
```

전체 대상에 `--apply`를 지정하면 조건에 맞고 payload 검증을 통과한 상품마다 실제 API 요청을 보냅니다. API 응답의 요청 접수는 BUYMA 화면 반영 완료와 같지 않으므로 `request_uid`와 처리 결과를 따로 확인해야 합니다.

Windows 배치 파일:
- `run_recurring_dry_run.bat`: DRY RUN
- `run_recurring_apply.bat`: `APPLY`를 입력해야 실제 API 요청을 실행하도록 되어 있음

## 현재 사용하는 데이터 / 파일

- `config.yaml`: 본인 환경 설정
- `.env`: OAuth 환경 변수와 비밀값
- `secrets/tokens.json`: BUYMA OAuth 토큰
- `secrets/service_account.json`: Google 서비스 계정 키
- `data/buyma_products.json`: 상품별 API payload 또는 수집한 source data
- `data/buyma_product_ids.json`: 선택적 진단용 ID 저장소(일반 가격 비교에 불필요)
- `logs/`: 실행 로그
- `reports/`: CSV 실행 결과

`.env`, `config.yaml`, `secrets/`, 실제 계정/상품 데이터는 공개 저장소나 고객 간 공유 ZIP에 포함하지 마세요.

## 고객 판매용 패키지화 전 남은 작업

현재 코드는 개발/검증 버전입니다. PyInstaller로 EXE만 만들면 고객용 설치 프로그램이 완성되는 것은 아닙니다.

1. 고객마다 Google Sheets 인증을 안전하게 설정할 수 있는 온보딩을 만들어야 합니다. 현재의 서비스 계정 JSON 방식은 고객별 설정이 필요합니다.
2. BUYMA OAuth 앱/Client Secret/Redirect URL 운영 방식을 정리해야 합니다. Client Secret이나 사용자 토큰을 EXE에 내장하면 안 됩니다.
3. 기존 상품의 전체 수정 payload를 안정적으로 준비하고 신규 상품에도 같은 정책을 적용해야 합니다.
4. DRY RUN, 단일 상품 검증, 오류 복구, 요청 제한 및 API 웹훅/반영 확인을 테스트해야 합니다.
5. 위 사항이 안정화된 다음 Windows용 PyInstaller 패키지와 고객용 설치/설정 안내를 만듭니다.

현재 EXE 빌드 스크립트는 개발용입니다. 고객에게 배포하기 전 이 항목들을 해결해야 합니다.
