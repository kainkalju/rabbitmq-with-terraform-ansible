# RabbitMQ Test Setup

End-to-end test harness for the 3-node RabbitMQ 4.2.5 cluster. Provisions a
dedicated EC2 Spot test client (Terraform), configures Docker via Ansible, and runs
Python producer/consumer services in Docker Compose.

Two stacks run independently on the test client:

| Stack | systemd service | What it tests |
|---|---|---|
| Basic producer/consumer | `docker-compose@rabbitmq-test` | Durable named queue, manual ack, multi-host failover |
| Scenarios | `docker-compose@rabbitmq-test-scenarios` | Work Queues, PubSub, Routing, Topics |

## Architecture

```
test/
├── terraform/      AWS EC2 t4g.small Spot (arm64, Ubuntu 24.04) — eu-north-1a
├── ansible/        Docker CE + syslog + rabbitmq-test role → Docker Compose
├── producer/       Python 3.12 — publishes JSON messages continuously
├── consumer/       Python 3.12 — consumes with manual ack, prefetch=1
├── scenarios/      Python 3.12 — four messaging pattern scenarios
│   ├── common/         Shared multi-host failover connection helper
│   ├── s1_work_queues/ Work queues — competing workers, fair dispatch
│   ├── s2_pubsub/      Publish/subscribe — fanout exchange, temp queues
│   ├── s3_routing/     Routing — direct exchange, multiple bindings
│   └── s4_topics/      Topics — wildcard routing key patterns
└── scripts/        gen_inventory.py — merges test + cluster TF outputs
```

The test client is added to the existing `rabbitmq` self-referencing security
group, granting port 5672 access to all three cluster nodes without any new
ingress rules.

## Usage

> **Before you apply:** `terraform/variables.tf` contains a `vpc_id` and `subnet_id`
> specific to the author's AWS account. Update these before running Terraform.
> Security groups (`ssh-enabled`, `from-home`, `ping`, `rabbitmq`) and the
> `rabbitmq-key` key pair are looked up by name at runtime — they must exist in
> the target account (i.e. the cluster Terraform in `../terraform` must have been
> applied first).

### 1. Provision

```bash
cd test/terraform
terraform init
terraform apply
```

### 2. Generate inventory

```bash
cd test
terraform -chdir=terraform output -json | \
    python3 scripts/gen_inventory.py --rabbitmq-tf-dir ../terraform \
    > ansible/inventory/hosts.yml
```

### 3. Deploy

```bash
cd test/ansible
ansible-playbook site.yml \
    -i inventory/hosts.yml \
    --vault-password-file ~/.vault_pass
```

Both stacks (`rabbitmq-test` and `rabbitmq-test-scenarios`) are deployed and
started by the same playbook run.

## Verify

### Basic stack

```bash
ssh -i ~/.ssh/rabbitmq_ed25519 ubuntu@<public_ip>

sudo systemctl status docker-compose@rabbitmq-test
sudo docker compose -f /etc/docker/compose/rabbitmq-test/docker-compose.yml ps
sudo docker compose -f /etc/docker/compose/rabbitmq-test/docker-compose.yml logs -f
```

Expected output:
```
[producer] sent #1
[producer] sent #2
[consumer] received seq=1 from=<hostname> ts=1743771234.123
```

### Scenarios stack

```bash
sudo systemctl status docker-compose@rabbitmq-test-scenarios
sudo docker compose -f /etc/docker/compose/rabbitmq-test-scenarios/docker-compose.yml ps

# Follow a specific scenario
sudo docker compose -f /etc/docker/compose/rabbitmq-test-scenarios/docker-compose.yml \
    logs -f s1-producer s1-worker-1 s1-worker-2 s1-worker-3

# Follow all topic consumers to verify wildcard routing
sudo docker compose -f /etc/docker/compose/rabbitmq-test-scenarios/docker-compose.yml \
    logs -f s4-producer s4-consumer-a s4-consumer-b s4-consumer-c
```

See [scenarios/README.md](scenarios/README.md) for per-scenario verification details.

## Failover Test

Stop one cluster node and confirm the apps reconnect automatically:

```bash
# On a RabbitMQ node
sudo docker compose -f /etc/docker/compose/rabbitmq/docker-compose.yml stop

# Watch the test client logs — reconnect within ~5–10s
```

## Design Notes

- **Spot instance** — persistent, hibernate on interruption, max price `$0.0172/h`; encrypted EBS required for hibernate
- **AMI** — resolved at runtime via `data "aws_ami"` (latest Ubuntu 24.04 LTS arm64 from Canonical)
- **Security groups** — all four resolved at runtime via `data "aws_security_group"` by name
- **pika 1.3.2** — uses `auto_ack=False`, `on_message_callback=`, `pika.DeliveryMode.Persistent`
- **Multi-host failover** — `RABBITMQ_HOSTS` is a comma-separated list; apps cycle through on reconnect
- **Durable queue** — survives broker restarts (named queues in S1 and basic stack)
- **Temporary queues** — exclusive, server-named, re-created on every reconnect (S2, S3, S4)
- **prefetch_count=1** — prevents consumers/workers from buffering messages locally
- **Docker/syslog roles** — symlinked from `../../ansible/roles/`
- **Separate Terraform state** — fully isolated from cluster state
