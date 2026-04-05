FROM python:3.12-slim
WORKDIR /app

COPY common/ ./common/

COPY s3_routing/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY s3_routing/producer.py .
COPY s3_routing/consumer_a.py .
COPY s3_routing/consumer_b.py .

CMD ["python", "-u", "producer.py"]
