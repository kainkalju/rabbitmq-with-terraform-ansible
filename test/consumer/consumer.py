#!/usr/bin/env python3
"""
RabbitMQ consumer — consumes messages with manual acknowledgment.

Env vars:
  RABBITMQ_HOSTS  comma-separated broker IPs/hostnames
  RABBITMQ_USER   AMQP username
  RABBITMQ_PASS   AMQP password
  QUEUE_NAME      source queue (default: test.messages)
"""

import json
import os
import time

import pika

HOSTS = os.environ["RABBITMQ_HOSTS"].split(",")
USER = os.environ["RABBITMQ_USER"]
PASS = os.environ["RABBITMQ_PASS"]
QUEUE = os.environ.get("QUEUE_NAME", "test.messages")


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
                print(f"[consumer] connecting to {host}...", flush=True)
                conn = pika.BlockingConnection(make_params(host))
                print(f"[consumer] connected to {host}", flush=True)
                return conn
            except pika.exceptions.AMQPConnectionError as exc:
                print(f"[consumer] {host} unreachable: {exc}", flush=True)
        print("[consumer] all hosts unreachable, retrying in 5s", flush=True)
        time.sleep(5)


def on_message(
    ch: pika.adapters.blocking_connection.BlockingChannel,
    method: pika.spec.Basic.Deliver,
    _properties: pika.spec.BasicProperties,
    body: bytes,
) -> None:
    try:
        data = json.loads(body)
        print(
            f"[consumer] received seq={data.get('seq')} "
            f"from={data.get('producer')} "
            f"ts={data.get('ts', 0):.3f}",
            flush=True,
        )
    except json.JSONDecodeError:
        print(f"[consumer] received non-JSON: {body!r}", flush=True)
    ch.basic_ack(delivery_tag=method.delivery_tag)


def run() -> None:
    while True:
        connection = connect()
        try:
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(
                queue=QUEUE,
                on_message_callback=on_message,
                auto_ack=False,
            )
            print("[consumer] waiting for messages", flush=True)
            channel.start_consuming()
        except (
            pika.exceptions.AMQPConnectionError,
            pika.exceptions.AMQPChannelError,
            pika.exceptions.StreamLostError,
        ) as exc:
            print(f"[consumer] connection lost: {exc}, reconnecting", flush=True)
            try:
                connection.close()
            except Exception:
                pass


if __name__ == "__main__":
    run()
