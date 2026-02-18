#!/bin/bash
set -e

cd /root/cc-manager

# 加载环境变量
source ~/.bashrc

# 安装 Python 依赖
echo "=== Installing dependencies ==="
cd backend
/root/.local/bin/uv sync || pip install -r requirements.txt

# 启动 FastAPI 服务
echo "=== Starting CC Manager API on port 8080 ==="
python3.11 -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload

