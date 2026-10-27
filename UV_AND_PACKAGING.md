# uv / 폴더 구조

- 프로젝트 루트: `pyproject.toml`, `.env`, `config.yaml`, `secrets/`, `data/`, `.venv/`
- 소스 코드: `app/`
- 패키지 소스: `app/src/buyma_price_competitor/`

최초 설치:

```bat
uv sync
````

`uv.lock`은 새 환경에서 `uv sync`를 실행하면 생성됩니다.

모든 명령은 프로젝트 루트에서 실행합니다.
