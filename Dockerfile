FROM python:alpine
LABEL authors="okuznetsov"

WORKDIR /app
COPY . /app
RUN pip3 install --no-cache-dir -r requirements.txt
EXPOSE 3000
ENTRYPOINT ["python", "main.py"]