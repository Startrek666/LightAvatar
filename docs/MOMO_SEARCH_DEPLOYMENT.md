# Momo Search 高级搜索集成部署指南

本文档将指导你如何在服务器上部署和配置 Momo Search 高级搜索功能。

---

## 📋 目录

1. [功能概述](#功能概述)
2. [前置要求](#前置要求)
3. [部署 SearXNG](#部署-searxng)
4. [安装 Python 依赖](#安装-python-依赖)
5. [配置 Momo Search](#配置-momo-search)
6. [下载嵌入模型](#下载嵌入模型)
7. [启动服务并测试](#启动服务并测试)
8. [故障排查](#故障排查)

---

## 功能概述

**Momo Search** 是一个基于向量检索的高级联网搜索系统，提供比简单搜索更强大的功能：

### 🆚 对比简单搜索

| 特性 | 简单搜索 (WebSearchHandler) | 高级搜索 (Momo Search) |
|------|---------------------------|---------------------|
| **搜索引擎** | DuckDuckGo | SearXNG (聚合多个搜索引擎) |
| **搜索结果** | 3-5个 | 50个候选 |
| **内容筛选** | 无 | FAISS向量检索 |
| **深度爬取** | 简单提取 | 完整网页内容提取 |
| **文档分块** | 无 | 智能分块和二次检索 |
| **引用标注** | 无 | 自动添加 [citation:X] |
| **搜索模式** | 单一 | 快速/深度双模式 |

### 🎯 两种搜索模式

- **Speed 模式（快速）**：3-5秒
  - SearXNG搜索 → FAISS筛选 → 生成回答
  
- **Quality 模式（深度）**：10-20秒
  - SearXNG搜索 → FAISS筛选 → 深度爬取 → 文档分块 → 二次检索 → 生成回答

---

## 前置要求

### 系统要求

- **操作系统**: Linux (推荐 Ubuntu 20.04+)
- **内存**: 至少 4GB (推荐 8GB+)
- **磁盘**: 至少 10GB 空闲空间
- **Docker**: 已安装 Docker 和 Docker Compose

### 已安装的软件

```bash
# 检查 Docker
docker --version

# 检查 Docker Compose
docker-compose --version

# 如果未安装，请先安装 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

---

## 部署 SearXNG

SearXNG 是一个隐私友好的元搜索引擎，聚合多个搜索源。

### 步骤1: 创建 SearXNG 目录

```bash
cd /opt
sudo mkdir -p searxng
cd searxng
```

### 步骤2: 创建 docker-compose.yml

```bash
sudo nano docker-compose.yml
```

粘贴以下内容：

```yaml
version: '3.7'

services:
  searxng:
    container_name: searxng
    image: searxng/searxng:latest
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - ./searxng:/etc/searxng:rw
    environment:
      - SEARXNG_BASE_URL=http://localhost:8080/
```

**保存**: `Ctrl+O`, `Enter`, `Ctrl+X`

### 步骤3: 创建 SearXNG 配置文件

```bash
# 创建配置目录
sudo mkdir -p searxng

# 创建配置文件
sudo nano searxng/settings.yml
```

粘贴以下内容：

```yaml
# SearXNG Configuration
use_default_settings: true

general:
  debug: false
  instance_name: "SearXNG for Momo Search"

search:
  safe_search: 0
  autocomplete: ""
  default_lang: "zh-CN"
  formats:
    - html
    - json

server:
  port: 8080
  bind_address: "0.0.0.0"
  secret_key: "ultrasecretkey"  # 请修改为随机字符串
  limiter: false
  image_proxy: false

ui:
  static_use_hash: true
  default_locale: "zh-CN"
  query_in_title: false
  infinite_scroll: false
  center_alignment: false

engines:
  - name: google
    disabled: false
  - name: bing
    disabled: false
  - name: duckduckgo
    disabled: false
  - name: baidu
    disabled: false
  - name: wikipedia
    disabled: false
```

**保存**: `Ctrl+O`, `Enter`, `Ctrl+X`

### 步骤4: 启动 SearXNG

```bash
# 启动容器
sudo docker-compose up -d

# 查看日志
sudo docker-compose logs -f
```

等待片刻，直到看到 "uvicorn started" 消息。

### 步骤5: 测试 SearXNG

```bash
# 测试搜索API
curl "http://localhost:8080/search?q=test&format=json&language=zh-CN" | head -n 50

# 应该返回JSON格式的搜索结果
```

如果返回搜索结果，说明 SearXNG 部署成功！

---

## 安装 Python 依赖

### 步骤1: 进入项目目录

```bash
cd /path/to/lightweight-avatar-chat
```

### 步骤2: 激活虚拟环境

```bash
# 如果使用 venv
source venv/bin/activate

# 或者使用 conda
conda activate your-env-name
```

### 步骤3: 安装新依赖

```bash
pip install faiss-cpu>=1.7.4
pip install sentence-transformers>=2.2.2
pip install langchain-text-splitters>=0.2.0

# 或者直接安装所有依赖
pip install -r requirements.txt
```

**重要**: 这些包比较大，特别是 `sentence-transformers` (约 500MB)，请耐心等待。

---

## 配置 Momo Search

### 步骤1: 编辑配置文件

```bash
cd /path/to/lightweight-avatar-chat
nano config/config.yaml
```

### 步骤2: 修改搜索配置

找到 `search` 部分，修改如下：

```yaml
# Search settings
search:
  # 简单搜索 (WebSearchHandler - DuckDuckGo)
  simple:
    enabled: true
    max_results: 5
    fetch_content: true
    content_max_length: 2000
  
  # 高级搜索 (MomoSearchHandler - SearXNG + FAISS)
  advanced:
    enabled: true  # ✅ 改为 true
    searxng_url: "http://localhost:8080"  # SearXNG地址
    searxng_language: "zh"  # "zh" 中文 或 "en" 英文
    searxng_time_range: "day"  # "day", "week", "month", "year", ""
    max_search_results: 50  # SearXNG 搜索结果数量
    
    # 向量检索配置
    embedding_model: "BAAI/bge-small-zh-v1.5"  # 中文嵌入模型
    num_candidates: 40  # 候选文档数量
    sim_threshold: 0.45  # 相似度阈值 (0-1)
    
    # 深度爬取配置
    enable_deep_crawl: true  # 是否启用深度网页爬取
    crawl_score_threshold: 0.5  # 只爬取相似度高于此值的文档
    max_crawl_docs: 10  # 最多爬取的文档数量
```

**保存**: `Ctrl+O`, `Enter`, `Ctrl+X`

### 步骤3: 重要配置说明

#### SearXNG 配置

- `searxng_url`: SearXNG服务地址
  - 本地部署: `http://localhost:8080`
  - 远程部署: `http://your-server-ip:8080`

- `searxng_language`: 搜索语言
  - `zh`: 中文
  - `en`: 英文

- `searxng_time_range`: 搜索时间范围
  - `day`: 最近一天
  - `week`: 最近一周
  - `month`: 最近一个月
  - `year`: 最近一年
  - `""`: 不限时间

#### 向量检索配置

- `embedding_model`: 嵌入模型
  - 中文: `BAAI/bge-small-zh-v1.5` (推荐)
  - 英文: `sentence-transformers/all-MiniLM-L6-v2`
  - 多语言: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`

- `sim_threshold`: 相似度阈值
  - 越高越严格，返回结果越少但更准确
  - 推荐范围: 0.4-0.6

#### 深度爬取配置

- `enable_deep_crawl`: 是否启用深度爬取
  - `true`: Quality模式会爬取完整网页内容
  - `false`: 只使用搜索引擎摘要

---

## 下载嵌入模型

首次运行时，系统会自动下载嵌入模型。为了避免运行时下载失败，建议提前下载。

### 方法1: Python命令预下载

```bash
# 激活虚拟环境
source venv/bin/activate

# 进入Python
python3
```

在Python交互式环境中：

```python
from sentence_transformers import SentenceTransformer

# 下载模型 (约300MB)
print("正在下载模型...")
model = SentenceTransformer('BAAI/bge-small-zh-v1.5')
print("模型下载完成！")

# 测试模型
embeddings = model.encode(["测试文本"])
print(f"嵌入维度: {embeddings.shape}")

# 退出
exit()
```

### 方法2: 直接启动服务下载

```bash
# 启动后端，首次运行会自动下载
python backend/app/main.py
```

观察日志，看到类似信息说明下载成功：

```
✅ 嵌入模型加载成功: BAAI/bge-small-zh-v1.5
📦 FAISS检索器初始化: dim=512, candidates=40, threshold=0.45
✅ Momo Search Handler 初始化完成
```

---

## 启动服务并测试

### 步骤1: 启动后端

```bash
cd /path/to/lightweight-avatar-chat

# 激活虚拟环境
source venv/bin/activate

# 启动后端
python backend/app/main.py
```

检查日志中是否有：

```
✅ Momo search handler initialized for session xxx
```

### 步骤2: 启动前端

新开终端：

```bash
cd /path/to/lightweight-avatar-chat/frontend
npm run dev
```

### 步骤3: 在浏览器中测试

1. 打开 `http://localhost:3000`
2. 点击"联网搜索"开关 (开启)
3. 在搜索模式下拉框中选择：
   - **简单**: 使用 DuckDuckGo 简单搜索
   - **高级**: 使用 Momo Search
4. 如果选择"高级"，选择搜索质量：
   - **快速**: Speed 模式 (3-5秒)
   - **深度**: Quality 模式 (10-20秒)

### 步骤4: 测试搜索

发送测试消息：

```
英伟达最新股价是多少？
```

或

```
2024年AI发展趋势
```

观察后端日志：

```
🔍 执行Momo高级搜索: 英伟达最新股价是多少？ (模式: speed)
✅ SearXNG搜索完成: 获得50个结果
🎯 找到15个相关文档（阈值>0.45）
✅ Momo搜索完成: 返回15个文档
```

如果一切正常，你应该看到带引用标注的回答：

```
英伟达（NVIDIA）最新股价为$500[1][3]，较前一交易日上涨3.5%[2]...

📚 参考来源：
1. [英伟达股价实时行情 - 新浪财经](https://finance.sina.com.cn/...)
2. [NVIDIA Corporation Stock - Yahoo Finance](https://finance.yahoo.com/...)
3. [英伟达今日股价 - 东方财富网](https://quote.eastmoney.com/...)
```

---

## 故障排查

### 问题1: SearXNG 无法访问

**症状**：
```
❌ SearXNG请求失败: Connection refused
```

**解决方法**：

```bash
# 检查 SearXNG 是否运行
sudo docker ps | grep searxng

# 如果未运行，启动它
cd /opt/searxng
sudo docker-compose up -d

# 查看日志
sudo docker-compose logs -f

# 测试连接
curl http://localhost:8080/search?q=test&format=json
```

### 问题2: 嵌入模型下载失败

**症状**：
```
❌ 嵌入模型加载失败: Connection timeout
```

**解决方法**：

```bash
# 方法1: 设置国内镜像源
export HF_ENDPOINT=https://hf-mirror.com
python backend/app/main.py

# 方法2: 手动下载模型
mkdir -p ~/.cache/huggingface/hub
cd ~/.cache/huggingface/hub

# 使用 huggingface-cli 下载
pip install huggingface-hub
huggingface-cli download BAAI/bge-small-zh-v1.5 --local-dir bge-small-zh-v1.5

# 方法3: 使用国内镜像
git clone https://hf-mirror.com/BAAI/bge-small-zh-v1.5
```

### 问题3: 内存不足

**症状**：
```
Killed
或
MemoryError
```

**解决方法**：

```bash
# 1. 使用更小的模型
nano config/config.yaml

# 修改为：
embedding_model: "sentence-transformers/all-MiniLM-L6-v2"  # 只有80MB

# 2. 减少候选文档数量
num_candidates: 20  # 从40改为20
max_search_results: 30  # 从50改为30

# 3. 禁用深度爬取
enable_deep_crawl: false
```

### 问题4: 搜索速度慢

**症状**: Quality模式超过30秒

**解决方法**：

```bash
# 1. 使用 Speed 模式（不启用深度爬取）

# 2. 减少爬取的文档数量
nano config/config.yaml

max_crawl_docs: 5  # 从10改为5

# 3. 提高相似度阈值（返回更少但更相关的结果）
sim_threshold: 0.55  # 从0.45改为0.55
```

### 问题5: 向量检索没有结果

**症状**：
```
⚠️ 未找到相关文档
```

**解决方法**：

```bash
# 降低相似度阈值
nano config/config.yaml

sim_threshold: 0.35  # 从0.45降到0.35

# 增加候选文档数量
num_candidates: 50  # 从40增到50
```

### 问题6: 引用标注不显示

**检查**：

1. 后端日志中是否有 `citations_text`
2. 前端是否正确处理包含引用的消息
3. LLM 是否理解了引用格式要求

---

## 性能优化建议

### 1. SearXNG 优化

```yaml
# searxng/settings.yml

# 启用缓存
outgoing:
  request_timeout: 5.0  # 减少超时时间
  max_request_timeout: 10.0

# 限制并发请求
search:
  max_page: 1  # 只搜索第一页（Momo会自动翻页）
```

### 2. 嵌入模型优化

```python
# 使用GPU加速（如果有GPU）
nano config/config.yaml

embedding_model: "BAAI/bge-small-zh-v1.5"
# 后端会自动检测GPU并使用

# 或使用更小的模型
embedding_model: "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
```

### 3. 系统资源优化

```bash
# 增加文件描述符限制
sudo nano /etc/security/limits.conf

# 添加：
* soft nofile 65536
* hard nofile 65536

# 增加 Docker 资源限制
sudo nano docker-compose.yml

# 在 searxng 服务下添加：
deploy:
  resources:
    limits:
      memory: 1G
    reservations:
      memory: 512M
```

---

## 日常维护

### 定期更新 SearXNG

```bash
cd /opt/searxng
sudo docker-compose pull
sudo docker-compose up -d
```

### 清理模型缓存

```bash
# 清理 Hugging Face 缓存
rm -rf ~/.cache/huggingface/hub

# 重新下载
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')"
```

### 监控日志

```bash
# 后端日志
tail -f logs/app.log

# SearXNG 日志
cd /opt/searxng
sudo docker-compose logs -f
```

---

## 总结

完成以上步骤后，你应该已经成功部署了 Momo Search 高级搜索功能！

**功能验证清单**：

- [x] SearXNG 正常运行
- [x] Python 依赖已安装
- [x] 嵌入模型已下载
- [x] 配置文件已修改
- [x] 后端启动无错误
- [x] 前端显示搜索模式选择
- [x] 测试搜索返回带引用的结果

如有问题，请参考[故障排查](#故障排查)部分或提交 Issue。

---

**相关文档**：
- [SearXNG 官方文档](https://docs.searxng.org/)
- [Momo-Search 原项目](https://github.com/yourusername/Momo-Search-master)
- [FAISS 文档](https://github.com/facebookresearch/faiss)
- [Sentence Transformers 文档](https://www.sbert.net/)



