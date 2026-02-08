# Tumbller Agent — ERC-8004 + MCP Plan

## Goal

Expose the Tumbller self-balancing robot as a **trustless, on-chain discoverable AI agent** using:

- **FastMCP** (Python) to wrap the robot's HTTP API as MCP tools
- **ngrok** to tunnel the local MCP server to a public URL
- **ERC-8004** (via `agent0_sdk` Python SDK) to register the agent on-chain so any AI can discover and interact with it

**Everything is Python. No TypeScript/Node.js required.**

Based on the [Ethereum Foundation tutorial](https://ai.ethereum.foundation/blog/how-to-register-an-mcp-server-using-erc-8004) by @VittoStack and @Marcello_AI.

```
┌─────────────┐     HTTP      ┌─────────────────┐   streamable-http   ┌────────┐   tunnel   ┌───────┐
│  Tumbller    │◄────────────►│  FastMCP Server  │◄───────────────────►│ ngrok  │◄─────────►│ AI /  │
│  ESP32-S3    │  (WiFi LAN)  │  (Python)        │    localhost:8000   │        │  public   │ Agent │
│  port 80     │              │                  │                     │        │  URL      │       │
└─────────────┘              └─────────────────┘                     └────────┘           └───────┘
                                      │                                  │
                                      │ setMCP(url)                      │
                                      │ auto-discovers                   ▼
                                      │ tools/resources/prompts ┌──────────────────┐
                                      └────────────────────────►│  ERC-8004        │
                                                                │  Identity        │
                                                                │  Registry        │
                                                                │  (Eth Sepolia)   │
                                                                │  + IPFS (Pinata) │
                                                                └──────────────────┘
```

---

## 1. Architecture

### Components

| Component | Role | Tech |
|-----------|------|------|
| **Tumbller ESP32-S3** | Physical robot, HTTP API on port 80 | C++/Arduino, FreeRTOS |
| **FastMCP Server** | Wraps robot HTTP API as MCP tools | Python, `fastmcp`, `httpx` |
| **ngrok** | Tunnels MCP server to public URL | `pyngrok` or CLI |
| **Agent0 SDK** | Registers agent on ERC-8004, discovery, reputation | Python, `agent0_sdk` |
| **Pinata / IPFS** | Hosts the registration JSON (agent card) | Decentralized storage |

### Data Flow

**Registration (one-time):**
1. Start FastMCP server locally with all Tumbller tools
2. ngrok tunnels it to a public URL
3. `agent0_sdk` calls `agent.setMCP(ngrok_url)` which **auto-queries** the MCP server to discover all tools, resources, and prompts
4. `agent.registerIPFS()` uploads the registration JSON to IPFS via Pinata and mints an ERC-721 NFT on the Identity Registry

**Discovery (by other agents/users):**
1. AI client calls `sdk.searchAgents(mcp=True)` to find agents with MCP tools
2. Or calls `sdk.getAgent("11155111:<agentId>")` for a known agent
3. Fetches `tokenURI` → IPFS JSON → extracts MCP endpoint URL
4. Connects to MCP server via `streamable-http` transport
5. Calls tools, gets results from the physical robot

**Reputation:**
1. After using the agent, clients call `sdk.giveFeedback()` with a score (0-100) and tags
2. Feedback is stored on-chain + optionally off-chain (IPFS) for rich context
3. Other agents can query reputation before deciding to use the service

---

## 2. On-Chain Robot Classification

Robots are classified using **on-chain metadata** stored directly on the Identity Registry NFT via `setMetadata(agentId, key, value)`. This enables filtering and discovery without fetching IPFS files.

### Metadata Keys

| Key | Value (Tumbller) | Description |
|-----|------------------|-------------|
| `agent_type` | `robot` | Top-level category — distinguishes physical robots from software-only agents |
| `robot_type` | `differential_drive` | Locomotion/platform type (see taxonomy below) |
| `fleet_provider` | `yakrover` | Organization / provider operating the fleet |
| `fleet_domain` | `yakrover.com/finland` | Fleet domain path — groups robots by provider and region |

`agent_type=robot` is the **main category**. All physical robots share this tag regardless of platform. The `fleet_provider` identifies who operates the fleet, and `fleet_domain` scopes robots by provider and region for discovery and orchestration.

### Robot Type Taxonomy

As we register more robots, `robot_type` values form a consistent taxonomy:

| `robot_type` | Description | Example Platforms |
|--------------|-------------|-------------------|
| `differential_drive` | Two-wheeled, skid-steer | Tumbller, TurtleBot |
| `quadrotor` | Four-rotor aerial drone | DJI Tello, Crazyflie |
| `fixed_wing` | Fixed-wing aerial drone | ArduPilot plane |
| `quadruped` | Four-legged walker | Spot, Unitree Go2 |
| `manipulator` | Robotic arm / gripper | UR5, Franka |
| `omnidirectional` | Mecanum/omni-wheel base | KUKA youBot |
| `tracked` | Tank-tread drive | Clearpath Jackal |
| `humanoid` | Bipedal humanoid | Atlas, Optimus |

This taxonomy is **convention, not enforced by the contract**. Any string value works. The table above is the recommended set for interoperability.

### Off-Chain Metadata (optional)

OASF domain classification via `agent.addDomain()` can optionally be added to the IPFS registration file for indexing by the Agent0 subgraph. This is not required — on-chain metadata above is the primary classification mechanism.

---

## 3. FastMCP Server — MCP Tools

The MCP server exposes 3 tools: movement, info, and environment sensing. The robot's base URL (e.g. `http://finland-tumbller-01.local`) is configured via environment variable.

| Tool Name | Parameters | Maps To | Description |
|-----------|-----------|---------|-------------|
| `move` | `direction`: forward, back, left, right, stop | `GET /motor/{direction}` | Move the robot. Forward/back auto-stop after 2s, left/right after 1s, stop is immediate. |
| `is_robot_online` | *(none)* | `GET /info` | Check if the robot is online (hides internal IP) |
| `get_temperature_humidity` | *(none)* | `GET /sensor/ht` | Read temperature (C) and humidity (%) from onboard SHT3x sensor |

---

## 4. File Structure

```
tumbller-agent/
├── docs/
│   └── PLAN.md                  # This document
├── src/
│   ├── server.py                # FastMCP server — tool definitions + entrypoint
│   ├── tumbller_client.py       # HTTP client wrapper for robot API
│   ├── register_agent.py        # ERC-8004 registration via agent0_sdk
│   ├── discover_robot_agent.py   # Discover robot agents by on-chain metadata
│   └── generate_wallet.py       # Generate Ethereum wallet + private key
├── .env.example                 # Environment variable template
└── pyproject.toml               # Python project config (uv/pip)
```

No manual `agent-card.json` needed — the Agent0 SDK auto-builds the registration file by querying the live MCP server.

---

## 5. Implementation Steps

### Phase 1: FastMCP Server

**Step 1.1 — Project setup**
```bash
cd C:\Users\rovermaker\Documents\source\tumbller-agent
uv init
uv add fastmcp httpx python-dotenv pyngrok web3
```

**Step 1.2 — Tumbller HTTP client** (`src/tumbller_client.py`)

A thin async wrapper around the robot's HTTP API:

```python
import httpx
import os

class TumbllerClient:
    def __init__(self):
        self.base_url = os.getenv("TUMBLLER_URL", "http://finland-tumbller-01.local")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=5.0)

    async def get(self, path: str) -> dict:
        resp = await self.client.get(path)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"status": "ok", "body": resp.text}
```

> **Note:** The `/motor/*` endpoints return `Content-type: text/html` with a plain text body (not JSON). The `try/except` fallback is required to handle these responses gracefully.

**Step 1.3 — MCP server** (`src/server.py`)

```python
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from typing import Literal
from dotenv import load_dotenv
from fastmcp import FastMCP
from tumbller_client import TumbllerClient

load_dotenv()

mcp = FastMCP(
    name="Tumbller Self-Balancing Robot",
    instructions="Control and monitor a Tumbller ESP32-S3 self-balancing robot",
)
robot = TumbllerClient()

@mcp.tool
async def move(direction: Literal["forward", "back", "left", "right", "stop"]) -> dict:
    """Move the robot in a given direction.
    forward/back auto-stop after 2 seconds, left/right after 1 second,
    stop halts motors immediately."""
    return await robot.get(f"/motor/{direction}")

@mcp.tool
async def is_robot_online() -> dict:
    """Check if the robot is online and reachable."""
    try:
        await robot.get("/info")
        return {"online": True}
    except Exception:
        return {"online": False}

@mcp.tool
async def get_temperature_humidity() -> dict:
    """Read temperature (C) and humidity (%) from the onboard SHT3x sensor."""
    return await robot.get("/sensor/ht")

if __name__ == "__main__":
    port = 8000
    if "--ngrok" in sys.argv:
        from tunnel import start_tunnel
        start_tunnel(port)
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
```

**Step 1.4 — Wallet generator** (`src/generate_wallet.py`)

Generate a fresh Ethereum wallet for testnet registration (never reuse a wallet with real funds):

```python
"""Generate an Ethereum wallet for ERC-8004 registration."""

from web3 import Web3

w3 = Web3()
account = w3.eth.account.create()

print("=== New Ethereum Wallet ===")
print(f"Address:     {account.address}")
print(f"Private Key: {account.key.hex()}")
print()
print("Next steps:")
print(f"  1. Fund with Sepolia ETH: https://www.alchemy.com/faucets/ethereum-sepolia")
print(f"  2. Add to .env:  SIGNER_PVT_KEY={account.key.hex()}")
```

Run it:
```bash
uv run src/generate_wallet.py
```

**Step 1.5 — Environment config** (`.env.example`)
```
# Robot
TUMBLLER_URL=http://finland-tumbller-01.local

# ngrok (free static domain from https://dashboard.ngrok.com/domains)
NGROK_AUTHTOKEN=
NGROK_DOMAIN=your-name-here.ngrok-free.dev

# ERC-8004 Registration (Ethereum Sepolia)
RPC_URL=https://ethereum-sepolia-rpc.publicnode.com
SIGNER_PVT_KEY=
PINATA_JWT=
```

### Phase 2: ngrok Static Tunnel

Every free ngrok account gets a **permanent static domain** on `ngrok-free.dev`.
This means the on-chain registration URL never changes between restarts.

Claim yours at: **ngrok Dashboard > Universal Gateway > Domains**

**Step 2.1 — Tunnel with static domain** (CLI)

```bash
ngrok http 8000 --url=your-name-here.ngrok-free.dev
```

**Step 2.2 — Tunnel from Python** (integrated into `src/server.py`)

```python
from pyngrok import ngrok, conf
import os

def start_tunnel(port: int = 8000) -> str:
    ngrok.set_auth_token(os.getenv("NGROK_AUTHTOKEN"))
    domain = os.getenv("NGROK_DOMAIN")
    tunnel = ngrok.connect(
        addr=str(port),
        proto="http",
        hostname=domain,
    )
    public_url = f"https://{domain}"
    print(f"ngrok tunnel: {public_url}")
    return public_url
```

**Step 2.3 — Integrate into server startup**

The server entrypoint will:
1. Start the ngrok tunnel on the static domain
2. Print the permanent public URL
3. Start the FastMCP server on the tunneled port

Since the URL is static, on-chain registration only needs to happen **once**.

### Phase 3: ERC-8004 Registration (Agent0 Python SDK)

Uses the [`agent0_sdk`](https://sdk.ag0.xyz/docs) Python package — the same SDK used in the
[Ethereum Foundation tutorial](https://ai.ethereum.foundation/blog/how-to-register-an-mcp-server-using-erc-8004).

```bash
uv add agent0_sdk
```

**Key insight**: when you call `agent.setMCP(url)`, the SDK **automatically queries the live MCP
server** and populates `mcpTools`, `mcpResources`, and `mcpPrompts` in the registration file.
No manual agent-card.json needed.

**Step 3.1 — Registration script** (`src/register_agent.py`)

```python
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

# --- Configure capabilities ---
# setMCP auto-discovers tools, resources, and prompts from the live server
ngrok_domain = os.environ["NGROK_DOMAIN"]
agent.setMCP(f"https://{ngrok_domain}/mcp")

agent.setTrust(reputation=True)
agent.setActive(True)
agent.setX402Support(False)

# --- Register on-chain + upload to IPFS ---
# ⚠️ Run only once! This mints an NFT on the Identity Registry.
reg_file = agent.registerIPFS()
print(f"Agent registered on Ethereum Sepolia!")
print(f"Registration file:\n{reg_file}")

# --- Store robot classification on-chain ---
# These key-value pairs are stored directly on the Identity Registry NFT.
# They enable filtering/discovery by robot type and fleet membership.
agent_id = reg_file["registrations"][0]["agentId"]
sdk.identity_registry.functions.setMetadata(
    agent_id, "agent_type", b"robot"
).transact()
sdk.identity_registry.functions.setMetadata(
    agent_id, "robot_type", b"differential_drive"
).transact()
sdk.identity_registry.functions.setMetadata(
    agent_id, "fleet_provider", b"yakrover"
).transact()
sdk.identity_registry.functions.setMetadata(
    agent_id, "fleet_domain", b"yakrover.com/finland"
).transact()
print(f"On-chain metadata set: agent_type=robot, robot_type=differential_drive, fleet_provider=yakrover, fleet_domain=yakrover.com/finland")
```

**Expected output** (the SDK auto-populates `mcpTools` etc.):
```json
{
  "type": "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
  "name": "Tumbller Self-Balancing Robot",
  "description": "A physical ESP32-S3 two-wheeled robot ...",
  "endpoints": [
    {
      "name": "MCP",
      "endpoint": "https://your-name-here.ngrok-free.dev/mcp",
      "version": "2025-06-18",
      "mcpTools": [
        "move", "is_robot_online", "get_temperature_humidity"
      ],
      "mcpResources": [],
      "mcpPrompts": []
    }
  ],
  "registrations": [
    {
      "agentId": "<assigned_id>",
      "agentRegistry": "eip155:11155111:{identityRegistry}"
    }
  ],
  "supportedTrust": ["reputation"],
  "active": true,
  "x402support": false
}
```

### Phase 4: Discovery — How Others Find and Use the Tumbller

This is the consumer-side flow. Any developer can discover and use the Tumbller
agent with just `agent0_sdk` and a Sepolia RPC URL (read-only, no wallet needed).

**Step 4.1 — Search for MCP agents on-chain**

```python
from agent0_sdk import SDK

sdk = SDK(chainId=11155111, rpcUrl="https://ethereum-sepolia-rpc.publicnode.com")

# Find all agents that expose MCP tools
results = sdk.searchAgents(mcp=True, page_size=50)

for agent in results["items"]:
    if agent["mcpTools"]:
        print(f"{agent['name']} ({agent['agentId']})")
        print(f"  Tools: {agent['mcpTools']}")
```

**Step 4.2 — Get a specific agent and its MCP URL**

```python
# Get agent summary (no MCP URL here, just metadata)
summary = sdk.getAgent("11155111:<agentId>")
print(summary)

# To get the actual MCP URL, fetch the tokenURI → IPFS registration JSON
token_id = <agentId>
token_uri = sdk.identity_registry.functions.tokenURI(token_id).call()

import requests
ipfs_url = "https://dweb.link/ipfs/" + token_uri.split("//")[1]
registration = requests.get(ipfs_url).json()

# Extract MCP endpoint
mcp_url = next(
    ep["endpoint"]
    for ep in registration.get("endpoints", [])
    if ep.get("name") == "MCP"
)
print(f"MCP URL: {mcp_url}")
```

**Step 4.3 — Use discovered MCP tools with LangChain**

```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent

client = MultiServerMCPClient({
    "tumbller": {
        "transport": "http",
        "url": mcp_url,  # from step 4.2
    }
})

tool_list = await client.get_tools()
agent = create_agent(model="openai:gpt-4", tools=tool_list)

result = await agent.ainvoke({
    "messages": [{"role": "user", "content": "Move the robot forward, then tell me the temperature."}]
})
```

**Step 4.4 — Use directly with Claude Desktop**

```json
{
  "mcpServers": {
    "tumbller": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Phase 5: Reputation — Building Trust On-Chain

After interacting with the Tumbller agent, users can submit on-chain feedback.

**Step 5.1 — Submit feedback**

```python
# SDK needs a signer for write operations
user_sdk = SDK(
    chainId=11155111,
    rpcUrl=os.environ["RPC_URL"],
    signer=os.environ["SIGNER_PVT_KEY"],
    ipfs="pinata",
    pinataJwt=os.environ["PINATA_JWT"],
)

# Prepare rich off-chain feedback (stored on IPFS)
feedback_file = user_sdk.prepareFeedbackFile({
    "text": "Robot moved as expected. Sensor readings were accurate.",
    "capability": "tools",
    "name": "move",
    "context": {
        "use_case": "robot_remote_control",
        "integration": "claude_desktop",
        "environment": "local_network",
    },
})

# Submit on-chain feedback (score 0-100)
feedback = user_sdk.giveFeedback(
    agentId="11155111:<agentId>",
    value=90,
    tag1="robotics",
    tag2="mcp_tools",
    feedbackFile=feedback_file,
)
print(f"Feedback submitted: {feedback}")
```

**Step 5.2 — View feedback on explorers**

- [8004scan.io](https://8004scan.io) — browse agent registrations, reputation scores
- [8004agents.ai](https://8004agents.ai) — multichain agent directory

### Phase 6: Testing Checklist

| Test | Command | Expected |
|------|---------|----------|
| Generate wallet | `uv run src/generate_wallet.py` | Address + private key printed |
| Local MCP server | `uv run src/server.py` | Server on :8000 |
| FastMCP inspector | `fastmcp dev src/server.py` | Browser UI at :6274 |
| ngrok static tunnel | `ngrok http 8000 --url=$NGROK_DOMAIN` | Static domain live |
| Registration | `uv run src/register_agent.py` | Agent ID printed |
| On-chain query | `sdk.getAgent("11155111:<id>")` | Agent summary returned |
| Tool discovery | `sdk.searchAgents(mcp=True)` | Tumbller in results |
| Claude Desktop | Add to MCP config | Tools appear in Claude |

---

## 6. Python Dependencies

All managed via `uv` / `pyproject.toml`:

| Package | Purpose |
|---------|---------|
| `fastmcp` | MCP server framework (tools, resources, prompts) |
| `httpx` | Async HTTP client (robot API calls) |
| `python-dotenv` | Load .env files |
| `pyngrok` | ngrok tunnel from Python |
| `web3` | Ethereum wallet generation + RPC interaction |
| `agent0_sdk` | ERC-8004 registration, discovery, reputation |

Optional for discovery/LangChain integration:
| Package | Purpose |
|---------|---------|
| `langchain-mcp-adapters` | Use MCP tools in LangChain agents |
| `langchain-openai` | OpenAI LLM for LangChain agents |

---

## 7. Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TUMBLLER_URL` | Yes | Robot HTTP base URL (e.g. `http://finland-tumbller-01.local`) |
| `NGROK_AUTHTOKEN` | For tunnel | ngrok authentication token |
| `NGROK_DOMAIN` | For tunnel | Free static domain (e.g. `your-name-here.ngrok-free.dev`) |
| `RPC_URL` | For registration | Ethereum Sepolia RPC (e.g. `https://ethereum-sepolia-rpc.publicnode.com`) |
| `SIGNER_PVT_KEY` | For registration | Ethereum wallet private key (generate with `generate_wallet.py`) |
| `PINATA_JWT` | For registration | Pinata IPFS JWT token |

---

## 8. Prerequisites

| Requirement | Purpose |
|-------------|---------|
| Python 3.11+ | All code |
| uv | Python package manager |
| ngrok account | Public tunnel (free tier works) |
| Sepolia ETH | Gas for on-chain registration (free from faucet) |
| Pinata account | IPFS hosting for agent card (free tier works) |
| Tumbller robot on WiFi | Physical robot accessible on LAN |

---

## 9. Security Notes

- The MCP server has **full control** of the physical robot. In production, add authentication middleware.
- The `.env` file contains secrets (private key, API tokens). Never commit it.
- Use `generate_wallet.py` to create a **dedicated testnet wallet**. Never use a wallet holding real funds.
- The ngrok static domain is permanent but publicly accessible — anyone with the URL can control the robot.
- Tool descriptions and annotations are not inherently trustworthy — ERC-8004 feedback provides the actual trust signal.

---

## 10. Future Enhancements

- **x402 micropayments**: Charge per tool call using USDC (`agent.setX402Support(True)`)
- **Custom domain**: Use a custom domain via ngrok or fastmcp.cloud
- **Streaming telemetry**: MCP resource subscriptions for real-time angle/speed data
- **Automated reputation**: Server-side feedback collection based on tool call success/failure rates
- **Multi-agent**: Add A2A protocol endpoint (`agent.setA2A(url)`) for agent-to-agent orchestration
- **LangChain agent**: Build a LangChain agent that discovers the Tumbller from ERC-8004 and controls it autonomously

---

## References

- [EIP-8004: Trustless Agents Specification](https://eips.ethereum.org/EIPS/eip-8004)
- [How to Register an MCP Server Using ERC-8004](https://ai.ethereum.foundation/blog/how-to-register-an-mcp-server-using-erc-8004) — EF tutorial by @VittoStack & @Marcello_AI
- [Agent0 SDK Documentation](https://sdk.ag0.xyz/docs) — `pip install agent0_sdk`
- [FastMCP — Python MCP Framework](https://gofastmcp.com/) — `pip install fastmcp`
- [8004scan.io](https://8004scan.io) — On-chain agent explorer
- [ERC-8004 Contracts](https://github.com/erc-8004/erc-8004-contracts)
- [ngrok Free Static Domains](https://ngrok.com/blog/free-static-domains-ngrok-users) — Permanent URL for free accounts
- [Awesome ERC-8004](https://github.com/sudeepb02/awesome-erc8004) — Curated resource list
