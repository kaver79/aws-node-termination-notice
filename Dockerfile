FROM python:alpine
LABEL authors="okuznetsov"

WORKDIR /app
COPY . /app
RUN pip3 install --no-cache-dir -r requirements.txt
ENTRYPOINT ["python", "main.py"]