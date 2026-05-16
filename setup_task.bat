@echo off
chcp 65001 >nul 2>&1

echo ============================================
echo   CUG Auto Reconnect - Setup Scheduled Task
echo ============================================
echo.

set TASK_NAME=CUG_AutoReconnect
set SCRIPT_DIR=%~dp0
set PYTHON_PATH=pythonw
set SCRIPT_PATH=%SCRIPT_DIR%Login_CUG.py

:: Delete existing task
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Create scheduled task: run every 30 minutes
schtasks /create /tn "%TASK_NAME%" /tr "\"%PYTHON_PATH%\" \"%SCRIPT_PATH%\"" /sc minute /mo 30 /rl highest /f

if %errorlevel%==0 (
    echo.
    echo Task "%TASK_NAME%" created successfully!
    echo Runs every 30 minutes to check and reconnect network.
    echo Uses pythonw for silent background execution.
    echo.
    echo Commands:
    echo   View task:    schtasks /query /tn %TASK_NAME%
    echo   Run now:      schtasks /run /tn %TASK_NAME%
    echo   Delete task:  schtasks /delete /tn %TASK_NAME% /f
) else (
    echo.
    echo Failed! Please run this script as Administrator.
)

pause
