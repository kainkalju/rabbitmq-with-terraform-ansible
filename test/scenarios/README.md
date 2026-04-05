# RabbitMQ Scenarios

Four messaging patterns built on [pika 1.3.2](https://pika.readthedocs.io/), each
containerized and deployed as part of the `docker-compose@rabbitmq-test-scenarios`
systemd service.

All producers emit periodic JSON messages with ISO 8601 timestamps. All consumers
use manual ack and `prefetch_count=1`. The shared connection helper in `common/`
implements multi-host failover with automatic reconnection.

## Scenarios

### S1 — Work Queues

Exchange: default `""` · Queue: `work.tasks` (durable, named)

```
producer ──► work.tasks ──► worker-1
                        ──► worker-2   (competing consumers, fair dispatch)
                        ──► worker-3
```

The producer sends task messages containing a string of 1–5 dots. Each worker
sleeps one second per dot, simulating variable-length work. With `prefetch_count=1`
the broker only dispatches the next task after the worker acknowledges the current
one — no worker is overloaded while others idle.

Message: `{"seq": N, "producer": hostname, "ts": "...", "task": "..."}`

**Verify:** each sequence number appears in exactly one worker's log.

---

### S2 — Publish/Subscribe

Exchange: `logs` (fanout, durable) · Queues: exclusive temp (one per consumer)

```
producer ──► logs (fanout) ──► [temp-q-1] ──► consumer-1
                           ──► [temp-q-2] ──► consumer-2
```

Every consumer receives every message. Each consumer creates its own exclusive
temporary queue on connect and binds it to the fanout exchange. The queue is
destroyed when the connection closes; a new one is created on reconnect.

Message: `{"seq": N, "producer": hostname, "ts": "...", "log": "Log entry #N"}`

**Verify:** both consumers log identical sequence numbers.

---

### S3 — Routing (Direct Exchange)

Exchange: `direct_logs` (direct, durable) · Queues: exclusive temp per consumer

```
producer ──[error]──► [temp-q-A] ──► consumer-A  (error + warning)
         ──[warning]─►
         ──[info]───► [temp-q-B] ──► consumer-B  (info only)
```

The producer cycles through routing keys `error → warning → info`. Consumer A binds
to `error` and `warning`; consumer B binds to `info` only. The two binding sets are
non-overlapping — together they cover all messages exactly once.

Message: `{"seq": N, "producer": hostname, "ts": "...", "level": "...", "msg": "..."}`

**Verify:** consumer A never logs `level=info`; consumer B never logs `level=error` or `level=warning`.

---

### S4 — Topics

Exchange: `topic_logs` (topic, durable) · Queues: exclusive temp per consumer

```
Producer routing keys:   kern.critical  kern.info  cron.info  auth.critical  auth.warning

consumer-A  *.critical   ──► kern.critical, auth.critical
consumer-B  kern.*       ──► kern.critical, kern.info
consumer-C  #            ──► all five keys
```

`kern.critical` is delivered to all three consumers simultaneously.
`cron.info` and `auth.warning` reach only consumer C.

Message: `{"seq": N, "producer": hostname, "ts": "...", "key": "...", "msg": "..."}`

**Verify:**
- Consumer A receives only `kern.critical` and `auth.critical`
- Consumer B receives only `kern.critical` and `kern.info`
- Consumer C receives all five keys

## Directory Structure

```
scenarios/
├── common/
│   ├── __init__.py
│   └── connection.py       Shared multi-host failover (connect, make_params)
├── s1_work_queues/
│   ├── producer.py
│   ├── worker.py
│   ├── requirements.txt
│   └── Dockerfile
├── s2_pubsub/
│   ├── producer.py
│   ├── consumer.py
│   ├── requirements.txt
│   └── Dockerfile
├── s3_routing/
│   ├── producer.py
│   ├── consumer_a.py       Binds: error, warning
│   ├── consumer_b.py       Binds: info
│   ├── requirements.txt
│   └── Dockerfile
└── s4_topics/
    ├── producer.py
    ├── consumer_a.py       Pattern: *.critical
    ├── consumer_b.py       Pattern: kern.*
    ├── consumer_c.py       Pattern: #
    ├── requirements.txt
    └── Dockerfile
```

## Running Locally

```bash
export RABBITMQ_HOSTS="host1,host2,host3"
export RABBITMQ_USER="..."
export RABBITMQ_PASS="..."

docker compose -f ../docker-compose.scenarios.yml up --build
```

Follow a single scenario:

```bash
docker compose -f ../docker-compose.scenarios.yml logs -f \
    s4-producer s4-consumer-a s4-consumer-b s4-consumer-c
```

## Deployment

Deployed by the `rabbitmq-test` Ansible role alongside the basic producer/consumer
stack. Source is synced to `/etc/docker/compose/rabbitmq-test-scenarios/scenarios/`
and credentials are injected from vault via Jinja2 template.

```bash
cd ansible
ansible-playbook site.yml -i inventory/hosts.yml --vault-password-file ~/.vault_pass
```
