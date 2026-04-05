#!/usr/bin/env python3
"""
S1 Work Queues — worker (competing consumer).

Pulls tasks from a durable named queue. Simulates work by sleeping one second
per dot in the task string. Uses prefetch_count=1 for fair dispatch.

Env vars:
  RABBITMQ_HOSTS  comma-separated broker IPs/hostnames
  RABBITMQ_USER   AMQP username
  RABBITMQ_PASS   AMQP password
  QUEUE_NAME      source queue (default: work.tasks)
"""

import json
import os
import socket
import time

import pika

from common.connection import connect

HOSTS = os.environ["RABBITMQ_HOSTS"].split(",")
USER = os.environ["RABBITMQ_USER"]
PASS = os.environ["RABBITMQ_PASS"]
QUEUE = os.environ.get("QUEUE_NAME", "work.tasks")
HOSTNAME = socket.gethostname()


def on_message(
    ch: pika.adapters.blocking_connection.BlockingChannel,
    method: pika.spec.Basic.Deliver,
    _properties: pika.spec.BasicProperties,
    body: bytes,
) -> None:
    try:
        data = json.loads(body)
        task = data.get("task", "")
        seq = data.get("seq")
        print(
            f"[s1-worker/{HOSTNAME}] received #{seq} task='{task}'"
            f" — working {len(task)}s",
            flush=True,
        )
        time.sleep(len(task))
        print(f"[s1-worker/{HOSTNAME}] done #{seq}", flush=True)
    except json.JSONDecodeError:
        print(f"[s1-worker/{HOSTNAME}] received non-JSON: {body!r}", flush=True)
    ch.basic_ack(delivery_tag=method.delivery_tag)


def run() -> None:
    while True:
        connection = connect(HOSTS, USER, PASS, role=f"s1-worker/{HOSTNAME}")
        try:
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE, on_message_callback=on_message, auto_ack=False)
            print(f"[s1-worker/{HOSTNAME}] waiting for tasks", flush=True)
            channel.start_consuming()
        except (
            pika.exceptions.AMQPConnectionError,
            pika.exceptions.AMQPChannelError,
            pika.exceptions.StreamLostError,
        ) as exc:
            print(f"[s1-worker/{HOSTNAME}] connection lost: {exc}, reconnecting", flush=True)
            try:
                connection.close()
            except Exception:
                pass


if __name__ == "__main__":
    run()
