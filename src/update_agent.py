"""Update the existing Tumbller agent registration.

Loads agent 11155111:989, ensures MCP tools are set, migrates
on-chain metadata from agent_type to category (ERC-8004 standard),
re-uploads to IPFS, and updates the on-chain tokenURI.
"""

import os
from dotenv import load_dotenv
from agent0_sdk import SDK
from agent0_sdk.core.models import EndpointType

load_dotenv()

sdk = SDK(
    chainId=11155111,
    rpcUrl=os.environ["RPC_URL"],
    signer=os.environ["SIGNER_PVT_KEY"],
    ipfs="pinata",
    pinataJwt=os.environ["PINATA_JWT"],
)

AGENT_ID = "11155111:989"

print(f"Loading agent {AGENT_ID}...")
agent = sdk.loadAgent(AGENT_ID)

print(f"  Name: {agent.name}")
print(f"  MCP endpoint: {agent.mcpEndpoint}")
print(f"  Current tools: {agent.mcpTools}")

# Fix the MCP endpoint: set tools manually
ngrok_domain = os.environ["NGROK_DOMAIN"]
agent.setMCP(f"https://{ngrok_domain}/mcp", auto_fetch=False)

mcp_ep = next(ep for ep in agent.registration_file.endpoints if ep.type == EndpointType.MCP)
mcp_ep.meta["mcpTools"] = ["move", "is_robot_online", "get_temperature_humidity"]

print(f"\n  Updated tools: {mcp_ep.meta['mcpTools']}")

# Migrate on-chain metadata: agent_type -> category (ERC-8004 reserved key)
agent.setMetadata({
    "category": "robot",
    "robot_type": "differential_drive",
    "fleet_provider": "yakrover",
    "fleet_domain": "yakrover.com/finland",
})

# Delete the old non-standard key
agent.delMetadata("agent_type")

print("  Metadata: category=robot (migrated from agent_type)")

# Re-upload to IPFS and update on-chain URI + metadata
print("\nSubmitting update transaction...")
tx_handle = agent.registerIPFS()
print(f"Transaction submitted: {tx_handle.tx_hash}")

print("Waiting for transaction to be mined...")
mined = tx_handle.wait_mined(timeout=120)
reg_file = mined.result

print(f"\nAgent updated!")
print(f"  Agent ID:  {reg_file.agentId}")
print(f"  Agent URI: {reg_file.agentURI}")
print(f"  MCP tools: {agent.mcpTools}")
