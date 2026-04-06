@echo off
setlocal EnableDelayedExpansion

set "ROOT_DIR=%~dp0"
set "API_DIR=%ROOT_DIR%api-service"
set "WEB_DIR=%ROOT_DIR%web-app"
set "ENV_FILE=%ROOT_DIR%.env"

set "API_PORT=8000"
set "WEB_PORT=3000"

if exist "%ENV_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%A in (`findstr /R /C:"^[A-Z_][A-Z0-9_]*=" "%ENV_FILE%"`) do (
        if /I "%%A"=="API_PORT" set "API_PORT=%%B"
        if /I "%%A"=="WEB_PORT" set "WEB_PORT=%%B"
    )
)

set "API_PYTHON=python"
if exist "%ROOT_DIR%.venv\Scripts\python.exe" set "API_PYTHON=%ROOT_DIR%.venv\Scripts\python.exe"
if exist "%API_DIR%\venv\Scripts\python.exe" set "API_PYTHON=%API_DIR%\venv\Scripts\python.exe"

call :find_free_port %API_PORT% FREE_API_PORT
call :find_free_port %WEB_PORT% FREE_WEB_PORT

echo [1/5] Project root: %ROOT_DIR%
echo [2/5] API port requested: %API_PORT%
echo [3/5] API port using: !FREE_API_PORT!
echo [4/5] Web port requested: %WEB_PORT%
echo [5/5] Web port using: !FREE_WEB_PORT!

where docker >nul 2>nul
if %errorlevel%==0 (
    echo Trying to start PostgreSQL via docker compose...
    docker compose up -d postgres >nul 2>nul
) else (
    echo Docker not found. Skipping PostgreSQL auto-start.
    echo       Please make sure your local PostgreSQL is already running on port 5432.
)

if not "%API_PORT%"=="!FREE_API_PORT!" (
    echo API port %API_PORT% is occupied. Switched to !FREE_API_PORT!.
)

if not "%WEB_PORT%"=="!FREE_WEB_PORT!" (
    echo Web port %WEB_PORT% is occupied. Switched to !FREE_WEB_PORT!.
)

echo Launching API...
set "PORT=!FREE_API_PORT!"
set "API_BASE_URL=http://127.0.0.1:!FREE_API_PORT!"
start "GlobalReporter API" /D "%API_DIR%" "%API_PYTHON%" -m uvicorn app.main:app --host 0.0.0.0 --port !FREE_API_PORT!

echo Launching Web...
start "GlobalReporter Web" /D "%WEB_DIR%" cmd /k "set VITE_API_PROXY_TARGET=http://localhost:!FREE_API_PORT!&& call npm run dev -- --port !FREE_WEB_PORT! --strictPort"

echo Waiting for services to start...
timeout /t 6 /nobreak >nul

echo Opening browser...
start "" "http://localhost:!FREE_WEB_PORT!"

echo Done.
endlocal
goto :eof

:find_free_port
setlocal EnableDelayedExpansion
set "PORT=%~1"

:check_loop
set "FOUND="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":!PORT! .*LISTENING"') do (
    set "FOUND=%%P"
)

if defined FOUND (
    set /a PORT+=1
    goto check_loop
)

endlocal & set "%~2=%PORT%"
goto :eof
