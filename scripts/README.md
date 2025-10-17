# 部署脚本说明

本目录包含用于部署和管理 Lightweight Avatar Chat 的各种脚本。

## 📋 脚本列表

### 1. ubuntu_deploy.sh
**用途**: Ubuntu服务器自动部署脚本

**功能**:
- 更新系统并安装所有必需的依赖
- 安装Python 3.11和Node.js
- 克隆项目代码
- 创建虚拟环境并安装Python包
- 下载Whisper模型
- 设置基础目录结构

**使用方法**:
```bash
sudo bash scripts/ubuntu_deploy.sh
```

**注意**: 此脚本执行基础安装，完成后需要手动完成以下步骤：
- 下载Wav2Lip模型
- 配置config.yaml
- 构建前端
- 配置Nginx

---

### 2. download_models.sh
**用途**: 下载AI模型文件

**功能**:
- 交互式选择和下载Whisper模型（tiny/base/small/medium/large）
- 自动下载Wav2Lip模型（从多个源）
- 验证模型文件完整性

**使用方法**:
```bash
# 在项目根目录运行
bash scripts/download_models.sh
```

**可选模型大小**:
- `tiny` - 最快，准确率较低 (~75MB)
- `base` - 平衡 (~150MB)
- `small` - 推荐 (~470MB)
- `medium` - 高准确率 (~1.5GB)
- `large-v3` - 最高准确率 (~3GB)

---

### 3. convert_wav2lip_to_onnx.py
**用途**: 将Wav2Lip PyTorch模型转换为ONNX格式

**功能**:
- 加载PyTorch模型权重
- 导出为ONNX格式
- 验证转换正确性
- 性能优化

**使用方法**:
```bash
# 确保已下载wav2lip.pth
python scripts/convert_wav2lip_to_onnx.py
```

**优势**:
- ONNX格式推理速度更快
- 内存占用更低
- 更好的CPU优化

**要求**:
- `models/wav2lip/wav2lip.pth` 必须存在
- 已安装 `torch`, `onnx`, `onnxruntime`

---

### 4. check_environment.py
**用途**: 环境和依赖检查工具

**功能**:
- 检查Python版本（需要3.11+）
- 检查系统命令（ffmpeg, git, node等）
- 检查Python依赖包
- 检查项目结构完整性
- 检查模型文件
- 检查配置文件
- 检查端口占用

**使用方法**:
```bash
python scripts/check_environment.py
```

**输出示例**:
```
✓ Python版本: 3.11.5
✓ FFmpeg: 版本 4.4.2
✓ fastapi: 0.115.5
✓ 项目结构完整
⚠ Wav2Lip ONNX模型不存在（可选）

总计: 6/7 项检查通过
```

---

### 5. setup_ssl.sh
**用途**: 自动配置SSL证书（Let's Encrypt）

**功能**:
- 安装Certbot
- 验证域名解析
- 获取免费SSL证书
- 配置Nginx HTTPS
- 设置证书自动续期
- 优化SSL安全配置

**使用方法**:
```bash
sudo bash scripts/setup_ssl.sh your-domain.com [your-email@example.com]
```

**示例**:
```bash
sudo bash scripts/setup_ssl.sh avatar.example.com admin@example.com
```

**前提条件**:
- 域名已解析到服务器IP
- Nginx已正确配置并运行
- 80和443端口已开放

**自动续期**:
- 证书有效期90天
- 系统会每天自动检查2次
- 到期前30天自动续期

---

## 🚀 快速部署流程

### 方法一：完全自动化（推荐新服务器）

```bash
# 1. 基础环境安装
sudo bash scripts/ubuntu_deploy.sh

# 2. 下载模型
bash scripts/download_models.sh

# 3. 转换Wav2Lip为ONNX（可选，提升性能）
source venv/bin/activate
python scripts/convert_wav2lip_to_onnx.py

# 4. 检查环境
python scripts/check_environment.py

# 5. 配置文件
nano config/config.yaml  # 编辑配置

# 6. 构建前端
cd frontend
npm install
npm run build
cd ..

# 7. 配置Nginx和systemd（参考文档）
# 见 docs/UBUNTU_DEPLOYMENT.md

# 8. 配置SSL（如有域名）
sudo bash scripts/setup_ssl.sh your-domain.com
```

### 方法二：手动逐步部署

详细步骤请参考: `docs/UBUNTU_DEPLOYMENT.md`

---

## 📝 脚本依赖关系

```
ubuntu_deploy.sh (基础环境)
    ↓
download_models.sh (下载模型)
    ↓
convert_wav2lip_to_onnx.py (可选优化)
    ↓
check_environment.py (验证环境)
    ↓
[手动配置和部署]
    ↓
setup_ssl.sh (HTTPS配置)
```

---

## 🔧 故障排查

### 问题1: ubuntu_deploy.sh 运行失败

**可能原因**:
- 网络连接问题
- 权限不足
- 系统版本不兼容

**解决方法**:
```bash
# 检查网络
ping -c 4 8.8.8.8

# 检查系统版本
lsb_release -a

# 使用sudo
sudo bash scripts/ubuntu_deploy.sh
```

### 问题2: download_models.sh 下载缓慢

**解决方法**:
```bash
# 使用HuggingFace镜像
export HF_ENDPOINT=https://hf-mirror.com

# 重新运行
bash scripts/download_models.sh
```

### 问题3: convert_wav2lip_to_onnx.py 转换失败

**检查**:
```bash
# 确保wav2lip.pth存在
ls -lh models/wav2lip/wav2lip.pth

# 检查PyTorch是否安装
python -c "import torch; print(torch.__version__)"

# 手动运行
source venv/bin/activate
python scripts/convert_wav2lip_to_onnx.py
```

### 问题4: check_environment.py 检查失败

**根据输出修复**:
```bash
# Python包缺失
pip install -r requirements.txt

# 系统命令缺失
sudo apt install ffmpeg git nodejs npm

# 模型文件缺失
bash scripts/download_models.sh
```

### 问题5: setup_ssl.sh 证书获取失败

**常见原因**:
- 域名未正确解析
- 80端口未开放
- 防火墙阻止

**解决方法**:
```bash
# 检查域名解析
dig +short your-domain.com

# 检查端口
sudo netstat -tlnp | grep :80

# 检查防火墙
sudo ufw status
sudo ufw allow 'Nginx Full'
```

---

## 📚 相关文档

- [Ubuntu部署指南](../docs/UBUNTU_DEPLOYMENT.md) - 完整的部署步骤和脚本使用说明
- [架构文档](../docs/ARCHITECTURE.md) - 系统架构详解
- [使用说明](../docs/USAGE.md) - 功能使用指南
- [Avatar模板制作](../docs/AVATAR_TEMPLATE_GUIDE.md) - 数字人模板制作指南

---

## 🤝 贡献

欢迎提交改进建议和Bug报告！

## 📄 许可证

MIT License
