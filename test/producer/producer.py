#!/usr/bin/env python3
"""
RabbitMQ producer — publishes JSON messages continuously.

Env vars:
  RABBITMQ_HOSTS             comma-separated broker IPs/hostnames
  RABBITMQ_USER              AMQP username
  RABBITMQ_PASS              AMQP password
  QUEUE_NAME                 target queue (default: test.messages)
  PUBLISH_INTERVAL_SECONDS   sleep between publishes (default: 1)
"""

import json
import os
import socket
import time

import pika

HOSTS = os.environ["RABBITMQ_HOSTS"].split(",")
USER = os.environ["RABBITMQ_USER"]
PASS = os.environ["RABBITMQ_PASS"]
QUEUE = os.environ.get("QUEUE_NAME", "test.messages")
INTERVAL = float(os.environ.get("PUBLISH_INTERVAL_SECONDS", "1"))
HOSTNAME = socket.gethostname()


def make_params(host: str) -> pika.ConnectionParameters:
    return pika.ConnectionParameters(
        host=host.strip(),
        port=5672,
        credentials=pika.PlainCredentials(USER, PASS),
        heartbeat=60,
        blocked_connection_timeout=300,
        connection_attempts=3,
        retry_delay=2,
    )


def connect() -> pika.BlockingConnection:
    """Cycle through all hosts until one accepts the connection."""
    while True:
        for host in HOSTS:
            try:
                print(f"[producer] connecting to {host}...", flush=True)
                conn = pika.BlockingConnection(make_params(host))
                print(f"[producer] connected to {host}", flush=True)
                return conn
            except pika.exceptions.AMQPConnectionError as exc:
                print(f"[producer] {host} unreachable: {exc}", flush=True)
        print("[producer] all hosts unreachable, retrying in 5s", flush=True)
        time.sleep(5)


def run() -> None:
    seq = 0
    connection = connect()
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE, durable=True)

    while True:
        try:
            seq += 1
            body = json.dumps({
                "seq": seq,
                "producer": HOSTNAME,
                "ts": time.time(),
            })
            channel.basic_publish(
                exchange="",
                routing_key=QUEUE,
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=pika.DeliveryMode.Persistent,
                ),
            )
            print(f"[producer] sent #{seq}", flush=True)
            time.sleep(INTERVAL)

        except (
            pika.exceptions.AMQPConnectionError,
            pika.exceptions.AMQPChannelError,
            pika.exceptions.StreamLostError,
        ) as exc:
            print(f"[producer] connection lost: {exc}, reconnecting", flush=True)
            try:
                connection.close()
            except Exception:
                pass
            connection = connect()
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE, durable=True)


if __name__ == "__main__":
    run()
