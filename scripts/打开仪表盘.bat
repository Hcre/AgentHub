@echo off
chcp 65001 >nul
title 开发规范 - 项目仪表盘
cd /d "%~dp0"

echo ================================================
echo   开发规范 - 项目仪表盘
echo ================================================
echo   正在启动本地服务并打开浏览器...
echo   关闭此窗口即停止服务。
echo.

rem 优先用 py 启动器，回退到 python
where py >nul 2>nul && (
  py start_server.py %*
  goto :end
)
where python >nul 2>nul && (
  python start_server.py %*
  goto :end
)

echo [错误] 未检测到 Python。请先安装 Python 3 并勾选 "Add to PATH"。
echo        下载地址: https://www.python.org/downloads/

:end
echo.
pause
