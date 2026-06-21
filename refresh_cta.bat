@echo off
echo ========================================
echo   CTA 信号刷新 + 部署
echo ========================================
echo.

cd /d E:\素材\模拟交易

echo [1/2] 刷新数据...
python cta_refresh.py
if errorlevel 1 (
    echo [ERROR] 刷新失败
    pause
    exit /b 1
)

echo.
echo [2/2] 部署到 Cloudflare Pages...
npx wrangler pages deploy . --project-name cta-signals --branch main
if errorlevel 1 (
    echo [ERROR] 部署失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo   完成！
echo   CTA 信号页面: https://cta-signals.pages.dev/cta.html
echo ========================================
pause
