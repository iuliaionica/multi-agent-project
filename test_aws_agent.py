#!/usr/bin/env python3
"""Test AWS Agent - create S3 bucket using the agent system."""

import asyncio
import logging
import os
import sys

# Change to project directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

async def test_aws_agent(bucket_name: str, api_key: str):
    """Test AWS Agent creating an S3 bucket."""
    print("\n" + "="*60)
    print(f"TEST: AWS Agent - Create S3 Bucket '{bucket_name}'")
    print("="*60 + "\n")

    # Step 1: Create AWS Agent with Vault credentials
    print("[1] Creating AWS Agent...")
    from vault_aws_mcp.agents.aws_agent import AWSAgent
    from vault_aws_mcp.services.vault_client import VaultClient
    from vault_aws_mcp.services.aws_session_manager import AWSSessionManager

    # Initialize Vault and AWS session
    vault_client = VaultClient()
    if not vault_client.is_connected():
        print("    ERROR: Vault not connected!")
        return False

    session_manager = AWSSessionManager(vault_client)
    session_manager.initialize_session()
    print("    ✓ Vault connected, AWS session initialized")

    # Create the agent
    aws_agent = AWSAgent(
        vault_client=vault_client,
        session_manager=session_manager,
        api_key=api_key,
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
    )
    print(f"    ✓ AWS Agent created: {aws_agent.name}")
    print(f"    Tools available: {list(aws_agent._tools.keys())}")

    # Step 2: Ask the agent to create a bucket
    print(f"\n[2] Asking agent to create bucket '{bucket_name}'...")
    print("    Sending task to agent...")

    result = await aws_agent.run(
        f"Create a new S3 bucket named '{bucket_name}'. "
        f"First verify credentials, then create the bucket."
    )

    print(f"\n[3] Agent Result:")
    print(f"    Success: {result.success}")
    if result.output:
        print(f"    Output:\n{result.output}")
    if result.error:
        print(f"    Error: {result.error}")

    # Step 3: Verify the bucket was created
    print(f"\n[4] Verifying bucket exists...")
    verify_result = await aws_agent.run("List all S3 buckets to verify the new bucket exists")

    print(f"    Verification output:\n{verify_result.output}")

    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60 + "\n")

    return result.success


async def main():
    # Get API key
    api_key = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY required!")
        print("Usage: python test_aws_agent.py <api_key> [bucket_name]")
        return

    # Get bucket name
    bucket_name = sys.argv[2] if len(sys.argv) > 2 else "test-agent-bucket-12345"

    await test_aws_agent(bucket_name, api_key)


if __name__ == "__main__":
    asyncio.run(main())
