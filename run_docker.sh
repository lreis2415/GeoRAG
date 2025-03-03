#!/bin/bash

# 检查Docker是否运行
if ! docker info > /dev/null 2>&1; then
    echo "错误: Docker服务未运行"
    exit 1
fi

# 构建镜像
echo "正在构建Docker镜像..."
docker build -t casetest:1.0 .

# 检查构建是否成功
if [ $? -ne 0 ]; then
    echo "错误: Docker镜像构建失败"
    exit 1
fi

# 运行容器
echo "正在启动容器..."
docker run -it -d \
    -p 0.0.0.0:7512:7512 \
    --name georag_service \
    casetest:1.0

# 检查容器是否成功启动
if [ $? -eq 0 ]; then
    echo "服务已成功启动在 http://localhost:7512"
else
    echo "错误: 容器启动失败"
    exit 1
fi
