@echo off
echo ========================================
echo   CTA 定时任务设置
echo ========================================
echo.

REM 删除旧任务（如果存在）
schtasks /delete /tn "CTA_Refresh_10am" /f >nul 2>&1
schtasks /delete /tn "CTA_Refresh_230pm" /f >nul 2>&1

REM 创建 10:00 任务（刷新 + 部署）
schtasks /create /tn "CTA_Refresh_10am" /tr "python E:\素材\模拟交易\cta_refresh_deploy.py" /sc daily /st 10:00 /f
echo [OK] 已创建 10:00 定时任务（刷新 + 部署）

REM 创建 14:30 任务（刷新 + 部署）
schtasks /create /tn "CTA_Refresh_230pm" /tr "python E:\素材\模拟交易\cta_refresh_deploy.py" /sc daily /st 14:30 /f
echo [OK] 已创建 14:30 定时任务（刷新 + 部署）

echo.
echo ========================================
echo   定时任务已设置完成！
echo   - 每天 10:00 自动刷新 + 部署
echo   - 每天 14:30 自动刷新 + 部署
echo   - CTA 页面: https://cta-signals.pages.dev/cta.html
echo ========================================
echo.
pause
