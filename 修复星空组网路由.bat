@echo off
rem ============================================================
rem  StarVPN one-click fix: re-add 188.0/24 route
rem  Right-click this file -> Run as administrator
rem ============================================================
setlocal
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Please right-click and choose Run as administrator.
    pause
    exit /b 1
)

echo [1/3] Adding route 192.168.188.0/24 ...
netsh interface ipv4 add route 192.168.188.0/24 "StarVPN" 0.0.0.0 store=persistent >nul 2>&1
echo        Route added.

echo [2/3] Testing 192.168.188.2 ...
ping -n 3 -w 1000 192.168.188.2 | findstr /c:"TTL=" >nul 2>&1
if %errorlevel% equ 0 (
    echo        [OK] 192.168.188.2 reachable. StarVPN works.
) else (
    echo        [WARN] Not reachable. Check NAS power and StarVPN login.
)

echo [3/3] Done.
pause
endlocal
