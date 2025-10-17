#!/bin/bash
#
# SSL证书自动配置脚本 - 使用Let's Encrypt
# 用法: sudo bash setup_ssl.sh your-domain.com
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为root
if [ "$EUID" -ne 0 ]; then 
    echo_error "请使用sudo运行此脚本"
    exit 1
fi

# 检查参数
if [ -z "$1" ]; then
    echo_error "用法: sudo bash setup_ssl.sh your-domain.com"
    echo_error "例如: sudo bash setup_ssl.sh avatar.example.com"
    exit 1
fi

DOMAIN=$1
EMAIL=${2:-"admin@$DOMAIN"}

echo_info "==================================="
echo_info "SSL证书配置脚本"
echo_info "==================================="
echo ""
echo "域名: $DOMAIN"
echo "邮箱: $EMAIL"
echo ""

# 1. 安装Certbot
echo_info "1. 安装Certbot..."
apt update
apt install -y certbot python3-certbot-nginx

# 2. 检查Nginx配置
echo_info "2. 检查Nginx配置..."
nginx -t

if [ $? -ne 0 ]; then
    echo_error "Nginx配置有误，请先修复"
    exit 1
fi

# 3. 检查域名解析
echo_info "3. 检查域名解析..."
SERVER_IP=$(curl -s ifconfig.me)
DOMAIN_IP=$(dig +short $DOMAIN | head -n 1)

echo "   服务器IP: $SERVER_IP"
echo "   域名解析: $DOMAIN_IP"

if [ "$SERVER_IP" != "$DOMAIN_IP" ]; then
    echo_warn "域名解析不匹配！"
    echo_warn "请确保域名 $DOMAIN 解析到服务器 $SERVER_IP"
    read -p "是否继续? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 4. 备份现有Nginx配置
echo_info "4. 备份Nginx配置..."
NGINX_CONFIG="/etc/nginx/sites-available/lightavatar"
if [ -f "$NGINX_CONFIG" ]; then
    cp $NGINX_CONFIG ${NGINX_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)
    echo_info "   备份完成"
fi

# 5. 更新Nginx配置中的域名
echo_info "5. 更新Nginx配置..."
sed -i "s/server_name .*/server_name $DOMAIN;/" $NGINX_CONFIG
nginx -s reload

# 6. 获取SSL证书
echo_info "6. 获取Let's Encrypt证书..."
certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email $EMAIL --redirect

if [ $? -eq 0 ]; then
    echo_info "   ✓ SSL证书获取成功"
else
    echo_error "   ✗ SSL证书获取失败"
    exit 1
fi

# 7. 配置自动续期
echo_info "7. 配置证书自动续期..."
systemctl status certbot.timer

# 测试续期
certbot renew --dry-run

if [ $? -eq 0 ]; then
    echo_info "   ✓ 自动续期配置成功"
else
    echo_warn "   ⚠ 自动续期测试失败"
fi

# 8. 优化SSL配置
echo_info "8. 优化SSL配置..."

# 检查是否已有SSL配置段
if ! grep -q "ssl_protocols" $NGINX_CONFIG; then
    # 在server块中添加SSL优化配置
    cat >> $NGINX_CONFIG << 'EOF'

    # SSL优化配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # 其他安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
EOF
    
    echo_info "   ✓ SSL优化配置已添加"
fi

# 9. 测试并重启Nginx
echo_info "9. 重启Nginx..."
nginx -t && systemctl reload nginx

echo ""
echo_info "==================================="
echo_info "SSL配置完成！"
echo_info "==================================="
echo ""
echo_info "访问地址："
echo_info "  主界面:   https://$DOMAIN"
echo_info "  API文档:  https://$DOMAIN/docs"
echo_info "  健康检查: https://$DOMAIN/health"
echo ""
echo_info "证书信息："
certbot certificates
echo ""
echo_info "证书有效期: 90天"
echo_info "自动续期: 已启用（每天检查2次）"
echo ""
echo_info "手动续期命令:"
echo_info "  sudo certbot renew"
echo ""
