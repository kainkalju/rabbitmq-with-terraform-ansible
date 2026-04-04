# Ansible Playbook — How It Works

Runs three plays in order against a 3-node RabbitMQ cluster. Each play maps to a role.

```
ansible-playbook -i inventory/hosts.yml site.yml --ask-vault-pass
```

---

## Play order

```
site.yml
├── Play 1 — docker        (all 3 nodes, parallel)
├── Play 2 — docker-syslog (all 3 nodes, parallel)
└── Play 3 — rabbitmq      (serial: 1 — seed first, then nodes)
```

`serial: 1` in Play 3 ensures rabbitmq-1 (the seed) is fully up before rabbitmq-2 and
rabbitmq-3 attempt to join the cluster.

---

## Inventory groups

```
rabbitmq_all
├── rabbitmq_seed
│   └── rabbitmq-1   seed / cluster initiator
└── rabbitmq_nodes
    ├── rabbitmq-2   joins rabbit@rabbitmq-1
    └── rabbitmq-3   joins rabbit@rabbitmq-1
```

All hosts connect as `ubuntu` using `~/.ssh/rabbitmq_ed25519`.
Private IPs (172.31.x.x) are used for inter-node cluster traffic.

---

## Play 1 — `docker` role

Installs Docker CE on all three nodes in parallel.

```
Each node
  ├── apt install: ca-certificates curl gnupg lsb-release
  ├── /etc/apt/keyrings/docker.asc        ← Docker GPG key
  ├── apt repository (arm64/ubuntu/noble)
  ├── apt install: docker-ce docker-ce-cli containerd.io docker-compose-plugin
  ├── /etc/docker/compose/                ← compose projects root
  ├── /etc/systemd/system/docker-compose@.service  ← systemd template unit
  ├── ubuntu added to docker group
  └── docker.service: enabled + started
       └── HANDLER: Restart docker  (if packages changed)
           HANDLER: Reload systemd  (if unit file changed)
```

The `docker-compose@.service` unit is a parameterised template — any service name passed
as `%i` maps to `/etc/docker/compose/%i/` and runs `docker compose up -d`.

---

## Play 2 — `docker-syslog` role

Routes all container stdout/stderr into rsyslog via a Unix datagram socket, then writes
to per-container log files under `/var/log/docker/`.

```
Each node
  ├── /etc/rsyslog.conf                            ← full overwrite (stock Ubuntu default)
  ├── /etc/rsyslog.d/10-socket-for-containers.conf ← imuxsock on /run/docker/dev-log
  ├── /etc/rsyslog.d/20-docker.conf                ← routing rules (see below)
  ├── /lib/systemd/system/docker-dev-log.socket    ← systemd socket unit
  │    └── starts on boot, binds /run/docker/dev-log, backed by rsyslog.service
  ├── /etc/docker/daemon.json                      ← log-driver: syslog → unixgram:///run/docker/dev-log
  ├── /etc/logrotate.d/rsyslog-docker              ← rotate at 10 MB, keep 8, hourly
  ├── mv /etc/cron.daily/logrotate → /etc/cron.hourly/logrotate  (once)
  └── /etc/systemd/system/logrotate.timer          ← OnCalendar=hourly

  HANDLERS (deferred until end of play):
    Restart rsyslog
    Restart docker   (picks up new log-driver from daemon.json)
    Reload systemd
```

### Log routing (20-docker.conf)

```
syslog message arrives on /run/docker/dev-log
│
├── programname == 'dockerd'    → /var/log/docker/docker.log
├── programname == 'containerd' → /var/log/docker/docker.log
└── programname == 'docker'
    └── syslogtag contains 'docker/'
        └── tag format: docker/<container-name>[pid]
            → /var/log/docker/<container-name>.log
                           e.g. /var/log/docker/rabbitmq.log
```

Docker daemon is configured with `"tag": "docker/{{.Name}}"` so each container gets its
own log file automatically.

---

## Play 3 — `rabbitmq` role

Deploys RabbitMQ as a Docker Compose service via systemd. Runs **serial: 1** — seed node
first, then each of the two joining nodes.

```
rabbitmq-1 (seed)                 rabbitmq-2 / rabbitmq-3 (nodes)
─────────────────────────         ──────────────────────────────────────
/etc/hosts ← all 3 private IPs   /etc/hosts ← all 3 private IPs
docker-compose.yml (templated)    docker-compose.yml (templated)
rabbitmq.conf (templated)         rabbitmq.conf (templated)
  └── HANDLER: restart service      └── HANDLER: restart service
docker-compose@rabbitmq: started  docker-compose@rabbitmq: started
wait_for port 5672                wait_for port 5672
                                  rabbitmqctl cluster_status --formatter json
                                    └── already in cluster? → skip join
                                  rabbitmqctl stop_app
                                  rabbitmqctl reset
                                  rabbitmqctl join_cluster rabbit@rabbitmq-1
                                  rabbitmqctl start_app
```

The cluster join guard checks whether `rabbit@rabbitmq-1` already appears in
`running_nodes`. If it does, the stop/reset/join/start sequence is skipped — making
re-runs of the playbook safe.

### docker-compose.yml (per node)

```yaml
services:
  rabbitmq:
    image: rabbitmq:4.2.5-management
    hostname: rabbitmq-N          # injected from inventory_hostname
    network_mode: host            # uses host network — inter-node traffic on private IPs
    environment:
      RABBITMQ_ERLANG_COOKIE: <vault>
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
      - ./rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf:ro
```

`network_mode: host` is required — Erlang distribution (port 25672) and epmd (4369)
must be reachable on the host's private IP for clustering to work.

---

## Secrets (ansible-vault)

`group_vars/all/vault.yml` is encrypted and gitignored. It supplies:

| Variable                  | Used in                        |
|---------------------------|--------------------------------|
| `rabbitmq_erlang_cookie`  | docker-compose.yml.j2 env var  |
| `rabbitmq_user`           | rabbitmq.conf.j2               |
| `rabbitmq_password`       | rabbitmq.conf.j2               |

---

## End-to-end flow

```
Ansible controller (local)
        │
        │ SSH (rabbitmq_ed25519, ubuntu@<public-ip>)
        ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  rabbitmq-1   │   │  rabbitmq-2   │   │  rabbitmq-3   │
│  eu-north-1a  │   │  eu-north-1b  │   │  eu-north-1c  │
│               │   │               │   │               │
│  dockerd      │   │  dockerd      │   │  dockerd      │
│    │          │   │    │          │   │    │          │
│  rabbitmq     │   │  rabbitmq     │   │  rabbitmq     │
│  container    │   │  container    │   │  container    │
│    │  logs    │   │    │  logs    │   │    │  logs    │
│  rsyslog      │   │  rsyslog      │   │  rsyslog      │
│  /var/log/    │   │  /var/log/    │   │  /var/log/    │
│  docker/      │   │  docker/      │   │  docker/      │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                   │                   │
        │←──── Erlang distribution (25672) ─────│
        │←──── epmd (4369) ─────────────────────│
        │←──── AMQP inter-node (5672) ──────────│
        │       private IPs (172.31.x.x / VPC)  │
```

Cluster topology after Play 3 completes:

```
rabbit@rabbitmq-1  ←──── rabbit@rabbitmq-2
        ↑
        └──────────────── rabbit@rabbitmq-3
```

rabbitmq-1 is the seed; rabbitmq-2 and rabbitmq-3 each join it independently.
All three nodes are disc nodes (RabbitMQ default).
