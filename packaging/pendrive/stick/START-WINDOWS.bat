@echo off
REM START-WINDOWS.bat - plug-and-play SIF-precursor demo (OIL India, SIH 2026 PS 26165)
REM Double-click this file. First run unpacks to %%LOCALAPPDATA%%\sif-demo (~1 min),
REM nothing needs to be installed, no network needed. Windows 10/11 (tar.exe + curl.exe
REM ship with Windows).
setlocal EnableDelayedExpansion
set "STICK=%~dp0"
set "DEST=%LOCALAPPDATA%\sif-demo"
set "BASE=http://127.0.0.1:8177"

curl -sf --max-time 2 %BASE%/api/health >nul 2>&1
if not errorlevel 1 (
    echo [sif-demo] already running - opening %BASE%/
    start "" %BASE%/
    exit /b 0
)

if not exist "%DEST%\VERSION" goto :extract
fc /b "%STICK%VERSION" "%DEST%\VERSION" >nul 2>&1
if errorlevel 1 goto :extract
goto :seed

:extract
echo [sif-demo] first run on this machine - unpacking to %DEST% (one time)...
mkdir "%DEST%" 2>nul
tar -xf "%STICK%payload.tar.gz" -C "%DEST%"
if errorlevel 1 goto :fail
tar -xf "%STICK%runtimes\win-py314.zip" -C "%DEST%"
if errorlevel 1 goto :fail
copy /y "%STICK%VERSION" "%DEST%\VERSION" >nul

:seed
if not exist "%DEST%\runtime.db" (
    copy /y "%DEST%\payload\seed\demo_pre.db" "%DEST%\runtime.db" >nul
    echo [sif-demo] demo database seeded (4,548 reports)
)

cd /d "%DEST%\payload"
set "SIF_MODEL_PATH=%DEST%\payload\artifacts\models\masked-v2\sif_multitask_int8.onnx"
set "SIF_DB_PATH=%DEST%\runtime.db"
set "SIF_PORT=8177"
REM LLM rewording is optional; built-in explanation templates carry the demo.

start "sif-demo-server" /min "%DEST%\python\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8177 --workers 1

set /a tries=0
:waitloop
curl -sf --max-time 2 %BASE%/api/health >nul 2>&1
if not errorlevel 1 goto :ready
set /a tries+=1
if %tries% geq 120 goto :fail
timeout /t 1 /nobreak >nul
goto :waitloop

:ready
echo [sif-demo] DEMO READY: %BASE%/
start "" %BASE%/
echo [sif-demo] the server runs in the minimized "sif-demo-server" window - close it to stop
exit /b 0

:fail
echo [sif-demo] ERROR: startup failed. See %DEST%\ for state; delete that folder and retry.
exit /b 1
