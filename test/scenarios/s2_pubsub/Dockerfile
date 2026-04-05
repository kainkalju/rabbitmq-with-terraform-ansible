FROM python:3.12-slim
WORKDIR /app

COPY common/ ./common/

COPY s2_pubsub/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY s2_pubsub/producer.py .
COPY s2_pubsub/consumer.py .

CMD ["python", "-u", "producer.py"]
