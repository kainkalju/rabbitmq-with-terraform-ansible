# Terraform — What `apply` Creates

> **Before you apply:** the default values in `variables.tf` contain AWS resource IDs
> (`vpc_id`, `nodes` subnet IDs) that are specific to the author's AWS account.
> They do not exist in any other account. Edit `variables.tf` with your own VPC and
> subnet IDs before running any Terraform commands.
>
> Variables that must be updated:
> - `vpc_id` — your VPC ID
> - `nodes` — one subnet ID per AZ, within that VPC
>
> Security groups are looked up by name (`ssh-enabled`, `from-home`, `ping`) using data
> sources in `data.tf`. These groups must exist in the target VPC before applying.

Five resources total: 1 security group + 4 ingress/egress rules (counted separately by Terraform) + 1 key pair + 3 EC2 instances.

```
terraform init
terraform plan   # should show 10 resources to add
terraform apply
```

---

## Resources

### `aws_key_pair.rabbitmq` — SSH key pair

Uploads `~/.ssh/rabbitmq_ed25519.pub` to AWS as key pair named `rabbitmq-key`.
Used by all three EC2 instances.

---

### `aws_security_group.rabbitmq` — inter-node SG

New security group named `rabbitmq` in the existing default VPC. Purpose: allow
RabbitMQ cluster traffic between the three nodes only — all ingress rules are
**self-referencing** (source = this SG itself).

```
Ingress (self-referencing — nodes only)
├── TCP 4369          Erlang epmd — node discovery
├── TCP 5672          AMQP inter-node messaging
├── TCP 25672         Erlang distribution (inter-node RPC)
└── TCP 35672–35682   CLI tools

Egress
└── all traffic, 0.0.0.0/0
```

Client access (AMQP 5672, management UI 15672) is not opened here — it is already
covered by the pre-existing `from-home` SG attached to each instance.

---

### `aws_instance.rabbitmq` × 3 — EC2 instances

Three instances created via `for_each` over the `nodes` map. One per availability zone.

```
rabbitmq-1   eu-north-1a   subnet-01c51fde23794b3af   seed node
rabbitmq-2   eu-north-1b   subnet-0103f2f2ecf770362   joins rabbitmq-1
rabbitmq-3   eu-north-1c   subnet-02ec638de5f418bf7   joins rabbitmq-1
```

| Property | Value |
|---|---|
| AMI | Latest Ubuntu 24.04 LTS arm64 published by Canonical — resolved at plan time via `data.aws_ami.ubuntu` |
| Instance type | `t4g.medium` — 2 vCPU, 4 GiB RAM, ARM64/Graviton3 |
| Root volume | 20 GiB gp3, encrypted, deleted on termination |
| Public IP | Assigned (MapPublicIpOnLaunch — default VPC subnets) |
| Key pair | `rabbitmq-key` (from `~/.ssh/rabbitmq_ed25519.pub`) |
| IAM profile | `AmazonSSMManagedInstanceProfile` — enables SSM Session Manager |

Each instance attaches four security groups:

| SG | Origin | Purpose |
|---|---|---|
| `ssh-enabled` | pre-existing | SSH port 22 from trusted IPs |
| `from-home` | pre-existing | All traffic from home/office — covers AMQP + management UI |
| `ping` | pre-existing | ICMP from anywhere |
| `rabbitmq` | created here | Inter-node cluster ports (self-ref) |

Tags: `Name=rabbitmq-N`, `Role=rabbitmq`, `Cluster=rabbitmq-cluster`.

---

## What is NOT created

Terraform reuses the existing default VPC — no new VPC, subnets, internet gateway,
or route tables are provisioned. The three pre-existing security groups (`ssh-enabled`,
`from-home`, `ping`) are looked up by name via data sources and not modified.

---

## Outputs

After `apply`, three outputs are available:

| Output | Description |
|---|---|
| `public_ips` | Map of node name → public IP |
| `private_ips` | Map of node name → private IP (used for Erlang clustering) |
| `instance_ids` | Map of node name → EC2 instance ID |

These are consumed by `scripts/gen_inventory.py` to build the Ansible inventory:

```bash
terraform output -json | python3 ../scripts/gen_inventory.py > ../ansible/inventory/hosts.yml
terraform output -json | python3 ../scripts/gen_pssh_hosts.py > ../pssh_hosts
```

---

## State

Local backend (`terraform.tfstate`). Upgrade to S3 + DynamoDB for shared/team use.

The AMI is resolved dynamically at plan time — no manual ID lookup needed.

## Teardown

```bash
terraform destroy
```

Destroys all 10 resources. The three pre-existing security groups and the default VPC
are not touched.
