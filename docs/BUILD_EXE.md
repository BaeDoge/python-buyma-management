# Windows 실행 파일(EXE) 만들기

이 프로젝트는 Windows에서 빌드하는 것을 기준으로 합니다. 실행 파일은 BUYMA 상품 변경을 수행하는 프로그램과, 정해진 시간에 자동 실행하는 프로그램 두 개로 만듭니다.

## 1. 필요한 프로그램

- Windows 10 또는 11
- Python 3.11
- uv
- Google Chrome
- Git

Python과 uv가 준비되어 있지 않다면 먼저 설치하고, GitHub 저장소를 내려받습니다.

```bat
git clone https://github.com/BaeDoge/python-buyma-management.git
cd python-buyma-management
```

## 2. EXE 만들기

프로젝트 폴더에서 아래 파일을 실행합니다.

```bat
build_exe.bat
```

빌드 스크립트가 하는 일은 다음과 같습니다.

1. `uv sync`로 프로젝트 패키지를 설치합니다.
2. PyInstaller를 임시로 실행해 메뉴 프로그램을 빌드합니다.
3. 예약 실행 프로그램을 빌드합니다.
4. `dist/`에 설정 예시와 필요한 폴더를 준비합니다.

빌드가 끝나면 다음 파일이 만들어집니다.

```text
dist/
├── BUYMA-Manager.exe
├── BUYMA-Scheduler.exe
├── config.yaml
├── .env.example
├── secrets/
├── data/
├── logs/
└── reports/
```

두 실행 파일은 콘솔 프로그램입니다. 예약 실행 파일은 실행해 둔 동안 콘솔 창이 열려 있습니다.

## 3. 처음 실행할 때 설정

`dist/` 폴더에서 설정합니다.

1. `.env.example`을 복사해 `.env`로 이름을 바꿉니다.
2. `config.yaml`에 실제 Google Sheets 주소, 탭 이름과 Chrome 경로를 입력합니다.
3. `secrets/service_account.json`에 Google 서비스 계정 키를 넣습니다.
4. `secrets/tokens.json`에 BUYMA OAuth 토큰을 넣습니다.
5. Google 스프레드시트를 해당 서비스 계정 이메일에 공유합니다.

OAuth 토큰이 아직 없다면 기존 OAuth 설정 절차를 먼저 진행합니다. `app/oauth_server.py`와 `app/ngrok_tunnel.py`는 OAuth 토큰 발급에 사용하는 도구이므로 저장소에서 제거하지 않습니다.

## 4. 실행 파일을 다른 PC에 전달할 때

실행 파일만 전달하면 바로 동작하지 않습니다. 다음 항목을 함께 전달하거나 현장에서 설정해야 합니다.

- `BUYMA-Manager.exe`
- `BUYMA-Scheduler.exe`
- `config.yaml`
- `.env`
- `secrets/service_account.json`
- `secrets/tokens.json`

실제 `.env`와 `secrets/`에는 로그인 정보와 인증 토큰이 들어 있습니다. GitHub나 일반 메신저에 올리지 말고, 담당자에게 안전한 경로로 따로 전달합니다.

실행 파일은 `dist/`에서 설정 파일과 같은 폴더에 놓아야 합니다. 실행 파일의 위치를 바꾸면 그 폴더를 기준으로 `config.yaml`, `.env`, `secrets/`, `data/`, `logs/`, `reports/`를 찾습니다.

## 5. 코드가 바뀌었을 때 새 EXE 만들기

1. 최신 코드를 내려받습니다.

```bat
git pull
```

2. 의존성이 바뀌었다면 잠금 파일을 갱신하고 설치합니다.

```bat
uv lock
uv sync
```

의존성 변경이 없다면 바로 다음 단계로 넘어가도 됩니다.

3. 빌드합니다.

```bat
build_exe.bat
```

4. 새로 만들어진 `dist/BUYMA-Manager.exe`, `dist/BUYMA-Scheduler.exe`를 기존 실행 폴더에 교체합니다.

5. 기존 `config.yaml`, `.env`, `secrets/`, `data/`는 그대로 둡니다. 특히 `data/scheduler_runs.json`을 지우면 이미 완료된 예약 시간이 다시 실행될 수 있으니 유지합니다.

코드만 바뀌고 설정 항목이 그대로라면 `.env`와 `config.yaml`은 다시 만들 필요가 없습니다. 새 설정 항목이 추가된 경우에만 기존 설정 파일에 해당 항목을 반영합니다.

## 6. 예약 실행기 상시 구동

`BUYMA-Scheduler.exe`를 실행하면 시간표를 읽고 계속 대기합니다. 정해진 시각에 자동으로 가격 비교 및 변경을 시작합니다.

Windows 작업 스케줄러를 이용하면 PC 로그인 후 예약 실행기를 자동 시작하도록 등록할 수 있습니다.

- 트리거: 사용자 로그인 시
- 동작: `BUYMA-Scheduler.exe` 실행
- 중복 실행: 기존 인스턴스가 있으면 새 인스턴스는 실행되지 않음
- PC 전원/절전: 예약 시각에 PC가 켜져 있고 절전 상태가 아니어야 함

## 7. 빌드 관련 참고

- PyInstaller 빌드는 Windows에서 실행해야 Windows용 EXE가 만들어집니다.
- 빌드할 PC에 Python 3.11, uv와 프로젝트 의존성이 설치되어 있어야 합니다.
- Chrome은 실행 PC에 설치되어 있어야 합니다. 이 프로그램은 Chrome 경로를 `config.yaml`에서 읽습니다.
- EXE 빌드는 인증정보를 포함하지 않습니다.
- 백신에서 새로 빌드한 EXE를 처음 실행할 때 경고할 수 있습니다. 회사/판매자 PC의 보안 정책을 먼저 확인합니다.


## 2-1. GitHub Actions에서 EXE 받기

저장소의 **Actions → Build Windows executables** workflow를 선택해 `Run workflow`를 누르면 Windows runner에서 같은 `build_exe.bat`을 실행합니다. 빌드가 끝나면 실행 기록의 Artifacts에서 `BUYMA-Windows-Executables`를 내려받을 수 있습니다. main에 코드가 push된 경우에도 자동으로 실행됩니다. 아티팩트에는 실행 파일과 예시 설정만 들어가며 실제 `.env`와 `secrets/` 인증정보는 포함하지 않습니다. 아티팩트 보관 기간은 30일.
