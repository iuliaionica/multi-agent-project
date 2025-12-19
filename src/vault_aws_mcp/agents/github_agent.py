"""GitHub Agent for repository operations."""

import logging
import subprocess
from typing import Any

from .base_agent import AgentTool, BaseAgent

logger = logging.getLogger(__name__)


class GitHubAgent(BaseAgent):
    """Agent for GitHub operations.

    Handles:
    - Git operations (add, commit, push, pull)
    - Repository status
    - Branch management
    """

    def __init__(
        self,
        vault_client: Any = None,
        repo_path: str = ".",
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 2048,
    ) -> None:
        self._vault_client = vault_client
        self._repo_path = repo_path
        self._github_token: str | None = None
        self._github_username: str | None = None

        super().__init__(
            name="GitHubAgent",
            model=model,
            max_tokens=max_tokens,
            api_key=api_key,
        )

        # Load GitHub credentials from Vault
        self._load_github_credentials()

    @property
    def system_prompt(self) -> str:
        return """You are a GitHub Agent specialized in git operations and repository management.

Your capabilities:
- Check repository status (git status)
- Stage files for commit (git add)
- Create commits with descriptive messages
- Push changes to remote repository
- Pull latest changes
- Manage branches

When asked to push code:
1. First check git status to see what's changed
2. Stage the appropriate files (usually all with git add .)
3. Create a commit with a clear, descriptive message
4. Push to the remote repository

Always provide clear feedback about what operations were performed.
Be careful with sensitive files - never commit .env or credentials.
"""

    @property
    def vault_role(self) -> str:
        return "github-role"

    def _load_github_credentials(self) -> None:
        """Load GitHub credentials from Vault."""
        if not self._vault_client:
            logger.warning("No Vault client provided, GitHub auth may fail")
            return

        try:
            # Read from Vault KV
            response = self._vault_client.client.secrets.kv.v2.read_secret_version(
                path="github",
                mount_point="secret",
            )
            data = response["data"]["data"]
            self._github_token = data.get("token")
            self._github_username = data.get("username")
            logger.info(f"Loaded GitHub credentials for user: {self._github_username}")
        except Exception as e:
            logger.error(f"Failed to load GitHub credentials: {e}")

    def _run_git_command(self, *args: str) -> dict[str, Any]:
        """Run a git command and return the result."""
        cmd = ["git", "-C", self._repo_path] + list(args)
        logger.info(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            output = result.stdout.strip()
            error = result.stderr.strip()

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": error or output,
                    "return_code": result.returncode,
                }

            return {
                "success": True,
                "output": output,
                "return_code": 0,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _register_tools(self) -> None:
        """Register GitHub-specific tools."""

        self.register_tool(AgentTool(
            name="git_status",
            description="Check the status of the git repository. Shows modified, staged, and untracked files.",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
            handler=self._git_status,
        ))

        self.register_tool(AgentTool(
            name="git_add",
            description="Stage files for commit. Use '.' to stage all files, or specify a path.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to stage. Use '.' for all files.",
                        "default": ".",
                    },
                },
                "required": [],
            },
            handler=self._git_add,
        ))

        self.register_tool(AgentTool(
            name="git_commit",
            description="Create a commit with the staged changes.",
            parameters={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Commit message describing the changes.",
                    },
                },
                "required": ["message"],
            },
            handler=self._git_commit,
        ))

        self.register_tool(AgentTool(
            name="git_push",
            description="Push commits to the remote repository.",
            parameters={
                "type": "object",
                "properties": {
                    "remote": {
                        "type": "string",
                        "description": "Remote name (default: origin)",
                        "default": "origin",
                    },
                    "branch": {
                        "type": "string",
                        "description": "Branch name (default: main)",
                        "default": "main",
                    },
                },
                "required": [],
            },
            handler=self._git_push,
        ))

        self.register_tool(AgentTool(
            name="git_pull",
            description="Pull latest changes from the remote repository.",
            parameters={
                "type": "object",
                "properties": {
                    "remote": {
                        "type": "string",
                        "description": "Remote name (default: origin)",
                        "default": "origin",
                    },
                    "branch": {
                        "type": "string",
                        "description": "Branch name (default: main)",
                        "default": "main",
                    },
                },
                "required": [],
            },
            handler=self._git_pull,
        ))

        self.register_tool(AgentTool(
            name="git_log",
            description="Show recent commit history.",
            parameters={
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Number of commits to show (default: 5)",
                        "default": 5,
                    },
                },
                "required": [],
            },
            handler=self._git_log,
        ))

        self.register_tool(AgentTool(
            name="git_branch",
            description="List branches or create a new branch.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "New branch name. If not provided, lists existing branches.",
                    },
                },
                "required": [],
            },
            handler=self._git_branch,
        ))

        self.register_tool(AgentTool(
            name="git_init_remote",
            description="Initialize git repository and set up remote origin.",
            parameters={
                "type": "object",
                "properties": {
                    "repo_url": {
                        "type": "string",
                        "description": "GitHub repository URL (e.g., https://github.com/user/repo.git)",
                    },
                },
                "required": ["repo_url"],
            },
            handler=self._git_init_remote,
        ))

    async def _git_status(self) -> dict[str, Any]:
        """Get repository status."""
        return self._run_git_command("status", "--porcelain=v1")

    async def _git_add(self, path: str = ".") -> dict[str, Any]:
        """Stage files."""
        return self._run_git_command("add", path)

    async def _git_commit(self, message: str) -> dict[str, Any]:
        """Create a commit."""
        return self._run_git_command("commit", "-m", message)

    async def _git_push(self, remote: str = "origin", branch: str = "main") -> dict[str, Any]:
        """Push to remote."""
        if self._github_token and self._github_username:
            # Configure credential helper for this push
            self._run_git_command(
                "config", "credential.helper", "store"
            )

        result = self._run_git_command("push", "-u", remote, branch)

        if not result["success"] and "rejected" in str(result.get("error", "")):
            # Try with force if needed (be careful!)
            return {
                "success": False,
                "error": result["error"],
                "hint": "Push was rejected. You may need to pull first or use force push.",
            }

        return result

    async def _git_pull(self, remote: str = "origin", branch: str = "main") -> dict[str, Any]:
        """Pull from remote."""
        return self._run_git_command("pull", remote, branch)

    async def _git_log(self, count: int = 5) -> dict[str, Any]:
        """Show commit history."""
        return self._run_git_command("log", f"-{count}", "--oneline")

    async def _git_branch(self, name: str | None = None) -> dict[str, Any]:
        """List or create branches."""
        if name:
            return self._run_git_command("checkout", "-b", name)
        return self._run_git_command("branch", "-a")

    async def _git_init_remote(self, repo_url: str) -> dict[str, Any]:
        """Initialize repository and set remote."""
        results = []

        # Check if already a git repo
        check = self._run_git_command("rev-parse", "--git-dir")
        if not check["success"]:
            # Initialize new repo
            init_result = self._run_git_command("init")
            results.append(f"git init: {init_result}")

        # Configure user if not set
        self._run_git_command("config", "user.email", f"{self._github_username}@users.noreply.github.com")
        self._run_git_command("config", "user.name", self._github_username or "Agent")

        # Set up remote with token authentication
        if self._github_token and self._github_username:
            # Convert https://github.com/user/repo.git to https://token@github.com/user/repo.git
            if repo_url.startswith("https://github.com/"):
                auth_url = repo_url.replace(
                    "https://github.com/",
                    f"https://{self._github_username}:{self._github_token}@github.com/"
                )
            else:
                auth_url = repo_url
        else:
            auth_url = repo_url

        # Remove existing origin if present
        self._run_git_command("remote", "remove", "origin")

        # Add new origin
        remote_result = self._run_git_command("remote", "add", "origin", auth_url)
        results.append(f"remote add: {remote_result}")

        # Set default branch to main
        self._run_git_command("branch", "-M", "main")

        return {
            "success": True,
            "output": f"Repository initialized with remote: {repo_url}",
            "details": results,
        }
