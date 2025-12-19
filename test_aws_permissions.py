#!/usr/bin/env python3
"""Test AWS permissions for current user."""

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def test_permissions():
    """Test various AWS operations to see what's allowed."""
    print("\n" + "="*60)
    print("AWS PERMISSIONS TEST")
    print("="*60 + "\n")

    from vault_aws_mcp.services.vault_client import VaultClient
    from vault_aws_mcp.services.aws_session_manager import AWSSessionManager

    # Setup
    vault_client = VaultClient()
    session_mgr = AWSSessionManager(vault_client)
    session_mgr.initialize_session()

    identity = session_mgr.get_caller_identity()
    print(f"User: {identity.get('Arn')}")
    print(f"Account: {identity.get('Account')}\n")

    # Test S3 permissions
    print("S3 Permissions:")
    s3 = session_mgr.get_client('s3')

    # List buckets
    try:
        buckets = s3.list_buckets()
        print(f"  ✓ s3:ListAllMyBuckets - {len(buckets.get('Buckets', []))} buckets found")
        for b in buckets.get('Buckets', [])[:5]:
            print(f"      - {b['Name']}")
    except Exception as e:
        print(f"  ✗ s3:ListAllMyBuckets - {e}")

    # Test EC2 permissions
    print("\nEC2 Permissions:")
    ec2 = session_mgr.get_client('ec2')

    try:
        instances = ec2.describe_instances()
        count = sum(len(r['Instances']) for r in instances.get('Reservations', []))
        print(f"  ✓ ec2:DescribeInstances - {count} instances found")
    except Exception as e:
        print(f"  ✗ ec2:DescribeInstances - {e}")

    try:
        regions = ec2.describe_regions()
        print(f"  ✓ ec2:DescribeRegions - {len(regions.get('Regions', []))} regions")
    except Exception as e:
        print(f"  ✗ ec2:DescribeRegions - {e}")

    # Test IAM permissions
    print("\nIAM Permissions:")
    iam = session_mgr.get_client('iam')

    try:
        user = iam.get_user()
        print(f"  ✓ iam:GetUser - {user['User']['UserName']}")
    except Exception as e:
        print(f"  ✗ iam:GetUser - {e}")

    try:
        policies = iam.list_attached_user_policies(UserName='iulia-aws')
        print(f"  ✓ iam:ListAttachedUserPolicies:")
        for p in policies.get('AttachedPolicies', []):
            print(f"      - {p['PolicyName']}")
    except Exception as e:
        print(f"  ✗ iam:ListAttachedUserPolicies - {type(e).__name__}")

    print("\n" + "="*60)


if __name__ == "__main__":
    test_permissions()
