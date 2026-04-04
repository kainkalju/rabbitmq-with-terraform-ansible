# RabbitMQ Producer/Consumer Test Setup

End-to-end test harness for the 3-node RabbitMQ 4.2.5 cluster. Provisions a
dedicated EC2 test client (Terraform), configures Docker via Ansible, and runs
Python producer/consumer services in Docker Compose.

## Architecture

```
test/
├── terraform/      AWS EC2 t4g.small (arm64, Ubuntu 24.04) — eu-north-1a
├── ansible/        Docker CE + rabbitmq-test role → Docker Compose
├── producer/       Python 3.12 — publishes JSON messages continuously
├── consumer/       Python 3.12 — consumes with manual ack, prefetch=1
└── scripts/        gen_inventory.py — merges test + cluster TF outputs
```

The test client is added to the existing `rabbitmq` self-referencing security
group, granting port 5672 access to all three cluster nodes without any new
ingress rules.

## Usage

> **Before you apply:** the default values in `terraform/variables.tf` contain AWS resource IDs
> (`vpc_id`, `subnet_id`, `sg_*`) that are specific to the author's AWS account.
> They do not exist in any other account. Edit `terraform/variables.tf` with your own VPC, subnet,
> and security group IDs before running any Terraform commands.
>
> Variables that must be updated:
> - `vpc_id` — your VPC ID
> - `subnet_id` — a subnet ID within that VPC (eu-north-1a recommended, same AZ as the seed node)
> - `sg_ssh_enabled`, `sg_from_home`, `sg_ping` — IDs of your existing security groups
>
> Also requires the RabbitMQ cluster Terraform (`../terraform`) to have been applied first —
> the `rabbitmq` security group and `rabbitmq-key` key pair must already exist in AWS.

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

- **pika 1.3.2** — uses `auto_ack=False`, `on_message_callback=`, `pika.DeliveryMode.Persistent`
- **Multi-host failover** — `RABBITMQ_HOSTS` is a comma-separated list; apps cycle through on reconnect
- **Durable queue** — survives broker restarts
- **prefetch_count=1** — prevents consumer from buffering all messages locally
- **Vault symlink** — `ansible/group_vars/all/vault.yml` → `../../ansible/group_vars/all/vault.yml`
- **Docker role symlink** — `ansible/roles/docker` → `../../ansible/roles/docker`
- **Separate Terraform state** — fully isolated from cluster state
