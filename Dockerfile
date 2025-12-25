FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        libpq-dev \
        gcc \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

COPY . /GeoRAGApp

WORKDIR /GeoRAGApp

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 暴露应用端口
EXPOSE 7512

# 启动应用
CMD ["python3", "main.py"]
