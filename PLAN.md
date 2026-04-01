# 3-Node RabbitMQ Cluster on AWS eu-north-1

## Overview

Deploy a 3-node RabbitMQ cluster in AWS eu-north-1 (Stockholm) using:
- **Terraform** — infrastructure provisioning (EC2, Security Group, Key Pair — reusing existing VPC)
- **Ansible** — configuration management (Docker, Docker Compose, RabbitMQ)
- **Docker + Docker Compose** — RabbitMQ runs as a containerized service managed by systemd
- **Architecture** — ARM64 (Graviton3) via t4g.medium instances

---

## Existing AWS Infrastructure

The account already has a **default VPC** in eu-north-1 that will be reused:

| Resource | ID | Value |
|---|---|---|
| VPC | `vpc-0f47c76ebce94dc7b` | `172.31.0.0/16`, default VPC |
| Subnet eu-north-1a | `subnet-01c51fde23794b3af` | `172.31.16.0/20`, public, MapPublicIpOnLaunch |
| Subnet eu-north-1b | `subnet-0103f2f2ecf770362` | `172.31.32.0/20`, public, MapPublicIpOnLaunch |
| Subnet eu-north-1c | `subnet-02ec638de5f418bf7` | `172.31.0.0/20`, public, MapPublicIpOnLaunch |
| Internet Gateway | `igw-00f33307dcf816c02` | Attached, 0.0.0.0/0 routed |

### Existing Security Groups (reuse where applicable)

| Name | ID | Purpose |
|---|---|---|
| `ssh-enabled` | `sg-064d9ecc1338dad4e` | SSH port 22 from specific IPs |
| `from-home` | `sg-0207690533a7d530d` | All traffic from home IPs |
| `From_Office` | `sg-0fafc3f4a85531ee2` | All traffic from office IPs |
| `ping` | `sg-05d597352554aae74` | ICMP from anywhere |
| `default` | `sg-0f894f63905e53a62` | All traffic within group members |

The RabbitMQ instances will attach: `ssh-enabled` + `from-home` + `ping` + a new `rabbitmq` SG for inter-node ports.

---

## Architecture

```
eu-north-1 — Default VPC (172.31.0.0/16)
├── subnet eu-north-1a (172.31.16.0/20) → rabbitmq-1 (EC2 t4g.medium, arm64) — seed node
├── subnet eu-north-1b (172.31.32.0/20) → rabbitmq-2 (EC2 t4g.medium, arm64) — joins rabbitmq-1
└── subnet eu-north-1c (172.31.0.0/20)  → rabbitmq-3 (EC2 t4g.medium, arm64) — joins rabbitmq-1
```

One node per AZ for failure isolation. Nodes communicate over private IPs within the VPC.

---

## Project Structure

```
aws/
├── PLAN.md
├── terraform/
│   ├── main.tf              # Provider, backend config
│   ├── variables.tf         # Region, instance type, AMI, existing resource IDs
│   ├── security_groups.tf   # New rabbitmq SG for inter-node ports only
│   ├── key_pair.tf          # AWS key pair from ~/.ssh/rabbitmq_ed25519.pub
│   ├── ec2.tf               # 3x EC2 instances, one per AZ
│   └── outputs.tf           # Public IPs, private IPs, instance IDs
└── ansible/
    ├── site.yml             # Master playbook
    ├── inventory/
    │   └── hosts.yml        # Generated from Terraform outputs
    └── roles/
        ├── docker/
        │   ├── tasks/
        │   │   └── main.yml         # Docker + docker-compose install
        │   ├── files/
        │   │   ├── docker-compose@.service  # Systemd template
        │   │   └── daemon.json              # Docker daemon config
        │   └── handlers/
        │       └── main.yml         # Restart docker
        └── rabbitmq/
            ├── tasks/
            │   └── main.yml         # Deploy compose file, enable service, cluster join
            ├── templates/
            │   └── docker-compose.yml.j2    # RabbitMQ compose template
            └── files/
                └── rabbitmq.conf    # RabbitMQ base configuration
```

---

## Terraform Plan

### Provider & Backend (`main.tf`)
- AWS provider, region: `eu-north-1`
- Local state (can be upgraded to S3 backend)

### Variables (`variables.tf`)
| Variable | Default | Description |
|---|---|---|
| `region` | `eu-north-1` | AWS region |
| `instance_type` | `t4g.medium` | EC2 instance type (ARM64/Graviton3) |
| `ami_id` | Ubuntu 24.04 LTS arm64 (eu-north-1) | AMI ID — must be arm64 variant |
| `vpc_id` | `vpc-0f47c76ebce94dc7b` | Existing default VPC |
| `subnet_ids` | `[subnet-01c51fde23794b3af, subnet-0103f2f2ecf770362, subnet-02ec638de5f418bf7]` | One per AZ |
| `ssh_public_key_path` | `~/.ssh/rabbitmq_ed25519.pub` | Path to public key |

### Networking
No new VPC/subnet/IGW/route table resources — the existing default VPC is fully routed to the internet. Terraform will use `data` sources to reference existing resources by ID.

### Security Group (`security_groups.tf`)
Create one new SG: `rabbitmq` — inter-node ports only (self-referencing ingress):

| Port | Protocol | Source | Purpose |
|---|---|---|---|
| 4369 | TCP | SG self-ref | Erlang epmd (inter-node) |
| 5672 | TCP | SG self-ref | AMQP between nodes |
| 25672 | TCP | SG self-ref | Erlang distribution (inter-node) |
| 35672-35682 | TCP | SG self-ref | CLI tools (inter-node) |

Client access (AMQP 5672, Management UI 15672) is covered by `from-home` and `From_Office` SGs which allow all traffic from trusted IPs. Egress: all traffic allowed.

Each EC2 instance attaches all of: `ssh-enabled`, `from-home`, `ping`, `rabbitmq` (new).

### Key Pair (`key_pair.tf`)
- Reads `~/.ssh/rabbitmq_ed25519.pub`
- Creates AWS key pair `rabbitmq-key`

### EC2 Instances (`ec2.tf`)
- 3 instances using `for_each` over a map of `{name → subnet_id}`
- Named: `rabbitmq-1` (eu-north-1a), `rabbitmq-2` (eu-north-1b), `rabbitmq-3` (eu-north-1c)
- One node per AZ for failure isolation
- Ubuntu 24.04 LTS **arm64**
- Instance type: `t4g.medium` (2 vCPU, 4 GiB RAM, ARM64/Graviton3)
- 20 GiB gp3 root volume
- Security groups: `ssh-enabled` + `from-home` + `ping` + new `rabbitmq` SG
- Tagged with `Name`, `Role=rabbitmq`, `Cluster=rabbitmq-cluster`

### Outputs (`outputs.tf`)
- Public IPs of all 3 nodes
- Private IPs of all 3 nodes (used for RabbitMQ clustering)
- Instance IDs

---

## Ansible Plan

### Inventory (`inventory/hosts.yml`)
Generated manually (or via script) from `terraform output`. Groups:
- `rabbitmq_seed` — rabbitmq-1 (cluster seed node)
- `rabbitmq_nodes` — rabbitmq-2, rabbitmq-3 (join the seed)
- `rabbitmq_all` — all 3 nodes (children of both groups)

Connection settings: `ansible_user: ubuntu`, `ansible_ssh_private_key_file: ~/.ssh/rabbitmq_ed25519`

### Master Playbook (`site.yml`)
Runs roles in order:
1. `docker` role on all nodes (installs Docker + docker-compose + systemd service)
2. `rabbitmq` role on all nodes (deploys compose file, starts service)
3. Cluster join tasks on `rabbitmq_nodes` (rabbitmq-2, rabbitmq-3 join rabbitmq-1)

### Role: `docker`

1. Install prerequisites: `ca-certificates`, `curl`, `gnupg`, `lsb-release`
2. Add Docker's official GPG key and apt repository (arm64 variant)
3. Install `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-compose-plugin`
4. Install `docker-compose@.service` systemd template to `/etc/systemd/system/`
5. Create `/etc/docker/compose/` directory
6. Copy `daemon.json` to `/etc/docker/daemon.json`
7. Add `ubuntu` user to `docker` group
8. Enable and start `docker` service
9. Flush handlers (restart docker if config changed)

Note: Docker Compose v2 is installed as a plugin (`docker compose`), not a standalone binary. The systemd template invokes `docker compose` accordingly.

### Role: `rabbitmq`

1. Create `/etc/docker/compose/rabbitmq/` directory
2. Template `docker-compose.yml.j2` → `/etc/docker/compose/rabbitmq/docker-compose.yml`
3. Copy `rabbitmq.conf` to `/etc/docker/compose/rabbitmq/rabbitmq.conf`
4. Enable and start `docker-compose@rabbitmq` systemd service
5. Wait for RabbitMQ to be healthy (port 5672 listening)
6. **Cluster join** (on `rabbitmq_nodes` only):
   - `rabbitmqctl stop_app`
   - `rabbitmqctl reset`
   - `rabbitmqctl join_cluster rabbit@rabbitmq-1` (using private IP hostname)
   - `rabbitmqctl start_app`

### Docker Compose Template (`docker-compose.yml.j2`)

```yaml
services:
  rabbitmq:
    image: rabbitmq:4.2.5-management
    hostname: "{{ inventory_hostname }}"
    container_name: rabbitmq
    restart: unless-stopped
    environment:
      RABBITMQ_ERLANG_COOKIE: "{{ rabbitmq_erlang_cookie }}"
    ports:
      - "4369:4369"
      - "5672:5672"
      - "15672:15672"
      - "25672:25672"
      - "35672-35682:35672-35682"
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
      - ./rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf:ro
    extra_hosts:
      - "rabbitmq-1:{{ hostvars['rabbitmq-1'].ansible_host }}"
      - "rabbitmq-2:{{ hostvars['rabbitmq-2'].ansible_host }}"
      - "rabbitmq-3:{{ hostvars['rabbitmq-3'].ansible_host }}"
volumes:
  rabbitmq_data:
```

Key points:
- Image: `rabbitmq:4.2.5-management` — official image, v4.2.x stable, includes management UI; supports arm64v8 natively
- `hostname` set to `inventory_hostname` so RabbitMQ node names are consistent (`rabbit@rabbitmq-1`, etc.)
- `extra_hosts` maps all node names to private IPs so Erlang clustering works across containers
- Shared `RABBITMQ_ERLANG_COOKIE` (stored in Ansible vault) is required for clustering
- As of RabbitMQ 3.9+, `RABBITMQ_DEFAULT_USER`/`RABBITMQ_DEFAULT_PASS` env vars are deprecated — credentials are set via `rabbitmq.conf` instead
- `rabbitmq.conf` configures credentials, `cluster_formation.peer_discovery_backend = rabbit_peer_discovery_classic_config`, and any memory tuning

### Ansible Vault
Sensitive values stored in `ansible/group_vars/all/vault.yml` (encrypted):
- `rabbitmq_erlang_cookie`
- `rabbitmq_user`
- `rabbitmq_password`

---

## Deployment Steps

```bash
# 1. Provision infrastructure
cd terraform/
terraform init
terraform plan
terraform apply

# 2. Populate Ansible inventory from Terraform outputs
terraform output -json | python3 ../scripts/gen_inventory.py > ../ansible/inventory/hosts.yml

# 3. Configure all nodes
cd ../ansible/
ansible-playbook -i inventory/hosts.yml site.yml --ask-vault-pass

# 4. Verify cluster
ansible rabbitmq_all -i inventory/hosts.yml -m shell \
  -a "docker exec rabbitmq rabbitmqctl cluster_status"
```

---

## Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Instance type | t4g.medium | ARM64/Graviton3; better price-performance than t3; 2 vCPU / 4 GiB |
| Architecture | arm64 | Graviton3; requires arm64 AMI and arm64-compatible Docker images |
| Ubuntu version | 24.04 LTS arm64 | LTS stability; arm64 variant required for Graviton |
| Docker Compose version | v2 (plugin) | Ships with Docker CE; replaces standalone v1 binary |
| Systemd integration | `docker-compose@.service` template | Enables service management per compose project |
| RabbitMQ image | `rabbitmq:4.2.5-management` | Official image v4.2.5 stable; arm64v8 supported; includes management UI |
| RabbitMQ config | `rabbitmq.conf` file | Env vars `RABBITMQ_DEFAULT_USER/PASS` deprecated since 3.9; use config file |
| Cluster formation | Manual `join_cluster` via Ansible | Simple and explicit; no peer discovery plugin needed |
| Networking | Reuse existing default VPC | VPC/subnets/IGW already configured and routed |
| Node placement | One node per AZ (1a/1b/1c) | Failure isolation across AZs |
| Security groups | Modular, attach multiple | Follows existing account pattern; `from-home` covers client access |
| State | Local Terraform state | Starting point; upgrade to S3+DynamoDB for team use |
