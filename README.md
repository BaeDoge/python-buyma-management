# BESTSHIP 최저가 관리 프로그램

이 프로젝트는 **BESTSHIP 한 곳만을 위한 Windows 프로그램**입니다.

- BUYMA 판매자 ID: `12217668` (코드에서 고정)
- 일반 실행 파일: `run_bestship_price_manager.bat`
- Python 진입점: `buyma_price_manager.py`
- Windows EXE 빌드: `build_windows_exe.bat`

일반 사용자는 마이그레이션 스크립트, 상품 ID 저장소, OAuth 서버를 실행할 필요가 없습니다. OAuth가 이미 연결돼 있고 `secrets/tokens.json`이 남아 있다면 일반 실행에서 인증을 다시 하지 않습니다.

## 1. 처음 한 번만 준비

### 설정 파일

1. `config.example.yaml`을 `config.yaml`로 복사합니다.
2. `config.yaml`의 `google.sheet_url`을 BESTSHIP이 사용하는 스프레드시트 URL로 설정합니다.
3. `google.price_sheet`은 상품 URL이 있는 시트(기본 `[2]최저가`), `google.url_column`은 URL 컬럼명(기본 `URL`)과 일치시킵니다.
4. Google 서비스 계정 JSON을 `secrets/service_account.json`에 둡니다. 해당 계정이 대상 Google Sheet에 접근할 수 있어야 합니다.
5. 이미 승인된 BESTSHIP의 BUYMA OAuth 토큰을 `secrets/tokens.json`에 둡니다.

로컬 개발 실행에 필요한 패키지 설치:

```powershell
uv sync
```

이미 OAuth가 연결된 경우, 매번 OAuth나 ngrok을 실행하지 않습니다. 토큰을 찾을 수 없거나 인증이 거부된 경우에만 아래의 OAuth 복구 도구를 사용합니다.

## 2. 평소 실행

Windows에서는 `run_bestship_price_manager.bat`을 더블클릭합니다. 또는 프로젝트 폴더에서 다음 명령을 실행합니다.

```powershell
uv run buyma_price_manager.py
```

메뉴에서 다음 중 하나를 선택합니다.

- **1. 가격 비교 결과 확인 (DRY RUN)**: Google Sheet의 URL 목록을 매번 새로 읽고, BUYMA 공개 페이지에서 BESTSHIP 상품 가격과 다른 매장의 최저가를 비교합니다. 신규 가격을 계산하지만 BUYMA 가격 변경 API는 호출하지 않습니다.
- **2. 실제 가격 변경**: 전체 비교를 수행한 다음, 확인 문구를 입력한 경우에만 검증 가능한 상품에 대해 BUYMA Product API를 호출합니다.
- **0. 종료**: 프로그램을 종료합니다.

경쟁 최저가보다 낮출 금액은 기본 10원, 허용할 최대 인하 폭은 기본 100원입니다. 실행할 때 직접 바꿀 수도 있습니다.

## 3. 상품 URL 변경

Google Sheet의 URL 열을 일반 실행 때마다 다시 읽습니다. 따라서 URL을 추가, 삭제, 교체해도 `setup_once.py` 또는 `migration.py`를 매번 실행할 필요가 없습니다. 빈 셀과 중복 URL은 건너뛰며, 여러 URL에서 같은 BESTSHIP 상품 ID가 발견되면 상품별로 한 번만 판단합니다.

실행 결과는 `reports/`에 CSV로 저장하고, Google Sheet의 이력 탭(기본 `[5] 최저가 적용이력`)에 이전 이력을 지우지 않고 추가합니다.

## 4. BUYMA API와 상품 데이터 제한

### 가격 조회와 가격 변경은 다릅니다

- **경쟁 매장 가격 비교**: 현재 공개된 Personal Shopper API 문서에 경쟁 매장 최저가 검색 endpoint가 확인되지 않아 BUYMA 공개 상품 페이지를 조회합니다.
- **실제 가격 변경**: BUYMA 공식 Product API의 `POST /api/v1/products.json`을 사용합니다.

BUYMA Product API는 가격만 보내는 단순 수정 요청이 아닙니다. `control`, `name`, `comments`, `brand_id`, `category_id`, `price`, `available_until`, 구매/배송 지역, 이미지, 배송 방법, 옵션, variants 등 필수 필드를 포함하는 상품 payload가 필요합니다. 상세 규격은 [공식 Product API 문서](https://specification.personal-shopper-api.buyma.com/en/api/products_json/)를 참고하세요.

### 실제 변경에 필요한 payload

`data/buyma_products.json`에 각 상품별로 `product` 객체가 저장돼 있어야 하며, API 필수 필드와 현재 BESTSHIP 상품 ID가 일치해야 합니다. `source_product_data`만 저장돼 있거나 필수 정보가 빠져 있는 상품은 API 수정 대상이 아닙니다. 프로그램은 그 정보를 추측해서 만들거나 보내지 않습니다.

이 점은 중요합니다. **가격 비교가 성공해도 모든 상품에 대해 가격 변경이 가능하다는 뜻은 아닙니다.** 실행 메뉴에서 유효한 상품 payload가 하나도 없으면 실제 적용 단계는 시작하지 않습니다. payload가 일부만 준비돼 있다면 유효한 상품만 처리하고, 나머지는 결과에 사유를 남깁니다.

BUYMA 공식 API는 업데이트 요청을 비동기로 처리합니다. HTTP 201 및 `request_uid`는 요청 접수를 뜻하며, 가격 반영 완료와 같지 않습니다. BUYMA에서 제공하는 webhook 또는 상품 화면에서 최종 결과를 확인해야 합니다. 자세한 내용은 [공식 REST API 문서](https://specification.personal-shopper-api.buyma.com/en/api/)에 있습니다.

## 5. EXE 빌드

Windows 환경에서 프로젝트 루트의 `build_windows_exe.bat`을 실행합니다. 산출물은 `dist/BestShipPriceManager/`에 생성됩니다.

EXE에는 토큰이나 Google 서비스 계정 키를 내장하지 않습니다. 필요한 파일은 실행 파일 바깥의 `secrets/`, `data/`, `config.yaml`로 관리합니다. 이 패키지는 BESTSHIP 한 곳에 제공하는 용도이므로, 고객별 인증 파일은 별도 보안 경로로 전달하고 GitHub에 올리지 않습니다.

## 6. OAuth 복구 도구

`run_ngrok_tunnel.bat`, `run_oauth.bat`, `oauth_server.py`는 일반 가격 관리에 사용하지 않습니다. 기존 토큰이 없어졌거나 BUYMA가 재인증을 요구할 때만 사용합니다.

## 디렉터리 정리

- `buyma_price_manager.py`: 유일한 일반 실행 진입점
- `run_bestship_price_manager.bat`: Windows 실행 바로가기
- `app/src/buyma_price_competitor/`: 가격 비교, API, Google Sheet 처리 로직
- `config.yaml`: BESTSHIP 환경 설정(로컬 전용)
- `secrets/`: 기존 BUYMA OAuth 토큰 및 Google 서비스 계정 키(로컬 전용)
- `data/buyma_products.json`: 상품별 API payload(로컬 전용)
- `logs/`, `reports/`: 실행 로그와 CSV 보고서

`.env`, `config.yaml`, `secrets/`, `data/`, `dist/`에는 비밀정보나 고객 데이터가 있을 수 있습니다. 이 파일을 공개 저장소에 커밋하지 마세요.
