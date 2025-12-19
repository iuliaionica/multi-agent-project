#!/usr/bin/env python3
"""Test Vault KV credentials retrieval."""

import os
import sys

# Change to project directory to load .env
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def test_vault_connection():
    """Test reading AWS credentials from Vault KV."""
    print("\n" + "="*60)
    print("TEST: Vault KV Credentials")
    print("="*60 + "\n")

    # Import after changing directory so .env is found
    from vault_aws_mcp.services.vault_client import VaultClient
    from vault_aws_mcp.config import settings

    print(f"[Config]")
    print(f"  Vault Address: {settings.vault_addr}")
    print(f"  Vault Token: {settings.vault_token[:20]}..." if settings.vault_token else "  Vault Token: NOT SET")
    print(f"  Use KV: {settings.vault_use_kv}")
    print(f"  KV Path: {settings.vault_kv_path}")
    print()

    print("[1] Creating Vault client...")
    client = VaultClient()

    print("[2] Checking connection...")
    if client.is_connected():
        print("    ✓ Connected to Vault")
    else:
        print("    ✗ NOT connected to Vault!")
        print("    Make sure Vault is running: vault server -dev")
        return False

    print("[3] Reading credentials from KV...")
    try:
        creds = client.get_kv_credentials()
        print("    ✓ Credentials retrieved!")
        print(f"    Access Key: {creds.access_key[:8]}...{creds.access_key[-4:]}")
        print(f"    Secret Key: {'*' * 20}")
        print(f"    Lease ID: {creds.lease_id}")
    except Exception as e:
        print(f"    ✗ Failed: {e}")
        return False

    print("\n[4] Testing boto3 session creation...")
    try:
        from vault_aws_mcp.services.aws_session_manager import AWSSessionManager
        session_mgr = AWSSessionManager(client)
        session_mgr.initialize_session()
        print("    ✓ AWS session created!")

        # Try to get caller identity
        print("\n[5] Testing AWS connection (get caller identity)...")
        try:
            identity = session_mgr.get_caller_identity()
            print("    ✓ AWS connection successful!")
            print(f"    Account: {identity.get('Account')}")
            print(f"    ARN: {identity.get('Arn')}")
        except Exception as e:
            print(f"    ✗ AWS call failed: {e}")
            print("    (This is expected if credentials are invalid)")

    except Exception as e:
        print(f"    ✗ Session creation failed: {e}")
        return False

    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60 + "\n")
    return True


if __name__ == "__main__":
    success = test_vault_connection()
    sys.exit(0 if success else 1)
