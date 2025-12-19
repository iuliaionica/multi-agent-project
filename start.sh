#!/bin/bash
# Startup script pentru vault-aws-mcp
# După restart, rulează: ./start.sh

cd "$(dirname "$0")"

echo "=== Vault AWS MCP - Startup ==="
echo ""

# Activează virtual environment
if [ -d "venv" ]; then
    echo "[1/3] Activez virtual environment..."
    source venv/bin/activate
    echo "      ✓ venv activat"
else
    echo "[1/3] EROARE: venv nu există. Rulează: python3 -m venv venv && source venv/bin/activate && pip install -e ."
    exit 1
fi

# Verifică Vault
echo ""
echo "[2/3] Verifică dacă Vault rulează..."
export PATH="/snap/bin:$PATH"
export VAULT_ADDR='http://127.0.0.1:8200'

if vault status > /dev/null 2>&1; then
    echo "      ✓ Vault rulează"
else
    echo "      ✗ Vault NU rulează!"
    echo ""
    echo "      Deschide un alt terminal și rulează:"
    echo "      vault server -dev"
    echo ""
    echo "      Apoi copiază Root Token și setează-l:"
    echo "      export VAULT_TOKEN='hvs.xxxxx'"
    exit 1
fi

# Verifică VAULT_TOKEN
echo ""
echo "[3/3] Verifică VAULT_TOKEN..."
if [ -z "$VAULT_TOKEN" ]; then
    echo "      ✗ VAULT_TOKEN nu este setat!"
    echo ""
    echo "      Setează-l cu:"
    echo "      export VAULT_TOKEN='hvs.xxxxx'"
    exit 1
else
    echo "      ✓ VAULT_TOKEN setat"
fi

echo ""
echo "=== Gata! ==="
echo ""
echo "Acum poți rula:"
echo "  - vault-aws-mcp      # pornește MCP server"
echo "  - vault-aws-agents   # pornește sistemul de agenți"
echo ""
echo "Sau în Python:"
echo "  from vault_aws_mcp.agents import AgentSystem"
echo "  system = AgentSystem.create()"
