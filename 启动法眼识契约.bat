@echo off
chcp 65001 >nul
title 法眼识契约-Toobey（测试版）
echo =============================================
echo   法眼识契约-Toobey（测试版）
echo   合同风险智能把控系统
echo   关窗口即停服务，无需安装
echo =============================================
echo.
echo 启动中...
start "" /B "%~dp0法眼识契.exe"
timeout /t 4 /nobreak >nul
echo 浏览器将自动打开
echo.
echo   - 支持 Word 文档 (.docx) 上传自动解析
echo   - OCR 图片文字识别（中文简体）
echo   - 关窗口 = 停止服务
echo =============================================
pause
