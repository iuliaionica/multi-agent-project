#!/usr/bin/env python3
"""Create S3 bucket using AWS credentials from Vault."""

import os
import sys

# Change to project directory to load .env
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def create_bucket(bucket_name: str):
    """Create an S3 bucket using Vault credentials."""
    print("\n" + "="*60)
    print(f"CREATE S3 BUCKET: {bucket_name}")
    print("="*60 + "\n")

    # Step 1: Load config and connect to Vault
    print("[1] Loading configuration...")
    from vault_aws_mcp.config import settings
    print(f"    Vault Address: {settings.vault_addr}")
    print(f"    Using KV: {settings.vault_use_kv}")
    print(f"    KV Path: {settings.vault_kv_path}")

    # Step 2: Connect to Vault and get credentials
    print("\n[2] Connecting to Vault...")
    from vault_aws_mcp.services.vault_client import VaultClient
    vault_client = VaultClient()

    if not vault_client.is_connected():
        print("    ERROR: Cannot connect to Vault!")
        return False

    print("    ✓ Connected to Vault")

    print("\n[3] Getting AWS credentials from Vault KV...")
    try:
        creds = vault_client.get_kv_credentials()
        print(f"    ✓ Got credentials")
        print(f"    Access Key: {creds.access_key[:8]}...{creds.access_key[-4:]}")
    except Exception as e:
        print(f"    ERROR: {e}")
        return False

    # Step 3: Create AWS session
    print("\n[4] Creating AWS session...")
    from vault_aws_mcp.services.aws_session_manager import AWSSessionManager
    session_mgr = AWSSessionManager(vault_client)
    session_mgr.initialize_session()
    print("    ✓ AWS session created")

    # Step 4: Verify identity
    print("\n[5] Verifying AWS identity...")
    try:
        identity = session_mgr.get_caller_identity()
        print(f"    ✓ Connected as: {identity.get('Arn')}")
        print(f"    Account: {identity.get('Account')}")
    except Exception as e:
        print(f"    ERROR: {e}")
        return False

    # Step 5: Create S3 bucket
    print(f"\n[6] Creating S3 bucket '{bucket_name}'...")
    try:
        s3_client = session_mgr.get_client('s3')

        # Get current region
        region = settings.aws_region or 'us-east-1'
        print(f"    Region: {region}")

        # Create bucket (special handling for us-east-1)
        if region == 'us-east-1':
            response = s3_client.create_bucket(Bucket=bucket_name)
        else:
            response = s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )

        print(f"    ✓ Bucket created successfully!")
        print(f"    Location: {response.get('Location', 'N/A')}")

    except s3_client.exceptions.BucketAlreadyExists:
        print(f"    ERROR: Bucket '{bucket_name}' already exists (owned by another account)")
        return False
    except s3_client.exceptions.BucketAlreadyOwnedByYou:
        print(f"    INFO: Bucket '{bucket_name}' already exists and you own it")
        return True
    except Exception as e:
        print(f"    ERROR: {type(e).__name__}: {e}")
        return False

    # Step 6: Verify bucket exists
    print(f"\n[7] Verifying bucket exists...")
    try:
        buckets = s3_client.list_buckets()
        bucket_names = [b['Name'] for b in buckets.get('Buckets', [])]
        if bucket_name in bucket_names:
            print(f"    ✓ Bucket '{bucket_name}' confirmed in bucket list")
        else:
            print(f"    WARNING: Bucket not yet visible in list (may take a moment)")
    except Exception as e:
        print(f"    WARNING: Could not verify: {e}")

    print("\n" + "="*60)
    print("SUCCESS: S3 bucket created!")
    print("="*60 + "\n")
    return True


if __name__ == "__main__":
    bucket_name = sys.argv[1] if len(sys.argv) > 1 else "test1234999"
    success = create_bucket(bucket_name)
    sys.exit(0 if success else 1)
