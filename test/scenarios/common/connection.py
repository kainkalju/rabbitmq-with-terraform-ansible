"""
Shared RabbitMQ connection helper — multi-host failover for all scenarios.
"""

import time

import pika


def make_params(host: str, user: str, password: str) -> pika.ConnectionParameters:
    return pika.ConnectionParameters(
        host=host.strip(),
        port=5672,
        credentials=pika.PlainCredentials(user, password),
        heartbeat=60,
        blocked_connection_timeout=300,
        connection_attempts=3,
        retry_delay=2,
    )


def connect(
    hosts: list[str], user: str, password: str, role: str = "service"
) -> pika.BlockingConnection:
    """Cycle through all hosts until one accepts the connection."""
    while True:
        for host in hosts:
            try:
                print(f"[{role}] connecting to {host}...", flush=True)
                conn = pika.BlockingConnection(make_params(host, user, password))
                print(f"[{role}] connected to {host}", flush=True)
                return conn
            except pika.exceptions.AMQPConnectionError as exc:
                print(f"[{role}] {host} unreachable: {exc}", flush=True)
        print(f"[{role}] all hosts unreachable, retrying in 5s", flush=True)
        time.sleep(5)
