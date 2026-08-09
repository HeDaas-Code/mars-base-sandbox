#!/usr/bin/env bash
# ============================================================
# 后端一键部署脚本
# 用途：在自有服务器上部署 Mars Signal WebSocket 后端
# 默认端口：80（需 root 或 sudo 授权）
# 用法：
#   export LLM_API_KEY="sk-..."
#   export LLM_BASE_URL="http://.../v1"
#   bash scripts/deploy-backend.sh
# ============================================================

set -euo pipefail

REPO_URL="https://github.com/HeDaas-Code/mars-base-sandbox.git"
INSTALL_DIR="${HOME}/mars-base-sandbox"
BRANCH="deploy"
PORT="${PORT:-80}"
SERVICE_NAME="mars-signal-backend"

# 检查必要环境变量
if [ -z "${LLM_API_KEY:-}" ] || [ -z "${LLM_BASE_URL:-}" ]; then
    echo "[ERROR] 请先设置环境变量："
    echo "  export LLM_API_KEY='sk-...'"
    echo "  export LLM_BASE_URL='http://.../v1'"
    exit 1
fi

echo "[INFO] 使用端口: ${PORT}"
echo "[INFO] 后端目录: ${INSTALL_DIR}"

# 克隆或更新代码
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

# 安装/升级 Python 依赖
echo "[INFO] 安装依赖..."
cd backend
python3 -m pip install --user -q --upgrade pip
python3 -m pip install --user -q -r requirements.txt

# 写入环境变量文件
cat > "${INSTALL_DIR}/backend/.env" <<EOF
LLM_API_KEY=${LLM_API_KEY}
LLM_BASE_URL=${LLM_BASE_URL}
PORT=${PORT}
EOF

echo "[INFO] 环境变量已写入 ${INSTALL_DIR}/backend/.env"

# 创建 systemd service 文件（需要 sudo）
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "[INFO] 创建 systemd 服务（需要 sudo）..."
sudo tee "${SERVICE_FILE}" > /dev/null <<EOF
[Unit]
Description=Mars Signal WebSocket Backend
After=network.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${INSTALL_DIR}/backend
EnvironmentFile=${INSTALL_DIR}/backend/.env
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/backend/ws_server.py --host 0.0.0.0 --port ${PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 如果端口 < 1024，给 python3 绑定特权端口的能力
if [ "${PORT}" -lt 1024 ]; then
    echo "[INFO] 端口 ${PORT} 是特权端口，配置 CAP_NET_BIND_SERVICE..."
    sudo setcap cap_net_bind_service=+ep "$(readlink -f "$(which python3)")" || {
        echo "[WARN] setcap 失败，将尝试以 root 启动服务。"
        sudo sed -i "s/^User=.*/User=root/" "${SERVICE_FILE}"
    }
fi

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

echo "[INFO] 服务已启动，查看状态："
sudo systemctl status "${SERVICE_NAME}" --no-pager

echo ""
echo "[OK] 部署完成"
echo "[OK] WebSocket 地址：ws://$(curl -s ifconfig.me || hostname -I | awk '{print $1}'):${PORT}/ws"
echo "[OK] 健康检查：http://$(curl -s ifconfig.me || hostname -I | awk '{print $1}'):${PORT}/health"
