#!/usr/bin/env python3
"""
S2 Publish/Subscribe — producer.

Publishes broadcast log messages to a fanout exchange. Every bound consumer
receives every message (temporary exclusive queues per consumer).

Env vars:
  RABBITMQ_HOSTS             comma-separated broker IPs/hostnames
  RABBITMQ_USER              AMQP username
  RABBITMQ_PASS              AMQP password
  EXCHANGE_NAME              fanout exchange name (default: logs)
  PUBLISH_INTERVAL_SECONDS   sleep between publishes (default: 1)
"""

import json
import os
import socket
import time
from datetime import datetime, timezone

import pika

from common.connection import connect

HOSTS = os.environ["RABBITMQ_HOSTS"].split(",")
USER = os.environ["RABBITMQ_USER"]
PASS = os.environ["RABBITMQ_PASS"]
EXCHANGE = os.environ.get("EXCHANGE_NAME", "logs")
INTERVAL = float(os.environ.get("PUBLISH_INTERVAL_SECONDS", "1"))
HOSTNAME = socket.gethostname()


def setup(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="fanout", durable=True)


def run() -> None:
    seq = 0
    connection = connect(HOSTS, USER, PASS, role="s2-producer")
    channel = connection.channel()
    setup(channel)

    while True:
        try:
            seq += 1
            body = json.dumps({
                "seq": seq,
                "producer": HOSTNAME,
                "ts": datetime.now(timezone.utc).isoformat(),
                "log": f"Log entry #{seq}",
            })
            channel.basic_publish(
                exchange=EXCHANGE,
                routing_key="",
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=pika.DeliveryMode.Persistent,
                ),
            )
            print(f"[s2-producer] broadcast #{seq}", flush=True)
            time.sleep(INTERVAL)

        except (
            pika.exceptions.AMQPConnectionError,
            pika.exceptions.AMQPChannelError,
            pika.exceptions.StreamLostError,
        ) as exc:
            print(f"[s2-producer] connection lost: {exc}, reconnecting", flush=True)
            try:
                connection.close()
            except Exception:
                pass
            connection = connect(HOSTS, USER, PASS, role="s2-producer")
            channel = connection.channel()
            setup(channel)


if __name__ == "__main__":
    run()
