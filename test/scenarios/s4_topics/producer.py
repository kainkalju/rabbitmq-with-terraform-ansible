#!/usr/bin/env python3
"""
S4 Topics — producer.

Publishes messages to a topic exchange, cycling through dotted routing keys.
Consumers subscribe with wildcard patterns (* = one word, # = zero or more words).

Routing keys cycled: kern.critical → kern.info → cron.info → auth.critical → auth.warning

Env vars:
  RABBITMQ_HOSTS             comma-separated broker IPs/hostnames
  RABBITMQ_USER              AMQP username
  RABBITMQ_PASS              AMQP password
  EXCHANGE_NAME              topic exchange name (default: topic_logs)
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
EXCHANGE = os.environ.get("EXCHANGE_NAME", "topic_logs")
INTERVAL = float(os.environ.get("PUBLISH_INTERVAL_SECONDS", "1"))
HOSTNAME = socket.gethostname()

ROUTING_KEYS = ["kern.critical", "kern.info", "cron.info", "auth.critical", "auth.warning"]


def setup(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)


def run() -> None:
    seq = 0
    connection = connect(HOSTS, USER, PASS, role="s4-producer")
    channel = connection.channel()
    setup(channel)

    for routing_key in itertools.cycle(ROUTING_KEYS):
        try:
            seq += 1
            body = json.dumps({
                "seq": seq,
                "producer": HOSTNAME,
                "ts": datetime.now(timezone.utc).isoformat(),
                "key": routing_key,
                "msg": f"[{routing_key}] Event #{seq}",
            })
            channel.basic_publish(
                exchange=EXCHANGE,
                routing_key=routing_key,
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=pika.DeliveryMode.Persistent,
                ),
            )
            print(f"[s4-producer] sent #{seq} key={routing_key}", flush=True)
            time.sleep(INTERVAL)

        except (
            pika.exceptions.AMQPConnectionError,
            pika.exceptions.AMQPChannelError,
            pika.exceptions.StreamLostError,
        ) as exc:
            print(f"[s4-producer] connection lost: {exc}, reconnecting", flush=True)
            try:
                connection.close()
            except Exception:
                pass
            connection = connect(HOSTS, USER, PASS, role="s4-producer")
            channel = connection.channel()
            setup(channel)


if __name__ == "__main__":
    run()
