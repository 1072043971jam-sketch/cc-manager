#!/bin/bash
# CC Manager 启动脚本（使用 systemd）
systemctl restart cc-manager
systemctl status cc-manager --no-pager
echo ""
echo "Access: http://$(curl -s ifconfig.me 2>/dev/null || echo 118.25.107.200):8080"
