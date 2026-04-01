# Implementation Phases — RabbitMQ 3-Node Cluster

## Tracking Legend
- `[ ]` — pending
- `[~]` — in progress
- `[x]` — done
- `[!]` — blocked / needs attention

---

## Phase 1 — Terraform Infrastructure

**Goal:** Provision 3 EC2 instances (t4g.medium, arm64, Ubuntu 24.04 LTS) across 3 AZs in eu-north-1.

| # | File | Status | Notes |
|---|------|--------|-------|
| 1.1 | `terraform/main.tf` | `[x]` | Provider + local backend |
| 1.2 | `terraform/variables.tf` | `[x]` | Region, AMI, VPC/subnet IDs, key path |
| 1.3 | `terraform/security_groups.tf` | `[x]` | New `rabbitmq` SG (inter-node self-ref) |
| 1.4 | `terraform/key_pair.tf` | `[x]` | AWS key pair from `~/.ssh/rabbitmq_ed25519.pub` |
| 1.5 | `terraform/ec2.tf` | `[x]` | 3x EC2 via for_each, 1 per AZ |
| 1.6 | `terraform/outputs.tf` | `[x]` | Public IPs, private IPs, instance IDs |

**Validation checkpoints:**
- `terraform init` succeeds
- `terraform plan` shows 5 resources to create (SG + key pair + 3x EC2)
- `terraform apply` completes, all 3 instances reach `running` state
- SSH reachable on all 3 public IPs

---

## Phase 2 — Ansible: Docker Role

**Goal:** Install Docker CE + Docker Compose v2 plugin, configure systemd template.

| # | File | Status | Notes |
|---|------|--------|-------|
| 2.1 | `ansible/roles/docker/tasks/main.yml` | `[x]` | Install Docker, add GPG key, apt repo |
| 2.2 | `ansible/roles/docker/files/docker-compose@.service` | `[x]` | Systemd template for compose projects |
| 2.3 | `ansible/roles/docker/handlers/main.yml` | `[x]` | Restart docker handler |

**Note:** `daemon.json` is owned by the `docker-syslog` role (Phase 2b) — docker role no longer touches it.

**Validation checkpoints:**
- `docker --version` shows Docker CE 25+
- `docker compose version` shows v2 plugin
- `ubuntu` user in `docker` group
- `systemctl status docker` → active

---

## Phase 2b — Ansible: Docker-Syslog Role

**Goal:** Route all Docker container logs through rsyslog to `/var/log/docker/<name>.log` with hourly rotation.

| # | File | Status | Notes |
|---|------|--------|-------|
| 2b.1 | `ansible/roles/docker-syslog/tasks/main.yml` | `[x]` | rsyslog config, socket, daemon.json, logrotate |
| 2b.2 | `ansible/roles/docker-syslog/handlers/main.yml` | `[x]` | Restart docker, rsyslog, reload systemd |
| 2b.3 | `ansible/roles/docker-syslog/files/rsyslog.conf` | `[x]` | Overrides system rsyslog.conf |
| 2b.4 | `ansible/roles/docker-syslog/files/10-socket-for-containers.conf` | `[x]` | Unix socket at `/run/docker/dev-log` |
| 2b.5 | `ansible/roles/docker-syslog/files/20-docker.conf` | `[x]` | Routes container logs to per-name files |
| 2b.6 | `ansible/roles/docker-syslog/files/docker-dev-log.socket` | `[x]` | systemd socket unit activating rsyslog |
| 2b.7 | `ansible/roles/docker-syslog/files/daemon.json` | `[x]` | Docker: syslog driver → `unixgram:///run/docker/dev-log` |
| 2b.8 | `ansible/roles/docker-syslog/files/logrotate/rsyslog-docker` | `[x]` | Rotate 8x, hourly, 10MB min, compress |
| 2b.9 | `ansible/roles/docker-syslog/files/logrotate/logrotate.timer` | `[x]` | systemd timer: hourly, 10m accuracy |

**How it works:**
- Docker daemon sends logs via syslog driver to Unix datagram socket `/run/docker/dev-log`
- `docker-dev-log.socket` (systemd) listens on that socket, activates `rsyslog.service`
- rsyslog routes `docker/<container-name>` tagged messages → `/var/log/docker/<name>.log`
- logrotate runs hourly, rotates at 10 MB, keeps 8 compressed generations

**Validation checkpoints:**
- `systemctl status docker-dev-log.socket` → active (listening)
- `ls /var/log/docker/` → `rabbitmq.log` (and `docker.log`) after RabbitMQ starts
- `tail -f /var/log/docker/rabbitmq.log` shows RabbitMQ output
- `systemctl list-timers logrotate.timer` → shows next hourly run

---

## Phase 3 — Ansible: RabbitMQ Role

**Goal:** Deploy RabbitMQ 4.2.5 via Docker Compose, managed by systemd.

| # | File | Status | Notes |
|---|------|--------|-------|
| 3.1 | `ansible/roles/rabbitmq/tasks/main.yml` | `[x]` | Deploy compose file, enable service, cluster join |
| 3.2 | `ansible/roles/rabbitmq/templates/docker-compose.yml.j2` | `[x]` | RabbitMQ compose with extra_hosts, cookie, hostname |
| 3.3 | `ansible/roles/rabbitmq/files/rabbitmq.conf` | `[x]` | Peer discovery, credentials, memory watermark |

**Validation checkpoints:**
- `systemctl status docker-compose@rabbitmq` → active on all 3 nodes
- `docker ps` shows `rabbitmq` container running
- Port 5672 listening on all nodes
- Management UI accessible on port 15672

---

## Phase 4 — Ansible: Cluster Formation

**Goal:** Join rabbitmq-2 and rabbitmq-3 into the cluster seeded by rabbitmq-1.

| # | Task | Status | Notes |
|---|------|--------|-------|
| 4.1 | Cluster join tasks in rabbitmq role | `[x]` | stop_app → reset → join_cluster → start_app |
| 4.2 | Erlang cookie shared across all nodes | `[x]` | Via Ansible vault + compose template |
| 4.3 | `extra_hosts` maps private IPs in compose | `[x]` | Erlang clustering uses hostnames |

**Validation checkpoints:**
- `rabbitmqctl cluster_status` on any node shows all 3 nodes as `running`
- All nodes show same cluster name
- No `partitioned` nodes

---

## Phase 5 — Ansible: Inventory + Vault + Master Playbook

**Goal:** Wire everything together — inventory, vault, site.yml.

| # | File | Status | Notes |
|---|------|--------|-------|
| 5.1 | `ansible/inventory/hosts.yml` | `[x]` | Placeholder — populated via gen_inventory.py |
| 5.2 | `ansible/group_vars/all/vault.yml` | `[x]` | Vault-encrypted: erlang_cookie, user, password |
| 5.3 | `ansible/group_vars/all/vars.yml` | `[x]` | Non-secret defaults |
| 5.4 | `ansible/site.yml` | `[x]` | Master playbook ordering docker → rabbitmq → join |
| 5.5 | `scripts/gen_inventory.py` | `[x]` | Converts terraform output JSON → hosts.yml |

**Validation checkpoints:**
- `ansible-playbook --syntax-check site.yml` passes
- `ansible all -m ping` reaches all 3 hosts
- Vault decrypts with the password

---

## Phase 6 — End-to-End Deployment

**Goal:** Full deployment run from zero, cluster verified.

| # | Step | Status | Notes |
|---|------|--------|-------|
| 6.1 | `terraform apply` | `[ ]` | Needs real AWS credentials + apply |
| 6.2 | `gen_inventory.py` populates hosts.yml | `[ ]` | After apply |
| 6.3 | `ansible-playbook site.yml` | `[ ]` | Full run |
| 6.4 | Cluster status verification | `[ ]` | 3 nodes running, no partitions |
| 6.5 | Management UI accessible | `[ ]` | Port 15672 reachable from home/office |

---

## Known Risks / Watch Points

| Risk | Mitigation |
|------|-----------|
| AMI ID may change — must be Ubuntu 24.04 LTS arm64 in eu-north-1 | Confirm with `aws ec2 describe-images` before apply |
| Erlang cookie mismatch → nodes won't cluster | Set once in vault, never change without full reset |
| `from-home` SG must cover current home IP | Verify before SSH attempts |
| `rabbitmq:4.2.5-management` image must be arm64v8 compatible | Confirmed: official image is multi-arch |
| `join_cluster` is not idempotent — re-running site.yml will reset nodes | Add guard: skip if already in cluster |
| Docker Compose v2 (`docker compose`) vs v1 (`docker-compose`) | systemd unit must use `docker compose`, not `docker-compose` |

---

## Decision Log

| Date | Decision | Reason |
|------|----------|--------|
| 2026-04-01 | Use `rabbitmq:4.2.5-management` image | Latest stable 4.x with management UI; multi-arch |
| 2026-04-01 | Cluster join via `rabbitmqctl` (manual) | Simpler than peer discovery plugin; explicit |
| 2026-04-01 | Local Terraform state | Starting simple; upgrade to S3 when needed |
| 2026-04-01 | `from-home` SG for client access | Existing pattern in account; avoids new rules |
