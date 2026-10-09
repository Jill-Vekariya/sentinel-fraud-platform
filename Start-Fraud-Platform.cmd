@echo off
cd /d "%~dp0"
docker compose up -d
if errorlevel 1 (
  echo Startup failed. Check Docker Desktop is running.
  pause
  exit /b 1
)
start "" "http://localhost:8000"
echo Demo API key: local-demo-change-me
pause
