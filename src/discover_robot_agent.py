"""Discover robot agents registered on ERC-8004 (Ethereum Sepolia).

Filters by on-chain metadata: category=robot (ERC-8004 reserved key).
Read-only — no wallet or signer needed.
"""

import sys
import requests
from agent0_sdk import SDK

sdk = SDK(
    chainId=11155111,
    rpcUrl="https://ethereum-sepolia-rpc.publicnode.com",
)

IPFS_GATEWAY = "https://ipfs.io/ipfs/"


def fetch_ipfs_tools(agent_id_int: int) -> list:
    """Fetch MCP tools directly from IPFS (bypasses subgraph indexing delays)."""
    try:
        uri = sdk.identity_registry.functions.tokenURI(agent_id_int).call()
        if not uri or not uri.startswith("ipfs://"):
            return []
        cid = uri.replace("ipfs://", "")
        resp = requests.get(f"{IPFS_GATEWAY}{cid}", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for svc in data.get("services", []):
            if svc.get("name") == "MCP":
                return svc.get("mcpTools", [])
    except Exception:
        pass
    return []


print("Searching for robot agents on Ethereum Sepolia...\n")
results = sdk.searchAgents(hasMetadataKey="category")

found = False
for agent in results:
    agent_id_str = agent.get("agentId") if isinstance(agent, dict) else agent.agentId
    agent_id_int = int(str(agent_id_str).split(":")[-1])

    # Verify category=robot on-chain (ERC-8004 reserved key)
    meta = sdk.identity_registry.functions.getMetadata(agent_id_int, "category").call()
    if meta != b"robot":
        continue

    found = True
    robot_type = sdk.identity_registry.functions.getMetadata(agent_id_int, "robot_type").call()
    provider = sdk.identity_registry.functions.getMetadata(agent_id_int, "fleet_provider").call()
    fleet = sdk.identity_registry.functions.getMetadata(agent_id_int, "fleet_domain").call()

    name = agent.get("name") if isinstance(agent, dict) else agent.name

    # Get tools from subgraph first, fall back to direct IPFS fetch
    tools = agent.get("mcpTools", []) if isinstance(agent, dict) else agent.mcpTools
    if not tools:
        tools = fetch_ipfs_tools(agent_id_int)

    print(f"  {name} (ID: {agent_id_str})")
    print(f"    robot_type:     {robot_type.decode() if robot_type else 'unknown'}")
    print(f"    fleet_provider: {provider.decode() if provider else 'none'}")
    print(f"    fleet_domain:   {fleet.decode() if fleet else 'none'}")
    print(f"    MCP tools:      {tools}")
    print()

if not found:
    print("  No robot agents found.")

# If an agent ID is passed as argument, fetch details
if len(sys.argv) > 1:
    agent_id = sys.argv[1]
    print(f"\nFetching agent {agent_id}...")
    summary = sdk.getAgent(f"11155111:{agent_id}")
    print(summary)
