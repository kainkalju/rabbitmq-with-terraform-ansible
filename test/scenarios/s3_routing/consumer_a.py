#!/usr/bin/env python3
"""
S3 Routing / Direct Exchange — consumer A.

Binds to routing keys: error, warning.
Receives only messages with severity error or warning.

Env vars:
  RABBITMQ_HOSTS  comma-separated broker IPs/hostnames
  RABBITMQ_USER   AMQP username
  RABBITMQ_PASS   AMQP password
  EXCHANGE_NAME   direct exchange name (default: direct_logs)
"""

import json
import os
import socket

import pika

from common.connection import connect

HOSTS = os.environ["RABBITMQ_HOSTS"].split(",")
USER = os.environ["RABBITMQ_USER"]
PASS = os.environ["RABBITMQ_PASS"]
EXCHANGE = os.environ.get("EXCHANGE_NAME", "direct_logs")
HOSTNAME = socket.gethostname()

BINDING_KEYS = ["error", "warning"]


def on_message(
    ch: pika.adapters.blocking_connection.BlockingChannel,
    method: pika.spec.Basic.Deliver,
    _properties: pika.spec.BasicProperties,
    body: bytes,
) -> None:
    try:
        data = json.loads(body)
        print(
            f"[s3-consumer-A/{HOSTNAME}] received #{data.get('seq')}"
            f" level={data.get('level')}"
            f" msg='{data.get('msg')}'"
            f" ts={data.get('ts')}",
            flush=True,
        )
    except json.JSONDecodeError:
        print(f"[s3-consumer-A/{HOSTNAME}] received non-JSON: {body!r}", flush=True)
    ch.basic_ack(delivery_tag=method.delivery_tag)


def run() -> None:
    while True:
        connection = connect(HOSTS, USER, PASS, role=f"s3-consumer-A/{HOSTNAME}")
        try:
            channel = connection.channel()
            channel.exchange_declare(exchange=EXCHANGE, exchange_type="direct", durable=True)
            result = channel.queue_declare(queue="", exclusive=True)
            queue_name = result.method.queue
            for key in BINDING_KEYS:
                channel.queue_bind(exchange=EXCHANGE, queue=queue_name, routing_key=key)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=queue_name, on_message_callback=on_message, auto_ack=False)
            print(
                f"[s3-consumer-A/{HOSTNAME}] bound to {EXCHANGE}"
                f" keys={BINDING_KEYS}, waiting for messages",
                flush=True,
            )
            channel.start_consuming()
        except (
            pika.exceptions.AMQPConnectionError,
            pika.exceptions.AMQPChannelError,
            pika.exceptions.StreamLostError,
        ) as exc:
            print(
                f"[s3-consumer-A/{HOSTNAME}] connection lost: {exc}, reconnecting",
                flush=True,
            )
            try:
                connection.close()
            except Exception:
                pass


if __name__ == "__main__":
    run()
