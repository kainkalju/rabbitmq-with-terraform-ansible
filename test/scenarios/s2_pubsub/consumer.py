#!/usr/bin/env python3
"""
S2 Publish/Subscribe — consumer.

Creates an exclusive temporary queue and binds it to the fanout exchange.
Receives every message the producer broadcasts. The temp queue is destroyed
when this connection closes, so a new one is created on every reconnect.

Env vars:
  RABBITMQ_HOSTS  comma-separated broker IPs/hostnames
  RABBITMQ_USER   AMQP username
  RABBITMQ_PASS   AMQP password
  EXCHANGE_NAME   fanout exchange name (default: logs)
"""

import json
import os
import socket

import pika

from common.connection import connect

HOSTS = os.environ["RABBITMQ_HOSTS"].split(",")
USER = os.environ["RABBITMQ_USER"]
PASS = os.environ["RABBITMQ_PASS"]
EXCHANGE = os.environ.get("EXCHANGE_NAME", "logs")
HOSTNAME = socket.gethostname()


def on_message(
    ch: pika.adapters.blocking_connection.BlockingChannel,
    method: pika.spec.Basic.Deliver,
    _properties: pika.spec.BasicProperties,
    body: bytes,
) -> None:
    try:
        data = json.loads(body)
        print(
            f"[s2-consumer/{HOSTNAME}] received #{data.get('seq')}"
            f" log='{data.get('log')}'"
            f" from={data.get('producer')}"
            f" ts={data.get('ts')}",
            flush=True,
        )
    except json.JSONDecodeError:
        print(f"[s2-consumer/{HOSTNAME}] received non-JSON: {body!r}", flush=True)
    ch.basic_ack(delivery_tag=method.delivery_tag)


def run() -> None:
    while True:
        connection = connect(HOSTS, USER, PASS, role=f"s2-consumer/{HOSTNAME}")
        try:
            channel = connection.channel()
            # Idempotent — safe if exchange already exists
            channel.exchange_declare(exchange=EXCHANGE, exchange_type="fanout", durable=True)
            # Exclusive temp queue: server assigns a unique name; deleted on disconnect
            result = channel.queue_declare(queue="", exclusive=True)
            queue_name = result.method.queue
            channel.queue_bind(exchange=EXCHANGE, queue=queue_name)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=queue_name, on_message_callback=on_message, auto_ack=False)
            print(
                f"[s2-consumer/{HOSTNAME}] bound to {EXCHANGE} via {queue_name},"
                " waiting for messages",
                flush=True,
            )
            channel.start_consuming()
        except (
            pika.exceptions.AMQPConnectionError,
            pika.exceptions.AMQPChannelError,
            pika.exceptions.StreamLostError,
        ) as exc:
            print(
                f"[s2-consumer/{HOSTNAME}] connection lost: {exc}, reconnecting",
                flush=True,
            )
            try:
                connection.close()
            except Exception:
                pass


if __name__ == "__main__":
    run()
