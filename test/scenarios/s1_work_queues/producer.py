#!/usr/bin/env python3
"""
S1 Work Queues — producer.

Sends task messages to a durable named queue at a fixed interval.
Each task carries a random number of dots; workers sleep one second per dot.

Env vars:
  RABBITMQ_HOSTS             comma-separated broker IPs/hostnames
  RABBITMQ_USER              AMQP username
  RABBITMQ_PASS              AMQP password
  QUEUE_NAME                 target queue (default: work.tasks)
  PUBLISH_INTERVAL_SECONDS   sleep between publishes (default: 1)
"""

import json
import os
import random
import socket
import time
from datetime import datetime, timezone

import pika

from common.connection import connect

HOSTS = os.environ["RABBITMQ_HOSTS"].split(",")
USER = os.environ["RABBITMQ_USER"]
PASS = os.environ["RABBITMQ_PASS"]
QUEUE = os.environ.get("QUEUE_NAME", "work.tasks")
INTERVAL = float(os.environ.get("PUBLISH_INTERVAL_SECONDS", "1"))
HOSTNAME = socket.gethostname()


def setup(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    channel.queue_declare(queue=QUEUE, durable=True)


def run() -> None:
    seq = 0
    connection = connect(HOSTS, USER, PASS, role="s1-producer")
    channel = connection.channel()
    setup(channel)

    while True:
        try:
            seq += 1
            dots = "." * random.randint(1, 5)
            body = json.dumps({
                "seq": seq,
                "producer": HOSTNAME,
                "ts": datetime.now(timezone.utc).isoformat(),
                "task": dots,
            })
            channel.basic_publish(
                exchange="",
                routing_key=QUEUE,
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=pika.DeliveryMode.Persistent,
                ),
            )
            print(f"[s1-producer] sent #{seq} task='{dots}'", flush=True)
            time.sleep(INTERVAL)

        except (
            pika.exceptions.AMQPConnectionError,
            pika.exceptions.AMQPChannelError,
            pika.exceptions.StreamLostError,
        ) as exc:
            print(f"[s1-producer] connection lost: {exc}, reconnecting", flush=True)
            try:
                connection.close()
            except Exception:
                pass
            connection = connect(HOSTS, USER, PASS, role="s1-producer")
            channel = connection.channel()
            setup(channel)


if __name__ == "__main__":
    run()
