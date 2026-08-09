#!/usr/bin/env bash
# ============================================================
# 后端 + Cloudflare Tunnel 一键部署脚本
# 用途：在没有域名的情况下，为 GitHub Pages 提供 WSS 后端
# 说明：使用 Cloudflare Quick Tunnel（*.trycloudflare.com），无需域名、无需账号
# 注意：Quick Tunnel URL 每次重启会变，适合测试/演示
# 用法：
#   export LLM_API_KEY="sk-..."
#   export LLM_BASE_URL="http://.../v1"
#   bash scripts/deploy-backend-cloudflared.sh
# ============================================================

set -euo pipefail

REPO_URL="https://github.com/HeDaas-Code/mars-base-sandbox.git"
INSTALL_DIR="${HOME}/mars-base-sandbox"
BRANCH="deploy"
BACKEND_PORT="${BACKEND_PORT:-8000}"
SERVICE_NAME="mars-signal-backend"

# 检查必要环境变量
if [ -z "${LLM_API_KEY:-}" ] || [ -z "${LLM_BASE_URL:-}" ]; then
    echo "[ERROR] 请先设置环境变量："
    echo "  export LLM_API_KEY='sk-...'"
    echo "  export LLM_BASE_URL='http://.../v1'"
    exit 1
fi

# 安装 cloudflared
install_cloudflared() {
    if command -v cloudflared &> /dev/null; then
        echo "[INFO] cloudflared 已安装: $(cloudflared --version | head -n 1)"
        return
    fi

    echo "[INFO] 正在安装 cloudflared..."
    local tmpdir=$(mktemp -d)
    cd "${tmpdir}"

    local arch=$(uname -m)
    case "${arch}" in
        x86_64)  arch="amd64" ;;
        aarch64) arch="arm64" ;;
        armv7l)  arch="arm" ;;
    esac

    local os=$(uname -s | tr '[:upper:]' '[:lower:]')
    local url="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-${os}-${arch}"

    curl -fsSL "${url}" -o cloudflared
    chmod +x cloudflared
    sudo mv cloudflared /usr/local/bin/cloudflared
    cd -
    rm -rf "${tmpdir}"

    echo "[INFO] cloudflared 安装完成: $(cloudflared --version | head -n 1)"
}

# 克隆或更新代码
setup_code() {
    if [ -d "${INSTALL_DIR}/.git" ]; then
        echo "[INFO] 更新代码..."
        cd "${INSTALL_DIR}"
        git fetch origin
        git reset --hard "origin/${BRANCH}"
    else
        echo "[INFO] 克隆代码..."
        git clone --branch "${BRANCH}" --depth 1 "${REPO_URL}" "${INSTALL_DIR}"
        cd "${INSTALL_DIR}"
    fi
}

# 安装 Python 依赖并写入环境变量
setup_backend() {
    echo "[INFO] 创建 Python 虚拟环境..."
    python3 -m venv "${INSTALL_DIR}/venv"
    source "${INSTALL_DIR}/venv/bin/activate"

    echo "[INFO] 安装依赖..."
    cd "${INSTALL_DIR}/backend"
    python3 -m pip install -q --upgrade pip
    python3 -m pip install -q -r requirements.txt

    cat > "${INSTALL_DIR}/backend/.env" <<EOF
LLM_API_KEY=${LLM_API_KEY}
LLM_BASE_URL=${LLM_BASE_URL}
PORT=${BACKEND_PORT}
EOF
    echo "[INFO] 环境变量已写入 ${INSTALL_DIR}/backend/.env"
}

# 创建并启动后端 systemd 服务
start_backend_service() {
    local service_file="/etc/systemd/system/${SERVICE_NAME}.service"

    echo "[INFO] 创建后端 systemd 服务..."
    sudo tee "${service_file}" > /dev/null <<EOF
[Unit]
Description=Mars Signal WebSocket Backend
After=network.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${INSTALL_DIR}/backend
EnvironmentFile=${INSTALL_DIR}/backend/.env
ExecStart=${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/backend/ws_server.py --host 127.0.0.1 --port ${BACKEND_PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable "${SERVICE_NAME}"
    sudo systemctl restart "${SERVICE_NAME}"

    sleep 2
    echo "[INFO] 后端服务状态："
    sudo systemctl status "${SERVICE_NAME}" --no-pager || true
}

# 启动 Cloudflare Quick Tunnel（systemd 后台服务，SSH 断开后保持运行）
start_tunnel() {
    local tunnel_service="mars-signal-tunnel"
    local log_file="/var/log/mars-signal-tunnel.log"

    echo "[INFO] 创建 Cloudflare Tunnel systemd 服务..."
    sudo tee "/etc/systemd/system/${tunnel_service}.service" > /dev/null <<EOF
[Unit]
Description=Cloudflare Tunnel for Mars Signal
After=network.target ${SERVICE_NAME}.service
Wants=${SERVICE_NAME}.service

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/cloudflared tunnel --url http://127.0.0.1:${BACKEND_PORT} --metrics localhost:45678
Restart=always
RestartSec=5
StandardOutput=append:${log_file}
StandardError=append:${log_file}

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable "${tunnel_service}"
    # 清空旧日志，确保获取到最新 URL
    sudo rm -f "${log_file}"
    sudo systemctl restart "${tunnel_service}"

    echo "[INFO] 等待 Cloudflare Tunnel 启动并获取公网 URL..."
    local url=""
    for i in $(seq 1 30); do
        if sudo test -f "${log_file}"; then
            url=$(sudo grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" "${log_file}" | head -n 1)
            if [ -n "${url}" ]; then
                break
            fi
        fi
        sleep 2
    done

    echo ""
    if [ -n "${url}" ]; then
        echo "============================================================"
        echo "[OK] 公网 HTTPS 地址：${url}"
        echo "[OK] WebSocket 地址：${url}/ws （WSS，可直接填入 GitHub WS_URL）"
        echo "[OK] 健康检查：${url}/health"
        echo "============================================================"
        echo ""
        echo "[INFO] Tunnel 已作为 systemd 服务 '${tunnel_service}' 在后台运行"
        echo "[INFO] SSH 断开后仍然有效"
        echo "[INFO] 查看状态：sudo systemctl status ${tunnel_service}"
        echo "[INFO] 查看日志：sudo tail -f ${log_file}"
    else
        echo "[WARN] 未能自动获取 Tunnel URL"
        echo "[INFO] 请查看日志：sudo tail -f ${log_file}"
        echo "[INFO] 或查看服务状态：sudo systemctl status ${tunnel_service}"
    fi
}

# 主流程
install_cloudflared
setup_code
setup_backend
start_backend_service
start_tunnel
