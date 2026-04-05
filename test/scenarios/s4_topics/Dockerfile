FROM python:3.12-slim
WORKDIR /app

COPY common/ ./common/

COPY s4_topics/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY s4_topics/producer.py .
COPY s4_topics/consumer_a.py .
COPY s4_topics/consumer_b.py .
COPY s4_topics/consumer_c.py .

CMD ["python", "-u", "producer.py"]
