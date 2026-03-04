# 部署文档

## 打包部署文件

在本地开发环境中，使用以下命令打包必要文件：

```bash
tar -czf georag-deploy.tar.gz \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='data' \
  --exclude='logs' \
  --exclude='*.log' \
  --exclude='.git' \
  --exclude='archive' \
  --exclude='evaluation_logs' \
  --exclude='tests' \
  --exclude='.windsurf' \
  app main.py requirements.txt Dockerfile docker-compose.yml models.yaml run_docker.sh .env db
```

**打包内容包括：**
- `app/` - 应用程序代码
- `main.py` - 主入口文件
- `requirements.txt` - Python 依赖
- `Dockerfile` - Docker 镜像构建文件
- `docker-compose.yml` - Docker Compose 配置
- `models.yaml` - 模型配置
- `run_docker.sh` - Docker 部署脚本
- `.env` - 环境变量配置文件
- `.db` - 数据库初始化文件

**排除内容：**
- `data/` - 本地数据文件
- `logs/` - 日志文件
- `archive/` - 归档文件
- `evaluation_logs/` - 评估日志
- `tests/` - 测试文件
- `.git/` - Git 版本控制
- `.windsurf/` - Windsurf IDE 配置
- `__pycache__/`, `*.pyc` - Python 缓存文件

## 传输到服务器

### 使用 SCP 传输

```bash
scp georag-deploy.tar.gz root@8.130.184.170:~
```

### 使用 rsync 传输（推荐，支持断点续传）

```bash
rsync -avz --progress georag-deploy.tar.gz root@8.130.184.170:~
```

## 服务器端部署

### 1. 解压文件

```bash
# SSH 登录到服务器
ssh root@8.130.184.170

# 解压文件
tar -xzf georag-deploy.tar.gz

# 进入项目目录（根据实际部署路径调整）
cd /path/to/georag  # 或使用 cd ~ 如果解压在用户主目录
```

### 2. 配置环境变量

创建 `.env` 文件：

```bash
cat > .env << EOF
# OpenAI API 配置
OPENAI_API_KEY=your_api_key_here
OPENAI_API_BASE=https://api.openai.com/v1

# 嵌入模型 API
EMBEDDING_API_URL=https://api.example.com/embeddings

# 数据库配置
DB_URL=postgresql://geo:your_password@localhost:5432/georag_dev
USE_PGVECTOR=true

# 默认嵌入模型
DEFAULT_EMBEDDING_MODEL=text-embedding-v4

# 服务端口
PORT=7512
EOF
```

### 3. Docker 部署

#### 使用部署脚本（推荐）

```bash
# 添加执行权限
chmod +x run_docker.sh

# 运行部署脚本
./run_docker.sh
```

#### 手动部署



#### 使用 Docker Compose

```bash
# 构建并启动服务
docker compose -f 'docker-compose.yml' up -d --build 

# 仅启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 4. 验证部署

```bash
# 检查容器状态
docker ps | grep georag

# 查看容器日志
docker logs georag-app

# 健康检查
curl http://localhost:7512/llm/

# 查看 API 文档
curl http://localhost:7512/llm/docs
```

## 常用运维命令

### 查看日志

```bash
# 实时查看日志
docker logs -f georag-app

# 查看最近 100 行日志
docker logs --tail 100 georag-app
```

### 容器管理

```bash
# 停止容器
docker stop georag-app

# 启动容器
docker start georag-app

# 重启容器
docker restart georag-app

# 删除容器
docker rm georag-app

# 删除镜像
docker rmi georag-app
```

### 进入容器调试

```bash
# 进入容器 Shell
docker exec -it georag-app /bin/bash

# 查看容器内文件
docker exec georag-app ls -la /app
```

### 更新部署

```bash
# 1. 备份当前版本
tar -czf georag-backup-$(date +%Y%m%d).tar.gz app main.py requirements.txt Dockerfile docker-compose.yml models.yaml run_docker.sh

# 2. 停止并删除旧容器
docker stop georag-app
docker rm georag-app

# 3. 上传新版本
scp georag-deploy.tar.gz root@8.130.184.170:~

# 4. 解压并重新部署
ssh root@8.130.184.170
tar -xzf georag-deploy.tar.gz
./run_docker.sh
```

## 故障排查

### 容器无法启动

```bash
# 查看详细日志
docker logs georag-app

# 检查端口占用
netstat -tuln | grep 7512

# 检查环境变量
docker exec georag-app env | grep -E 'OPENAI|DB_URL|USE_PGVECTOR'
```

### 数据库连接失败

```bash
# 检查 PostgreSQL 容器状态
docker ps | grep postgres

# 测试数据库连接
docker exec -it georag-postgres psql -U geo -d georag_dev -c "SELECT 1;"

# 检查 pgvector 扩展
docker exec -it georag-postgres psql -U geo -d georag_dev -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

### 权限问题

```bash
# 修复 data 目录权限
sudo chown -R $(whoami):$(whoami) data/
chmod -R 755 data/
```

## 性能优化

### 数据库优化

```bash
# 启用 pgvector HNSW 索引
docker exec -it georag-postgres psql -U geo -d georag_dev -c "
CREATE INDEX ON documents USING hnsw (embedding vector_cosine_ops);
"
```

### 日志管理

```bash
# 清理旧日志
find logs/ -name "*.log" -mtime +30 -delete

# 配置日志轮转
cat > /etc/logrotate.d/georag << EOF
/path/to/georag/logs/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
EOF
```

## 安全建议

1. **防火墙配置**
```bash
# 只允许特定 IP 访问
firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="YOUR_IP/32" port port="7512" protocol="tcp" accept'
firewall-cmd --reload
```

2. **使用 HTTPS**
   - 配置 Nginx 反向代理
   - 使用 Let's Encrypt 证书

3. **环境变量保护**
```bash
# 设置 .env 文件权限
chmod 600 .env
```

4. **定期更新**
```bash
# 定期更新基础镜像
docker pull postgres:16-alpine
docker-compose build --no-cache
```
