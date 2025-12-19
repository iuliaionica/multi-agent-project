# Vault AWS MCP Server

MCP Server pentru operațiuni AWS cu management securizat de credențiale prin HashiCorp Vault.

## Sistem Multi-Agent

Proiectul include un sistem de agenți orchestrați:

| Agent | Responsabilități |
|-------|------------------|
| **Orchestrator** | Coordonează agenții, execută workflow-uri paralele |
| **AWS Agent** | Operații S3, EC2, Lambda, DynamoDB etc. |
| **Vault Agent** | Management secrete și credențiale |
| **MCP Agent** | Gestionare MCP server și tool discovery |
| **GitHub Agent** | Operații Git (status, commit, push, pull, branch) |

### CLI Interactiv

```bash
python cli.py
```

Comenzi: `/switch <agent>`, `/status`, `/help`, `/quit`

## Arhitectură MCP

```
┌─────────────────────────────────────────────────────────────────┐
│                       MCP Client (Claude)                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      MCP Server                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  S3 Tools   │  │ EC2 Tools   │  │  Generic AWS Tools      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│                           │                                      │
│                           ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              AWS Session Manager                            ││
│  └─────────────────────────────────────────────────────────────┘│
│                           │                                      │
│                           ▼                                      │
│  ┌──────────────────┐  ┌──────────────────────────────────────┐ │
│  │  Vault Client    │  │       Lease Manager                  │ │
│  └──────────────────┘  └──────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    HashiCorp Vault                              │
│              (AWS Secrets Engine + STS AssumeRole)              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         AWS STS                                  │
│                 (AssumeRole → temp credentials)                  │
└─────────────────────────────────────────────────────────────────┘
```

## Flow de Securitate

1. **MCP Server cere credențiale de la Vault** (nu credențiale raw)
2. **Vault comunică cu AWS STS** și face AssumeRole
3. **Vault returnează un token temporar:**
   - Generat dinamic de AWS STS
   - Expiră automat (default TTL 1h)
   - Nu expune niciodată credențialele root
   - Vault poate revoca token-ul înainte de expirare

## Instalare

```bash
cd vault-aws-mcp
pip install -e .
```

## Configurare Vault

### 1. Pornește Vault (dev mode pentru testing)

```bash
vault server -dev
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='hvs.xxx'  # root token din output
```

### 2. Configurează AWS Secrets Engine

```bash
# Enable AWS secrets engine
vault secrets enable aws

# Configurează credențialele root (pentru Vault să poată genera credențiale)
vault write aws/config/root \
    access_key=$AWS_ACCESS_KEY_ID \
    secret_key=$AWS_SECRET_ACCESS_KEY \
    region=us-east-1

# Creează IAM role pentru agenți
vault write aws/roles/mcp-agent-role \
    credential_type=assumed_role \
    role_arns=arn:aws:iam::ACCOUNT_ID:role/VaultMCPAgentRole \
    default_sts_ttl=1h \
    max_sts_ttl=4h
```

### 3. Creează IAM Role în AWS

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT_ID:user/vault-user"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

## Configurare Claude Code

Adaugă în `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "vault-aws": {
      "command": "python",
      "args": ["-m", "vault_aws_mcp.server"],
      "cwd": "/path/to/vault-aws-mcp/src",
      "env": {
        "VAULT_AWS_MCP_VAULT_ADDR": "http://127.0.0.1:8200",
        "VAULT_AWS_MCP_VAULT_TOKEN": "hvs.your-token",
        "VAULT_AWS_MCP_VAULT_AWS_ROLE": "mcp-agent-role"
      }
    }
  }
}
```

## Tool-uri Disponibile

### S3
- `s3_list_buckets` - Listează toate bucket-urile
- `s3_list_objects` - Listează obiectele dintr-un bucket
- `s3_get_object` - Descarcă conținutul unui obiect
- `s3_put_object` - Încarcă conținut într-un obiect
- `s3_delete_object` - Șterge un obiect
- `s3_get_bucket_info` - Informații despre un bucket

### EC2
- `ec2_list_instances` - Listează instanțele EC2
- `ec2_get_instance` - Detalii despre o instanță
- `ec2_start_instance` - Pornește o instanță
- `ec2_stop_instance` - Oprește o instanță
- `ec2_list_security_groups` - Listează security groups
- `ec2_list_vpcs` - Listează VPC-uri

### Generic AWS
- `aws_call` - Apelează orice API AWS (DynamoDB, Lambda, SQS, etc.)
- `aws_get_caller_identity` - Verifică identitatea curentă
- `aws_list_regions` - Listează regiunile AWS

### Vault Credentials
- `vault_credential_status` - Status credențiale curente
- `vault_refresh_credentials` - Reîmprospătează credențialele
- `vault_revoke_credentials` - Revocă credențialele imediat

## Variabile de Mediu

| Variabilă | Default | Descriere |
|-----------|---------|-----------|
| `VAULT_AWS_MCP_VAULT_ADDR` | `http://127.0.0.1:8200` | Adresa Vault |
| `VAULT_AWS_MCP_VAULT_TOKEN` | - | Token autentificare Vault |
| `VAULT_AWS_MCP_VAULT_AWS_MOUNT_PATH` | `aws` | Mount path AWS secrets engine |
| `VAULT_AWS_MCP_VAULT_AWS_ROLE` | `mcp-agent-role` | Rol Vault pentru credențiale |
| `VAULT_AWS_MCP_AWS_REGION` | `us-east-1` | Regiune AWS default |
| `VAULT_AWS_MCP_LEASE_TTL` | `1h` | TTL pentru credențiale |
| `VAULT_AWS_MCP_LEASE_AUTO_RENEW` | `true` | Auto-renewal pentru lease-uri |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/
ruff check src/
```
