FROM python:3.12-slim
WORKDIR /app

COPY common/ ./common/

COPY s1_work_queues/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY s1_work_queues/producer.py .
COPY s1_work_queues/worker.py .

CMD ["python", "-u", "producer.py"]
