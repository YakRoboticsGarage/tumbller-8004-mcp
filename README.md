# tumbller-agent

Register a physical robot as an on-chain AI agent using [ERC-8004](https://eips.ethereum.org/EIPS/eip-8004) and expose its capabilities via MCP.

This project wraps a Tumbller ESP32-S3 self-balancing robot's HTTP API as an MCP server and registers it on Ethereum Sepolia so other agents can discover and interact with it.

## Architecture

```
Claude / AI Client
        |
        | MCP (streamable-http)
        v
  FastMCP Server (port 8000)
        |
        | ngrok tunnel
        v
  Public URL (*.ngrok-free.dev/mcp)
        |
        | registered on-chain
        v
  ERC-8004 Identity Registry (Sepolia)
        |
        | tokenURI -> IPFS
        v
  Agent Card JSON (Pinata/IPFS)
```

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- An ESP32 robot with HTTP API (or any HTTP-controllable device)
- Sepolia ETH for gas (free from [faucet](https://www.alchemy.com/faucets/ethereum-sepolia))
- [Pinata](https://www.pinata.cloud/) account (free tier) for IPFS uploads
- [ngrok](https://ngrok.com/) account (free tier) for public tunnel

## Quick Start

### 1. Clone and install

```bash
git clone <repo-url>
cd tumbller-agent
uv sync --prerelease=allow
```

> `--prerelease=allow` is required because `agent0_sdk` depends on `ipfshttpclient>=0.8.0a2`.

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

| Variable | Description |
|----------|-------------|
| `TUMBLLER_URL` | Robot's local HTTP address (e.g. `http://my-robot.local`) |
| `NGROK_AUTHTOKEN` | From [ngrok dashboard](https://dashboard.ngrok.com/get-started/your-authtoken) |
| `NGROK_DOMAIN` | Free static domain from [ngrok domains](https://dashboard.ngrok.com/domains) |
| `RPC_URL` | Ethereum Sepolia RPC (default: `https://ethereum-sepolia-rpc.publicnode.com`) |
| `WALLET_ADDRESS` | Your Ethereum address (auto-generated in step 3) |
| `SIGNER_PVT_KEY` | Private key for signing transactions (auto-generated in step 3) |
| `PINATA_JWT` | JWT token from [Pinata API Keys](https://app.pinata.cloud/developers/api-keys) |

### 3. Generate a wallet

```bash
uv run python src/generate_wallet.py --new
```

This creates an Ethereum keypair and saves it to `.env`. Fund it with Sepolia ETH from a faucet.

### 4. Start the MCP server

```bash
# Local only (for testing with Claude Code)
uv run python src/server.py

# With ngrok tunnel (for public access and registration)
uv run python src/server.py --ngrok
```

The server runs on `http://localhost:8000/mcp` using MCP streamable-http transport.

### 5. Test with Claude Code

Add the MCP server to Claude Code:

```bash
claude mcp add --transport http tumbller http://localhost:8000/mcp
```

Then in a Claude Code session, ask Claude to move the robot or check its temperature.

### 6. Register on ERC-8004

With the MCP server running (with `--ngrok`):

```bash
uv run python src/register_agent.py
```

This will:
1. Create an agent with name, description, and MCP endpoint
2. Declare MCP tools: `move`, `is_robot_online`, `get_temperature_humidity`
3. Set on-chain metadata: `category=robot`, `robot_type`, `fleet_provider`, `fleet_domain`
4. Upload the agent card JSON to IPFS via Pinata
5. Mint an ERC-721 NFT on the Identity Registry and set the tokenURI to the IPFS hash

Output:
```
Agent registered on Ethereum Sepolia!
Agent ID: 11155111:989
Agent URI: ipfs://bafkrei...
```

### 7. Discover registered robots

```bash
uv run python src/discover_robot_agent.py
```

Searches all agents with `category=robot` metadata on Sepolia and displays their tools and fleet info.

## Registering Your Own Robot

To register a different robot, modify these files:

### server.py - Define your MCP tools

Replace the tool functions with your robot's capabilities:

```python
@mcp.tool
async def move(direction: Literal["forward", "back", "left", "right", "stop"]) -> dict:
    """Move the robot."""
    return await robot.get(f"/motor/{direction}")

@mcp.tool
async def my_custom_sensor() -> dict:
    """Read a custom sensor."""
    return await robot.get("/sensor/custom")
```

### register_agent.py - Update metadata

Change the agent name, description, and metadata to match your robot:

```python
agent = sdk.createAgent(
    name="My Robot Name",
    description="Description of your robot's capabilities (50-500 chars).",
)

# Update the tool list to match your server.py
mcp_ep.meta["mcpTools"] = ["move", "my_custom_sensor"]

# Set your classification metadata
agent.setMetadata({
    "category": "robot",                    # ERC-8004 reserved key
    "robot_type": "differential_drive",     # your robot type
    "fleet_provider": "your-org",           # your organization
    "fleet_domain": "your-domain.com",      # fleet management domain
})
```

### On-chain metadata keys

| Key | Type | Description |
|-----|------|-------------|
| `category` | ERC-8004 reserved | Classification tag. Use `robot` for physical robots |
| `robot_type` | Custom | Robot locomotion type (e.g. `differential_drive`, `quadruped`, `arm`) |
| `fleet_provider` | Custom | Organization managing the robot fleet |
| `fleet_domain` | Custom | Domain for fleet management services |

See [ERC-8004 best practices](https://best-practices.8004scan.io/docs/01-agent-metadata-standard.html) for the full metadata standard.

## Updating an Existing Registration

To update the IPFS metadata or MCP tools after registration:

```bash
uv run python src/update_agent.py
```

To fix on-chain metadata keys separately (avoids nonce issues):

```bash
uv run python src/fix_metadata.py
```

## Project Structure

```
src/
  server.py                 # FastMCP server with robot tools
  tumbller_client.py        # Async HTTP client for robot API
  tunnel.py                 # ngrok tunnel helper
  register_agent.py         # ERC-8004 registration (first time)
  update_agent.py           # Update existing registration
  fix_metadata.py           # Fix on-chain metadata keys
  discover_robot_agent.py   # Find registered robot agents
  generate_wallet.py        # Ethereum wallet generator
docs/
  PLAN.md                   # Architecture and implementation plan
  CHANGELOG.md              # Release notes
```

## Known Limitations

- **SDK auto-discovery broken**: The `agent0_sdk` EndpointCrawler doesn't support MCP streamable-http transport. Tools must be declared manually via `mcp_ep.meta["mcpTools"]` with `auto_fetch=False`.
- **Subgraph indexing delay**: The Graph may take time to re-index after on-chain updates. The discover script falls back to direct IPFS fetch for MCP tools.
- **Nonce race conditions**: The SDK's `registerIPFS()` can hit nonce errors when submitting metadata transactions immediately after the main transaction. Use `fix_metadata.py` for separate metadata updates.

## Links

- [ERC-8004 Specification](https://eips.ethereum.org/EIPS/eip-8004)
- [8004scan Best Practices](https://best-practices.8004scan.io)
- [agent0_sdk](https://pypi.org/project/agent0-sdk/)
- [FastMCP](https://pypi.org/project/fastmcp/)
- [MCP Specification](https://spec.modelcontextprotocol.io)
