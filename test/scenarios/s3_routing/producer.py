#!/usr/bin/env python3
"""
S3 Routing / Direct Exchange — producer.

Publishes messages to a direct exchange, cycling through routing keys
error → warning → info in round-robin. Consumers bind to specific keys
they care about.

Env vars:
  RABBITMQ_HOSTS             comma-separated broker IPs/hostnames
  RABBITMQ_USER              AMQP username
  RABBITMQ_PASS              AMQP password
  EXCHANGE_NAME              direct exchange name (default: direct_logs)
  PUBLISH_INTERVAL_SECONDS   sleep between publishes (default: 1)
"""

import itertools
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
EXCHANGE = os.environ.get("EXCHANGE_NAME", "direct_logs")
INTERVAL = float(os.environ.get("PUBLISH_INTERVAL_SECONDS", "1"))
HOSTNAME = socket.gethostname()

ROUTING_KEYS = ["error", "warning", "info"]


def setup(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="direct", durable=True)


def run() -> None:
    seq = 0
    connection = connect(HOSTS, USER, PASS, role="s3-producer")
    channel = connection.channel()
    setup(channel)

    for routing_key in itertools.cycle(ROUTING_KEYS):
        try:
            seq += 1
            body = json.dumps({
                "seq": seq,
                "producer": HOSTNAME,
                "ts": datetime.now(timezone.utc).isoformat(),
                "level": routing_key,
                "msg": f"[{routing_key.upper()}] Event #{seq}",
            })
            channel.basic_publish(
                exchange=EXCHANGE,
                routing_key=routing_key,
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=pika.DeliveryMode.Persistent,
                ),
            )
            print(f"[s3-producer] sent #{seq} level={routing_key}", flush=True)
            time.sleep(INTERVAL)

        except (
            pika.exceptions.AMQPConnectionError,
            pika.exceptions.AMQPChannelError,
            pika.exceptions.StreamLostError,
        ) as exc:
            print(f"[s3-producer] connection lost: {exc}, reconnecting", flush=True)
            try:
                connection.close()
            except Exception:
                pass
            connection = connect(HOSTS, USER, PASS, role="s3-producer")
            channel = connection.channel()
            setup(channel)


if __name__ == "__main__":
    run()
