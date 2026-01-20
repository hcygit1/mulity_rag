@echo off
REM AdaptiMultiRAG 项目打包脚本 (Windows)
REM 用途：清理开发文件，生成轻量级分发包

setlocal enabledelayedexpansion

set PROJECT_NAME=AdaptiMultiRAG
set OUTPUT_DIR=dist
set ARCHIVE_NAME=%PROJECT_NAME%-%date:~0,4%%date:~5,2%%date:~8,2%.zip

echo ==========================================
echo 开始打包 %PROJECT_NAME%
echo ==========================================

REM 1. 创建临时目录
echo [1/6] 创建临时目录...
set TEMP_DIR=%TEMP%\%PROJECT_NAME%_temp
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
mkdir "%TEMP_DIR%"
xcopy /E /I /Q . "%TEMP_DIR%\%PROJECT_NAME%"
cd /d "%TEMP_DIR%\%PROJECT_NAME%"

REM 2. 清理后端文件
echo [2/6] 清理后端文件...
cd rag-backend

REM 删除虚拟环境
if exist .venv rmdir /s /q .venv

REM 删除 Python 缓存
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
del /s /q *.pyc 2>nul
del /s /q *.pyo 2>nul

REM 删除日志文件
del /q *.log 2>nul

cd ..

REM 3. 清理前端文件
echo [3/6] 清理前端文件...
cd rag-frontend

REM 删除 node_modules
if exist node_modules rmdir /s /q node_modules

REM 删除构建产物
if exist dist rmdir /s /q dist

cd ..

REM 4. 清理根目录文件
echo [4/6] 清理根目录文件...
del /s /q .DS_Store 2>nul

REM 5. 创建输出目录
echo [5/6] 创建压缩包...
cd ..
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

REM 6. 打包（需要安装 7-Zip 或使用 PowerShell）
powershell -command "Compress-Archive -Path '%PROJECT_NAME%' -DestinationPath '%OUTPUT_DIR%\%ARCHIVE_NAME%' -Force"

echo ==========================================
echo 打包完成！
echo ==========================================
echo 输出文件: %OUTPUT_DIR%\%ARCHIVE_NAME%
echo ==========================================

REM 清理临时目录
rmdir /s /q "%TEMP_DIR%"

pause
