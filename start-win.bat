@echo off
REM =============================================================================
REM GeoRAG 一键启动脚本 (Windows) — start-win.bat
REM =============================================================================
REM 功能:
REM   1. 读取 conda 环境名称: 优先级为 命令行参数 > 系统环境变量 GEORAG_CONDA_ENV
REM      > 项目根目录 .env 文件 (被 git 忽略) > 默认值 (默认 langchain_v03)
REM   2. 自动定位 conda 并激活该环境
REM   3. (可选) 自动启动 pgvector 数据库容器
REM   4. 启动 GeoRAG 服务并打开浏览器
REM
REM 使用方法:
REM   start-win.bat                 REM 按上述优先级读取环境后启动
REM   start-win.bat ^<env^>         REM 临时指定其他 conda 环境
REM   start-win.bat --skip-db       REM 跳过数据库检查/启动
REM
REM 配置 conda 环境(任选其一):
REM   a) 写入项目根目录 .env  (推荐, 被 git 忽略, 不会入库)
REM        GEORAG_CONDA_ENV=langchain_v03
REM   b) 系统环境变量(持久生效, 执行一次):
REM        setx GEORAG_CONDA_ENV langchain_v03
REM
REM macOS/Linux 用户请使用同目录下的 start-mac.sh
REM =============================================================================

setlocal enabledelayedexpansion
chcp 65001 >nul

REM ---------------- 可配置项 ----------------
set "DEFAULT_CONDA_ENV=langchain_v03"
set "APP_PORT=7512"
set "APP_BASE_URL=http://localhost:%APP_PORT%"
set "API_DOCS_URL=%APP_BASE_URL%/docs"

cd /d "%~dp0"

echo.
echo   ======================================
echo    GeoRAG one-click launcher (Windows)
echo   ======================================
echo.

REM ---------------- 1. 读取 conda 环境名称 ----------------
set "CONDA_ENV=%GEORAG_CONDA_ENV%"

REM 从项目根目录 .env 读取 (格式: GEORAG_CONDA_ENV=xxx, 被 git 忽略)
if not defined CONDA_ENV if exist "%~dp0.env" (
    for /f "usebackq tokens=1,* delims==" %%a in ('findstr /b /i "GEORAG_CONDA_ENV" "%~dp0.env"') do (
        set "CONDA_ENV=%%b"
        if defined CONDA_ENV set "CONDA_ENV=!CONDA_ENV:"=!"
    )
)

REM 命令行参数优先级最高
if not "%~1"=="" if not "%~1"=="--skip-db" set "CONDA_ENV=%~1"

if not defined CONDA_ENV set "CONDA_ENV=%DEFAULT_CONDA_ENV%"

echo   [OK] 项目目录: %~dp0
echo   [OK] Conda 环境: %CONDA_ENV%
echo.

REM ---------------- 2. 定位 conda (优先取完整路径) ----------------
set "CONDA_BAT="
for /f "delims=" %%i in ('where conda.bat 2^>nul') do if not defined CONDA_BAT set "CONDA_BAT=%%i"
if not defined CONDA_BAT for /f "delims=" %%i in ('where conda 2^>nul') do if not defined CONDA_BAT set "CONDA_BAT=%%i"

REM 常见安装路径兜底
if not defined CONDA_BAT if exist "%USERPROFILE%\miniconda3\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\miniconda3\condabin\conda.bat"
if not defined CONDA_BAT if exist "%USERPROFILE%\anaconda3\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\anaconda3\condabin\conda.bat"
if not defined CONDA_BAT if exist "%USERPROFILE%\miniforge3\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\miniforge3\condabin\conda.bat"
if not defined CONDA_BAT if exist "%LOCALAPPDATA%\miniconda3\condabin\conda.bat" set "CONDA_BAT=%LOCALAPPDATA%\miniconda3\condabin\conda.bat"
if not defined CONDA_BAT if exist "%LOCALAPPDATA%\Continuum\anaconda3\Scripts\conda.bat" set "CONDA_BAT=%LOCALAPPDATA%\Continuum\anaconda3\Scripts\conda.bat"
if not defined CONDA_BAT if exist "C:\ProgramData\miniconda3\condabin\conda.bat" set "CONDA_BAT=C:\ProgramData\miniconda3\condabin\conda.bat"
if not defined CONDA_BAT if exist "C:\ProgramData\anaconda3\condabin\conda.bat" set "CONDA_BAT=C:\ProgramData\anaconda3\condabin\conda.bat"

if not defined CONDA_BAT (
    echo   [ERR] 未找到 conda，请先安装 Miniconda/Anaconda 或将其加入 PATH。
    goto :error_exit
)
echo   [OK] conda 路径: !CONDA_BAT!

REM ---------------- 3. 校验环境是否存在 ----------------
set "ENV_EXISTS="
for /f "tokens=1 delims= " %%a in ('call "!CONDA_BAT!" env list 2^>nul ^| findstr /v "^#"') do (
    if /i "%%a"=="%CONDA_ENV%" set "ENV_EXISTS=1"
)

if not defined ENV_EXISTS (
    echo   [ERR] Conda 环境 '%CONDA_ENV%' 不存在！可用环境:
    echo.
    call "!CONDA_BAT!" env list 2>nul | findstr /v "^#"
    echo.
    echo   [ERR] 请通过环境变量指定正确的环境:  setx GEORAG_CONDA_ENV ^<环境名^>
    goto :error_exit
)

REM ---------------- 4. 激活环境 ----------------
call "!CONDA_BAT!" activate "%CONDA_ENV%" || goto :activate_fail
echo   [OK] Python 版本:
python --version
echo.

REM ---------------- 5. 依赖完整性检查 ----------------
python -c "import fastapi, uvicorn, dotenv, langchain" >nul 2>nul
if errorlevel 1 (
    echo   [!!] 当前环境缺少项目依赖，正在尝试安装...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo   [ERR] 依赖安装失败，请手动执行: pip install -r requirements.txt
        goto :error_exit
    )
)

REM ---------------- 6. (可选) pgvector 数据库检查 ----------------
if /i not "%~1"=="--skip-db" if /i not "%~2"=="--skip-db" (
    if exist "%~dp0.env" (
        findstr /i /c:"USE_PGVECTOR=true" "%~dp0.env" >nul 2>nul
        if not errorlevel 1 (
            netstat -ano | findstr ":5434" | findstr "LISTENING" >nul 2>nul
            if errorlevel 1 (
                echo   [!!] USE_PGVECTOR=true 但数据库 (localhost:5434) 未就绪。
                where docker >nul 2>nul
                if not errorlevel 1 (
                    echo   [!!] 尝试通过 docker compose 启动 pgvector 容器...
                    docker compose up -d postgres >nul 2>nul || docker-compose up -d postgres >nul 2>nul || (
                        echo   [!!] docker 启动失败，请手动执行: docker compose up -d postgres
                    )
                ) else (
                    echo   [!!] 未安装 docker，请手动启动 PostgreSQL (见 docker-compose.yml)。
                )
            ) else (
                echo   [OK] pgvector 数据库已就绪 (localhost:5434)
            )
        )
    )
)

REM ---------------- 7. 启动服务并打开浏览器 ----------------
echo   [OK] 正在启动 GeoRAG 服务...
echo.
echo     URL:       %APP_BASE_URL%
echo     API Docs:  %API_DOCS_URL%
echo     Health:    %APP_BASE_URL%/llm/v1/health
echo     (按 Ctrl+C 停止服务)
echo.

REM 延迟约 4 秒打开浏览器 (等服务起来; ping 用于延迟,避免 timeout 输入重定向问题)
start "" /b cmd /c "ping -n 5 127.0.0.1 >nul & start http://localhost:%APP_PORT%/docs"

REM 前台运行, Ctrl+C 可直接停止
python main.py
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo   [ERR] 服务异常退出 (exit=%EXIT_CODE%)，请查看上方日志。
)
exit /b %EXIT_CODE%

:activate_fail
echo   [ERR] 激活环境失败: %CONDA_ENV%
goto :error_exit

:error_exit
echo.
echo   ======================================
echo    启动失败，按任意键退出
echo   ======================================
pause >nul
exit /b 1
