#!/usr/bin/env python3
"""CLI interactiv pentru agenții Vault-AWS-MCP."""

import asyncio
import os
import sys

# Adaugă src în path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()


def print_banner():
    print("""
╔═══════════════════════════════════════════════════════════╗
║             Vault-AWS-MCP Agent CLI                       ║
╠═══════════════════════════════════════════════════════════╣
║  Agenți disponibili:                                      ║
║    1. aws       - Operații AWS (S3, EC2)                  ║
║    2. vault     - Operații Vault                          ║
║    3. github    - Operații Git/GitHub                     ║
║    4. orchestrator - Coordonează toți agenții             ║
║                                                           ║
║  Comenzi:                                                 ║
║    /switch <agent>  - Schimbă agentul activ               ║
║    /status          - Arată starea conexiunilor           ║
║    /help            - Afișează ajutor                     ║
║    /quit            - Ieșire                              ║
╚═══════════════════════════════════════════════════════════╝
""")


def print_help():
    print("""
Comenzi disponibile:
  /switch aws         - Folosește AWS Agent
  /switch vault       - Folosește Vault Agent
  /switch github      - Folosește GitHub Agent
  /switch orchestrator - Folosește Orchestrator
  /status             - Verifică conexiunile
  /help               - Acest mesaj
  /quit               - Ieșire

Exemple de întrebări pentru agenți:
  AWS Agent:
    - List all S3 buckets
    - How many EC2 instances are running?
    - Create a bucket named test-bucket-123

  Vault Agent:
    - Show Vault status
    - List secrets engines

  GitHub Agent:
    - Check git status
    - Push all changes with message "Initial commit"
    - Show recent commits
    - Create branch feature-x

  Orchestrator:
    - List S3 buckets and check Vault status
""")


class AgentCLI:
    def __init__(self):
        self.current_agent = "github"
        self.agents = {}
        self.vault_client = None
        self.session_manager = None
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.repo_path = os.path.dirname(os.path.abspath(__file__))

    def initialize(self):
        """Inițializează conexiunile și agenții."""
        print("\n[*] Inițializare...")

        # Verifică API key
        if not self.api_key:
            print("[!] EROARE: ANTHROPIC_API_KEY nu este setat!")
            print("    Rulează: export ANTHROPIC_API_KEY='sk-ant-...'")
            return False
        print(f"[✓] Anthropic API Key: {self.api_key[:20]}...")

        # Conectare Vault
        print("[*] Conectare la Vault...")
        try:
            from vault_aws_mcp.services.vault_client import VaultClient
            self.vault_client = VaultClient()
            if self.vault_client.is_connected():
                print("[✓] Vault conectat")
            else:
                print("[!] Vault nu este conectat - unele funcții nu vor fi disponibile")
        except Exception as e:
            print(f"[!] Eroare Vault: {e}")

        # Inițializare AWS Session
        print("[*] Inițializare sesiune AWS...")
        try:
            from vault_aws_mcp.services.aws_session_manager import AWSSessionManager
            self.session_manager = AWSSessionManager(self.vault_client)
            self.session_manager.initialize_session()

            identity = self.session_manager.get_caller_identity()
            print(f"[✓] AWS conectat: {identity.get('Arn')}")
        except Exception as e:
            print(f"[!] Eroare AWS: {e}")

        # Creează agenții
        print("[*] Creare agenți...")

        # GitHub Agent (primul pentru că e default)
        try:
            from vault_aws_mcp.agents.github_agent import GitHubAgent
            self.agents["github"] = GitHubAgent(
                vault_client=self.vault_client,
                repo_path=self.repo_path,
                api_key=self.api_key,
            )
            print("[✓] GitHub Agent creat")
        except Exception as e:
            print(f"[!] Eroare GitHub Agent: {e}")

        # AWS Agent
        try:
            from vault_aws_mcp.agents.aws_agent import AWSAgent
            self.agents["aws"] = AWSAgent(
                vault_client=self.vault_client,
                session_manager=self.session_manager,
                api_key=self.api_key,
            )
            print("[✓] AWS Agent creat")
        except Exception as e:
            print(f"[!] Eroare AWS Agent: {e}")

        # Vault Agent
        try:
            from vault_aws_mcp.agents.vault_agent import VaultAgent
            self.agents["vault"] = VaultAgent(
                vault_client=self.vault_client,
                api_key=self.api_key,
            )
            print("[✓] Vault Agent creat")
        except Exception as e:
            print(f"[!] Eroare Vault Agent: {e}")

        # Orchestrator
        try:
            from vault_aws_mcp.agents import AgentSystem, AgentSystemConfig
            config = AgentSystemConfig(anthropic_api_key=self.api_key)
            system = AgentSystem.create(config)
            self.agents["orchestrator"] = system.orchestrator
            print("[✓] Orchestrator creat")
        except Exception as e:
            print(f"[!] Eroare Orchestrator: {e}")

        print("\n[✓] Inițializare completă!\n")
        return True

    def show_status(self):
        """Afișează starea conexiunilor."""
        print("\n--- Status ---")
        print(f"Agent activ: {self.current_agent}")
        print(f"Vault: {'Conectat' if self.vault_client and self.vault_client.is_connected() else 'Deconectat'}")
        print(f"AWS Session: {'Activă' if self.session_manager and self.session_manager.has_valid_session else 'Inactivă'}")
        print(f"Repo path: {self.repo_path}")
        print(f"Agenți disponibili: {list(self.agents.keys())}")
        print("--------------\n")

    async def run_query(self, query: str):
        """Execută o întrebare către agentul activ."""
        if self.current_agent not in self.agents:
            print(f"[!] Agentul '{self.current_agent}' nu este disponibil")
            return

        agent = self.agents[self.current_agent]
        print(f"\n[{self.current_agent.upper()}] Procesez: {query}")
        print("[*] Așteptați răspunsul...\n")

        try:
            result = await agent.run(query)
            if result.success:
                print(f"[✓] Răspuns:\n{result.output}")
            else:
                print(f"[!] Eroare: {result.error}")
        except Exception as e:
            print(f"[!] Excepție: {e}")

    def run(self):
        """Bucla principală CLI."""
        print_banner()

        if not self.initialize():
            return

        print(f"Agent activ: {self.current_agent}")
        print("Scrie o întrebare sau /help pentru ajutor.\n")

        while True:
            try:
                prompt = f"[{self.current_agent}]> "
                user_input = input(prompt).strip()

                if not user_input:
                    continue

                # Comenzi speciale
                if user_input.startswith("/"):
                    cmd = user_input.lower().split()

                    if cmd[0] == "/quit" or cmd[0] == "/exit":
                        print("La revedere!")
                        break

                    elif cmd[0] == "/help":
                        print_help()

                    elif cmd[0] == "/status":
                        self.show_status()

                    elif cmd[0] == "/switch":
                        if len(cmd) < 2:
                            print("Utilizare: /switch <aws|vault|github|orchestrator>")
                        elif cmd[1] in self.agents:
                            self.current_agent = cmd[1]
                            print(f"[✓] Agent schimbat: {self.current_agent}")
                        else:
                            print(f"[!] Agent necunoscut: {cmd[1]}")
                            print(f"    Disponibili: {list(self.agents.keys())}")
                    else:
                        print(f"[!] Comandă necunoscută: {cmd[0]}")

                else:
                    # Trimite întrebarea către agent
                    asyncio.run(self.run_query(user_input))

            except KeyboardInterrupt:
                print("\n\nLa revedere!")
                break
            except EOFError:
                break


if __name__ == "__main__":
    cli = AgentCLI()
    cli.run()
