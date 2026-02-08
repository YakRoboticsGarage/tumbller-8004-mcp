"""Fix on-chain metadata: set category=robot and clear old agent_type key.

One-time migration script. Safe to run multiple times.
"""

import os
from dotenv import load_dotenv
from agent0_sdk import SDK

load_dotenv()

sdk = SDK(
    chainId=11155111,
    rpcUrl=os.environ["RPC_URL"],
    signer=os.environ["SIGNER_PVT_KEY"],
)

AGENT_ID_INT = 989

# Read current values
old_key = sdk.identity_registry.functions.getMetadata(AGENT_ID_INT, "agent_type").call()
new_key = sdk.identity_registry.functions.getMetadata(AGENT_ID_INT, "category").call()
print(f"Current on-chain metadata:")
print(f"  agent_type = {old_key.decode() if old_key else '(empty)'}")
print(f"  category   = {new_key.decode() if new_key else '(empty)'}")

# Set category=robot
if new_key != b"robot":
    print("\nSetting category=robot...")
    tx = sdk.web3_client.transact_contract(
        sdk.identity_registry, "setMetadata", AGENT_ID_INT, "category", b"robot"
    )
    sdk.web3_client.wait_for_transaction(tx, timeout=60)
    print(f"  Done (tx: {tx})")
else:
    print("\n  category=robot already set, skipping.")

# Clear old agent_type key
if old_key:
    print("Clearing agent_type...")
    tx = sdk.web3_client.transact_contract(
        sdk.identity_registry, "setMetadata", AGENT_ID_INT, "agent_type", b""
    )
    sdk.web3_client.wait_for_transaction(tx, timeout=60)
    print(f"  Done (tx: {tx})")
else:
    print("  agent_type already empty, skipping.")

# Verify
new_val = sdk.identity_registry.functions.getMetadata(AGENT_ID_INT, "category").call()
old_val = sdk.identity_registry.functions.getMetadata(AGENT_ID_INT, "agent_type").call()
print(f"\nVerification:")
print(f"  category   = {new_val.decode() if new_val else '(empty)'}")
print(f"  agent_type = {old_val.decode() if old_val else '(empty)'}")
