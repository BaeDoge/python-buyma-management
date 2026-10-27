# 정기 최저가 갱신

정기 실행은 `refresh_prices.py`만 사용합니다. 이 실행 경로는 `payload_migration.py`를 호출하지 않고 BUYMA 웹 로그인을 하지 않습니다.

## 개발 중: DRY RUN

```bash
uv run refresh_prices.py --price-delta 10 --max-change 100
```

Windows에서는 `run_recurring_dry_run.bat`을 실행할 수 있습니다. 기본값은 실제 가격을 변경하지 않는 DRY RUN입니다.

## 실제 적용

먼저 한 상품으로 API 반영까지 검증한 뒤에만 실행합니다.

```bash
uv run refresh_prices.py --apply --product-id <상품ID> --price-delta 10 --max-change 100
```

검증 이후 전체 대상에 적용할 때:

```bash
uv run refresh_prices.py --apply --price-delta 10 --max-change 100
```

Windows의 `run_recurring_apply.bat`은 실행 전에 `APPLY` 확인을 요구합니다.

## 로그인/API/페이지 조회 구분

| 단계 | BUYMA 웹 로그인 | 공개 페이지 조회 | 공식 API |
|---|---|---|---|
| Google Sheets 읽기 | 아니오 | 아니오 | 아니오 |
| 경쟁 가격 비교 | 아니오 | 예 | 아니오 |
| DRY RUN 계산 | 아니오 | 위 비교 단계에서만 | 아니오 |
| 실제 가격 변경 | 아니오 | 비교 단계에서 수행 | 예 |
| payload 수집 | 예, 수동 조사 시 | 로그인 후 편집 페이지 | 가격 변경 API는 호출하지 않음 |

현재 경쟁 가격 수집은 공식 API가 아니라 비로그인 공개 페이지 조회를 사용합니다. 요청 빈도는 적절히 제한하고 BUYMA 이용 조건을 준수하세요. 공식 API로 바뀐 것은 가격 변경 요청 부분입니다.

## PyInstaller (최종 기능 검증 이후에만)

지금은 패키징하지 않습니다. 최종 프로그램이 안정화된 후 Windows에서 `build_windows_exe.bat`을 실행하도록 스크립트만 준비되어 있습니다. Windows 실행 파일은 Windows에서 빌드해야 합니다. 패키징 시 진입점은 `refresh_prices.py`이며, `--onedir` 폴더에 `config.yaml`, `secrets`, `data`를 별도로 배치합니다. 토큰과 서비스 계정 파일은 exe나 공유 ZIP에 포함하지 마세요.

최종 프로그램이 안정화되기 전에는 `uv run refresh_prices.py ...`로 테스트합니다. Windows 작업 스케줄러 등록도 API 가격 변경이 실제 반영되는지 검증한 이후에 진행하세요.
