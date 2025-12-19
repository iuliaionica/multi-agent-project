# Vault AWS MCP - Multi-Agent System

## Descriere

Sistem multi-agent pentru operațiuni AWS cu credențiale securizate prin HashiCorp Vault. Integrare MCP (Model Context Protocol) pentru Claude.

## Structura Proiectului

```
vault-aws-mcp/
├── src/vault_aws_mcp/
│   ├── agents/
│   │   ├── base_agent.py       # Clasă de bază pentru toți agenții
│   │   ├── aws_agent.py        # Operații AWS (S3, EC2, Lambda, DynamoDB)
│   │   ├── vault_agent.py      # Management secrete și credențiale
│   │   ├── github_agent.py     # Operații Git (status, commit, push, pull)
│   │   ├── mcp_agent.py        # Gestionare MCP server și tool discovery
│   │   ├── orchestrator.py     # Coordonare agenți, workflow-uri paralele
│   │   └── agent_system.py     # Entry point sistem multi-agent
│   ├── services/
│   │   ├── vault_client.py     # Client HashiCorp Vault
│   │   ├── aws_session_manager.py  # Sesiuni boto3 cu credențiale din Vault
│   │   └── lease_manager.py    # Gestionare TTL și reînnoire credențiale
│   ├── tools/
│   │   ├── s3_tools.py         # S3 operations (list, get, put, delete)
│   │   ├── ec2_tools.py        # EC2 operations (list, start, stop)
│   │   └── generic_tools.py    # Generic AWS (caller identity, regions)
│   ├── server.py               # MCP Server
│   └── config.py               # Configurație
├── cli.py                      # CLI interactiv
├── start.sh                    # Script pornire
└── pyproject.toml              # Config pachet Python
```

## Agenți

| Agent | Responsabilități |
|-------|------------------|
| **Orchestrator** | Coordonează toți agenții, execută workflow-uri paralele |
| **AWS Agent** | Operații S3, EC2, Lambda, DynamoDB |
| **Vault Agent** | Management secrete și credențiale cu TTL |
| **MCP Agent** | Gestionare MCP server și tool discovery |
| **GitHub Agent** | Operații Git (status, commit, push, pull, branch) |

## Comenzi

```bash
# Activare environment
cd ~/claude-project/vault-aws-mcp
source venv/bin/activate

# Pornire Vault (Terminal 1)
vault server -config=$HOME/vault/config.hcl

# Setup Vault (Terminal 2)
export VAULT_ADDR='http://127.0.0.1:8200'
vault operator unseal <unseal-key>
export VAULT_TOKEN='hvs.<token>'

# Rulare CLI
python cli.py

# Sau entry points
vault-aws-mcp        # Pornește MCP server
vault-aws-agents     # Pornește sistemul de agenți
```

## CLI Comenzi

- `/switch <agent>` - Schimbă agentul activ (aws, vault, mcp, github, orchestrator)
- `/status` - Afișează status agenți
- `/help` - Ajutor
- `/quit` - Ieșire

## Secrete în Vault

- `secret/github` - GitHub token pentru autentificare
- `secret/aws` - AWS credentials (sau AWS Secrets Engine pentru STS)

## Flow Securitate

1. MCP Server cere credențiale de la Vault
2. Vault comunică cu AWS STS și face AssumeRole
3. Vault returnează token temporar (TTL 1h, revocabil)

## Repository

https://github.com/iuliaionica/multi-agent-project
