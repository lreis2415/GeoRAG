FROM docker.anye.in/library/python:3.11

ENV PYTHONDONTWRITEBYTECODE=1


RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

COPY . /GeoRAGApp

WORKDIR /GeoRAGApp

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

CMD ["python3","GeoRAGApp.py"] 