@echo off
REM ============================================================
REM AgentHub launcher / manager
REM
REM Deploy mode (this version):
REM   - Backend (postgres / redis / backend / celery_worker) runs in Docker
REM   - Frontend (vite dev) runs on the HOST (not in Docker) so the browser
REM     hits localhost:5173 and the vite proxy can reach backend at
REM     localhost:18000 directly, no docker-internal DNS in the loop.
REM
REM Usage:
REM   agenthub.bat              default = start everything, wait ready, open browser
REM   agenthub.bat start        start everything (no browser)
REM   agenthub.bat stop         stop backend containers + host vite
REM   agenthub.bat restart      stop + start
REM   agenthub.bat status       show container + endpoint health
REM   agenthub.bat logs [svc]   follow docker logs; svc = backend, frontend, ...
REM   agenthub.bat build        rebuild docker images
REM   agenthub.bat down [-v]    stop + remove containers; -v wipes volumes
REM   agenthub.bat open         open frontend in default browser
REM   agenthub.bat frontend     start host vite only (backend assumed running)
REM   agenthub.bat help         show this help
REM ============================================================

chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "COMPOSE_FILE=src\docker\docker-compose.yml"
set "PROJECT=agenthub"
set "FRONTEND_URL=http://localhost:5173"
set "BACKEND_URL=http://localhost:18000"
set "VITE_PID_FILE=%TEMP%\agenthub-vite.pid"
set "VITE_WINDOW_TITLE=AgentHub Vite"

REM ---- default action: start all, wait ready, open browser ----
if "%~1"=="" (
    call :do_start
    call :do_wait_ready
    call :do_open
    echo.
    call :do_status
    echo.
    echo Tip: "agenthub.bat logs backend" to follow backend logs.
    echo      "agenthub.bat stop" to stop everything.
    echo      Closing this window does NOT stop the services.
    goto :cleanup_end
)

if /I "%~1"=="help"     goto :show_help
if /I "%~1"=="--help"   goto :show_help
if /I "%~1"=="-h"       goto :show_help

if /I "%~1"=="start"      call :do_start    & goto :cleanup_end
if /I "%~1"=="stop"       call :do_stop     & goto :cleanup_end
if /I "%~1"=="restart"    call :do_restart  & goto :cleanup_end
if /I "%~1"=="status"     call :do_status   & goto :cleanup_end
if /I "%~1"=="ps"         call :do_status   & goto :cleanup_end
if /I "%~1"=="logs"       call :do_logs     & goto :cleanup_end
if /I "%~1"=="build"      call :do_build    & goto :cleanup_end
if /I "%~1"=="down"       call :do_down     & goto :cleanup_end
if /I "%~1"=="open"       call :do_open     & goto :cleanup_end
if /I "%~1"=="browser"    call :do_open     & goto :cleanup_end
if /I "%~1"=="frontend"   call :do_frontend & goto :cleanup_end
if /I "%~1"=="vite"       call :do_frontend & goto :cleanup_end

echo Unknown command: %~1
echo Run "agenthub.bat help" for usage.
exit /b 1

:do_start
echo [start] bringing up backend containers ...
docker compose -f "%COMPOSE_FILE%" -p %PROJECT% up -d postgres redis backend celery_worker
if errorlevel 1 (
    echo [start] FAILED - see docker output above
    exit /b 1
)
echo.
call :do_frontend
echo.
echo [start] all services up.
echo   frontend: %FRONTEND_URL%
echo   backend : %BACKEND_URL%/docs
echo.
goto :eof

:do_frontend
echo [vite] starting on host at port 5173 ...
if not exist "src\frontend\node_modules" (
    echo [vite] node_modules missing - run "npm install" in src\frontend first
    exit /b 1
)
start "%VITE_WINDOW_TITLE%" /min cmd /c "cd /d "%~dp0src\frontend" && npm run dev"
timeout /t 4 /nobreak >nul
goto :eof

:do_stop
echo [stop] stopping backend containers ...
docker compose -f "%COMPOSE_FILE%" -p %PROJECT% stop postgres redis backend celery_worker
if errorlevel 1 (
    echo [stop] docker stop FAILED
)
call :do_stop_vite
echo [stop] done. Restart with: agenthub.bat start
goto :eof

:do_stop_vite
echo [vite] stopping host vite process ...
taskkill /F /T /FI "WINDOWTITLE eq %VITE_WINDOW_TITLE%*" 2>nul
if exist "%VITE_PID_FILE%" del "%VITE_PID_FILE%" 2>nul
goto :eof

:do_restart
call :do_stop
echo.
call :do_start
goto :eof

:do_status
echo [status] AgentHub containers:
echo.
docker compose -f "%COMPOSE_FILE%" -p %PROJECT% ps
echo.
echo Endpoint probes:
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; try { $r=Invoke-WebRequest -Uri 'http://localhost:18000/health' -UseBasicParsing -TimeoutSec 3; '  backend  /health -> HTTP '+$r.StatusCode+' (healthy)' } catch { '  backend  /health -> UNREACHABLE' }"
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; try { $r=Invoke-WebRequest -Uri 'http://localhost:5173/' -UseBasicParsing -TimeoutSec 3; '  frontend /        -> HTTP '+$r.StatusCode+' (serving)' } catch { '  frontend /        -> UNREACHABLE' }"
goto :eof

:do_wait_ready
echo [wait] probing backend /health (max 30s) ...
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; $deadline=(Get-Date).AddSeconds(30); $ok=$false; $attempt=0; while ((Get-Date) -lt $deadline) { $attempt++; try { $r=Invoke-WebRequest -Uri 'http://localhost:18000/health' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { $ok=$true; break } } catch {}; Start-Sleep -Seconds 1 }; if ($ok) { Write-Host ('  backend ready after ' + $attempt + 's') } else { Write-Host '  backend NOT ready after 30s - opening browser anyway' }"
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; $deadline=(Get-Date).AddSeconds(15); $ok=$false; $attempt=0; while ((Get-Date) -lt $deadline) { $attempt++; try { $r=Invoke-WebRequest -Uri 'http://localhost:5173/' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { $ok=$true; break } } catch {}; Start-Sleep -Seconds 1 }; if ($ok) { Write-Host ('  frontend ready after ' + $attempt + 's') } else { Write-Host '  frontend NOT ready after 15s' }"
goto :eof

:do_logs
if "%~2"=="" (
    docker compose -f "%COMPOSE_FILE%" -p %PROJECT% logs -f
) else (
    docker compose -f "%COMPOSE_FILE%" -p %PROJECT% logs -f %~2
)
goto :eof

:do_build
echo [build] rebuilding docker images ...
docker compose -f "%COMPOSE_FILE%" -p %PROJECT% build
if errorlevel 1 (
    echo [build] FAILED
    exit /b 1
)
echo [build] done. Apply with: agenthub.bat restart
goto :eof

:do_down
set "VOLS="
if /I "%~2"=="-v" set "VOLS=-v"
if /I "%~2"=="--volumes" set "VOLS=-v"
if "%VOLS%"=="-v" goto :confirm_volumes
echo [down] stopping and removing containers (volumes preserved) ...
docker compose -f "%COMPOSE_FILE%" -p %PROJECT% down
call :do_stop_vite
goto :eof

:confirm_volumes
echo !!
echo !! WARNING: -v will DELETE postgres + redis data volumes.
echo !! All conversation history, memory store, vector indexes will be lost.
echo !!
set /p "CONFIRM=Type YES to confirm: "
if /I not "%CONFIRM%"=="YES" (
    echo Cancelled.
    goto :eof
)
echo [down] removing containers + volumes ...
docker compose -f "%COMPOSE_FILE%" -p %PROJECT% down -v
call :do_stop_vite
echo [down] done. Start fresh with: agenthub.bat start
goto :eof

:do_open
echo [open] launching default browser at %FRONTEND_URL% ...
start "" "%FRONTEND_URL%"
goto :eof

:show_help
echo.
echo AgentHub launcher / manager
echo.
echo Usage: agenthub.bat ^<command^> [args]
echo.
echo Commands:
echo   start              start backend containers + host vite
echo   stop               stop backend containers + host vite
echo   restart            stop + start
echo   status             show containers + endpoint health
echo   logs [service]     follow docker logs; no service = all
echo   build              rebuild docker images
echo   down [-v]          stop + remove containers; -v wipes volumes
echo   open               open frontend in default browser
echo   frontend           start host vite only - backend assumed running
echo   help               show this help
echo.
echo No argument = start, wait for ready, open browser, show status.
echo.
echo Common service names:
echo   postgres  redis  backend  celery_worker
echo.
echo Ports:
echo   frontend 5173   backend 18000   postgres 5432   redis 6379
echo.
echo Deploy mode: backend in Docker, frontend (vite) on host.
echo.
goto :eof

:cleanup_end
endlocal
