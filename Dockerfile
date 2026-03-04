FROM registry.cn-hangzhou.aliyuncs.com/onesis-geomodels/python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

COPY . /GeoRAGApp

WORKDIR /GeoRAGApp

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 暴露应用端口
EXPOSE 7512

# 启动应用
CMD ["python3", "main.py"]
