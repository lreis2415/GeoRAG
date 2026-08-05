#!/usr/bin/env bash
# =============================================================================
# GeoRAG 一键启动脚本 (macOS / Linux) — start-mac.sh
# =============================================================================
# 功能:
#   1. 读取 conda 环境名称: 优先级为 命令行参数 > 系统环境变量 GEORAG_CONDA_ENV
#      > 项目根目录 .env 文件 (被 git 忽略) > 默认值 (默认 langchain_v03)
#   2. 自动定位 conda 并激活该环境
#   3. (可选) 自动启动 pgvector 数据库容器
#   4. 启动 GeoRAG 服务并打开浏览器
#
# 使用方法:
#   ./start-mac.sh                # 按上述优先级读取环境后启动
#   ./start-mac.sh <env>          # 临时指定其他 conda 环境
#   ./start-mac.sh --skip-db      # 跳过数据库检查/启动
#
# 配置 conda 环境(任选其一):
#   a) 写入项目根目录 .env  (推荐, 被 git 忽略, 不会入库)
#        GEORAG_CONDA_ENV=langchain_v03
#   b) 系统环境变量(持久生效):
#        echo 'export GEORAG_CONDA_ENV=langchain_v03' >> ~/.zshrc && source ~/.zshrc
#
# Windows 用户请使用同目录下的 start-win.bat
# =============================================================================

set -euo pipefail

# ---------------- 可配置项 ----------------
DEFAULT_CONDA_ENV="langchain_v03"   # 未配置环境变量时的默认环境
APP_PORT=7512
APP_BASE_URL="http://localhost:${APP_PORT}"
API_DOCS_URL="${APP_BASE_URL}/docs"
HEALTH_URL="${APP_BASE_URL}/llm/v1/health"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${PROJECT_ROOT}"

# ---------------- 工具函数 ----------------
print_banner() {
    echo ""
    echo "  ╔═══════════════════════════════════════════╗"
    echo "  ║       GeoRAG 一键启动脚本                 ║"
    echo "  ╚═══════════════════════════════════════════╝"
    echo ""
}

log()  { echo -e "\033[32m[✔]\033[0m $*"; }
warn() { echo -e "\033[33m[!]\033[0m $*"; }
err()  { echo -e "\033[31m[✘]\033[0m $*"; }

# ---------------- 解析命令行参数 ----------------
SKIP_DB=false
ENV_OVERRIDE=""
for arg in "$@"; do
    case "${arg}" in
        --skip-db) SKIP_DB=true ;;
        --help|-h)
            sed -n '2,20p' "$0"
            exit 0
            ;;
        *) ENV_OVERRIDE="${arg}" ;;
    esac
done

print_banner

# ---------------- 1. 读取 conda 环境名称 ----------------
# 优先级: 命令行参数 > 系统环境变量 > 项目 .env 文件 > 默认值
CONDA_ENV=""
ENV_SRC=""
if [[ -n "${GEORAG_CONDA_ENV:-}" ]]; then
    CONDA_ENV="${GEORAG_CONDA_ENV}"
    ENV_SRC="系统环境变量"
elif [[ -f "${PROJECT_ROOT}/.env" ]]; then
    # 从项目根目录 .env 读取 (格式: GEORAG_CONDA_ENV=xxx)
    CONDA_ENV="$(grep -E '^\s*GEORAG_CONDA_ENV\s*=' "${PROJECT_ROOT}/.env" | tail -1 | sed -E 's/^[^=]*=\s*"?([^"]*)"?\s*$/\1/' || true)"
    [[ -n "${CONDA_ENV}" ]] && ENV_SRC="项目 .env 文件"
fi
# 命令行参数优先级最高
if [[ -n "${ENV_OVERRIDE}" ]]; then
    CONDA_ENV="${ENV_OVERRIDE}"
    ENV_SRC="命令行参数"
fi
CONDA_ENV="${CONDA_ENV:-${DEFAULT_CONDA_ENV}}"
[[ -z "${ENV_SRC}" ]] && ENV_SRC="默认值"

log "项目目录: ${PROJECT_ROOT}"
log "Conda 环境: ${CONDA_ENV} (来源: ${ENV_SRC})"
echo ""

# ---------------- 2. 定位 conda ----------------
CONDA_BIN="$(command -v conda || true)"
if [[ -z "${CONDA_BIN}" ]]; then
    # 常见安装路径兜底
    for candidate in \
        "${HOME}/miniconda3/bin/conda" \
        "${HOME}/anaconda3/bin/conda" \
        "${HOME}/miniforge3/bin/conda" \
        "${HOME}/mambaforge/bin/conda" \
        "/opt/homebrew/Caskroom/miniconda/base/bin/conda" \
        "/opt/miniconda3/bin/conda" \
        "/opt/anaconda3/bin/conda" \
        "/usr/local/miniconda3/bin/conda" \
        "/usr/local/anaconda3/bin/conda"; do
        if [[ -x "${candidate}" ]]; then
            CONDA_BIN="${candidate}"
            break
        fi
    done
fi
if [[ -z "${CONDA_BIN}" ]]; then
    err "未找到 conda，请先安装 Miniconda/Anaconda 或将其加入 PATH。"
    exit 1
fi

# 通过 conda info --base 获取真实 base 路径 (兼容 homebrew 软链接等场景)
CONDA_BASE="$("${CONDA_BIN}" info --base 2>/dev/null || true)"
if [[ -z "${CONDA_BASE}" ]]; then
    CONDA_BASE="$(dirname "$(dirname "${CONDA_BIN}")")"
fi
CONDA_SH="${CONDA_BASE}/etc/profile.d/conda.sh"
log "conda 路径: ${CONDA_BIN}"

# ---------------- 3. 校验环境是否存在 ----------------
ENV_EXISTS=false
if [[ -f "${CONDA_SH}" ]]; then
    # shellcheck disable=SC1090
    source "${CONDA_SH}"
    conda env list | awk '{print $1}' | grep -qx "${CONDA_ENV}" && ENV_EXISTS=true
else
    # 直接检查环境目录兜底
    if [[ -d "${CONDA_BASE}/envs/${CONDA_ENV}" ]]; then
        ENV_EXISTS=true
        ENV_PYTHON="${CONDA_BASE}/envs/${CONDA_ENV}/bin/python"
    fi
fi

if [[ "${ENV_EXISTS}" != "true" ]]; then
    err "Conda 环境 '${CONDA_ENV}' 不存在！可用环境:"
    echo ""
    conda env list 2>/dev/null | grep -v '^#' | grep -v '^$' || true
    echo ""
    err "请通过环境变量指定正确的环境:  export GEORAG_CONDA_ENV=<环境名>"
    exit 1
fi

# ---------------- 4. 激活环境 ----------------
if [[ -f "${CONDA_SH}" ]]; then
    source "${CONDA_SH}"
    conda activate "${CONDA_ENV}"
else
    # 无 conda.sh 时直接使用环境 python (仍可运行,但建议完整激活)
    PATH="${CONDA_BASE}/envs/${CONDA_ENV}/bin:${PATH}"
fi
PYTHON_BIN="$(command -v python)"
log "Python: $(python --version 2>&1) @ $(command -v python)"
echo ""

# ---------------- 5. 依赖完整性检查 ----------------
if ! python -c "import fastapi, uvicorn, dotenv, langchain" >/dev/null 2>&1; then
    warn "当前环境缺少项目依赖，正在尝试安装..."
    pip install -r requirements.txt || {
        err "依赖安装失败，请手动执行: pip install -r requirements.txt"
        exit 1
    }
fi

# ---------------- 6. (可选) pgvector 数据库检查 ----------------
if [[ "${SKIP_DB}" != "true" ]] && grep -q '^USE_PGVECTOR=true' "${PROJECT_ROOT}/.env" 2>/dev/null; then
    DB_PORT="$(grep -oE ':[0-9]+/georag' "${PROJECT_ROOT}/.env" | head -1 | tr -d ':/' || echo 5434)"
    if nc -z localhost "${DB_PORT}" >/dev/null 2>&1; then
        log "pgvector 数据库已就绪 (localhost:${DB_PORT})"
    else
        warn "USE_PGVECTOR=true 但数据库 (localhost:${DB_PORT}) 未就绪。"
        if command -v docker >/dev/null 2>&1; then
            warn "尝试通过 docker compose 启动 pgvector 容器..."
            docker compose up -d postgres 2>/dev/null || docker-compose up -d postgres 2>/dev/null || {
                warn "docker 启动失败，请手动执行: docker compose up -d postgres"
            }
        else
            warn "未安装 docker，请手动启动 PostgreSQL (见 docker-compose.yml)。"
        fi
    fi
fi

# ---------------- 7. 启动服务并打开浏览器 ----------------
log "正在启动 GeoRAG 服务..."
echo ""
echo "  🚀 服务地址:   ${APP_BASE_URL}"
echo "  📖 API 文档:   ${API_DOCS_URL}"
echo "  🔍 健康检查:   ${HEALTH_URL}"
echo "  (Ctrl+C 停止服务)"
echo ""

# 延迟打开浏览器 (等服务起来)
(
    sleep 4
    open "${API_DOCS_URL}" >/dev/null 2>&1 || true
) &
OPENER_PID=$!

# 前台运行, Ctrl+C 可直接停止
set +e
python main.py
EXIT_CODE=$?
set -e

# 清理后台任务
kill "${OPENER_PID}" >/dev/null 2>&1 || true
if [[ ${EXIT_CODE} -ne 0 ]]; then
    err "服务异常退出 (exit=${EXIT_CODE})，请查看上方日志。"
fi
exit ${EXIT_CODE}
