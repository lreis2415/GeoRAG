#!/bin/bash

# 检查Docker是否运行
if ! docker info > /dev/null 2>&1; then
    echo "错误: Docker服务未运行"
    exit 1
fi

# 检查docker-compose是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "错误: docker-compose未安装"
    exit 1
fi

# 检查.env文件是否存在
if [ ! -f .env ]; then
    echo "警告: .env文件不存在"
    echo "请先创建.env文件并配置必要的环境变量:"
    echo "  - OPENAI_API_BASE"
    echo "  - OPENAI_API_KEY"
    echo "  - EMBEDDING_API_URL"
    echo ""
    read -p "是否继续? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 停止并删除旧容器
echo "正在停止旧容器..."
docker-compose down -v

# 构建并启动服务
echo "正在构建并启动Docker服务..."
docker-compose up -d --build

# 检查服务是否成功启动
if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "服务已成功启动!"
    echo "=========================================="
    echo "GeoRAG API: http://localhost:7512"
    echo "API 文档: http://localhost:7512/docs"
    echo "健康检查: http://localhost:7512/llm/health"
    echo ""
    echo "数据库信息:"
    echo "  主机: localhost"
    echo "  端口: 5434"
    echo "  数据库: georag_dev"
    echo "  用户: geo"
    echo ""
    echo "查看日志:"
    echo "  docker-compose logs -f"
    echo ""
    echo "停止服务:"
    echo "  docker-compose down"
    echo "=========================================="
else
    echo "错误: 服务启动失败"
    exit 1
fi
