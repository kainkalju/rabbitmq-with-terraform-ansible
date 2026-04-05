# RabbitMQ Producer/Consumer Test Setup

End-to-end test harness for the 3-node RabbitMQ 4.2.5 cluster. Provisions a
dedicated EC2 Spot test client (Terraform), configures Docker via Ansible, and runs
Python producer/consumer services in Docker Compose.

## Architecture

```
test/
├── terraform/      AWS EC2 t4g.small Spot (arm64, Ubuntu 24.04) — eu-north-1a
├── ansible/        Docker CE + syslog + rabbitmq-test role → Docker Compose
├── producer/       Python 3.12 — publishes JSON messages continuously
├── consumer/       Python 3.12 — consumes with manual ack, prefetch=1
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

## Verify

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
- **Durable queue** — survives broker restarts
- **prefetch_count=1** — prevents consumer from buffering all messages locally
- **Docker/syslog roles** — symlinked from `../../ansible/roles/`
- **Separate Terraform state** — fully isolated from cluster state
