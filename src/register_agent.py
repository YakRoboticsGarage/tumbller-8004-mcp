"""Register the Tumbller MCP server on ERC-8004 (Ethereum Sepolia)."""

import os
from dotenv import load_dotenv
from agent0_sdk import SDK

load_dotenv()

# --- Initialize Agent0 SDK ---
sdk = SDK(
    chainId=11155111,                          # Ethereum Sepolia
    rpcUrl=os.environ["RPC_URL"],
    signer=os.environ["SIGNER_PVT_KEY"],
    ipfs="pinata",
    pinataJwt=os.environ["PINATA_JWT"],
)

# --- Create agent ---
agent = sdk.createAgent(
    name="Tumbller Self-Balancing Robot",
    description=(
        "A physical ESP32-S3 two-wheeled robot controllable via MCP. "
        "Move in four directions, read temperature and humidity sensors."
    ),
    image="",  # optional image URL
)

# --- Configure MCP endpoint ---
# auto_fetch=False because the SDK's EndpointCrawler doesn't support
# MCP streamable-http transport (sends wrong headers, gets 400).
# We set the tool list manually instead.
ngrok_domain = os.environ["NGROK_DOMAIN"]
agent.setMCP(f"https://{ngrok_domain}/mcp", auto_fetch=False)

# Manually declare MCP tools (must match server.py tool names)
from agent0_sdk.core.models import EndpointType
mcp_ep = next(ep for ep in agent.registration_file.endpoints if ep.type == EndpointType.MCP)
mcp_ep.meta["mcpTools"] = ["move", "is_robot_online", "get_temperature_humidity"]

agent.setTrust(reputation=True)
agent.setActive(True)
agent.setX402Support(False)

# --- Robot classification metadata (on-chain) ---
# "category" is a reserved ERC-8004 key per https://best-practices.8004scan.io
# Custom keys (robot_type, fleet_provider, fleet_domain) are also allowed.
agent.setMetadata({
    "category": "robot",
    "robot_type": "differential_drive",
    "fleet_provider": "yakrover",
    "fleet_domain": "yakrover.com/finland",
})

# --- Register on-chain + upload to IPFS ---
# This mints an ERC-721 NFT on the Identity Registry.
print("Submitting registration transaction...")
tx_handle = agent.registerIPFS()
print(f"Transaction submitted: {tx_handle.tx_hash}")

# Wait for the transaction to be mined and get the result
print("Waiting for transaction to be mined...")
mined = tx_handle.wait_mined(timeout=120)
reg_file = mined.result

print(f"\nAgent registered on Ethereum Sepolia!")
print(f"Agent ID: {reg_file.agentId}")
print(f"Agent URI: {reg_file.agentURI}")
print(f"On-chain metadata: category=robot, robot_type=differential_drive, fleet_provider=yakrover, fleet_domain=yakrover.com/finland")
