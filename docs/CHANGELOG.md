# Changelog

All notable changes to the tumbller-agent project are documented here.

## [0.1.0] - 2026-02-08

### Added
- FastMCP server (`server.py`) with streamable-http transport exposing 3 tools:
  - `move` - drive the robot forward/back/left/right/stop
  - `is_robot_online` - check robot reachability (hides internal IP)
  - `get_temperature_humidity` - read SHT3x sensor data
- Async HTTP client (`tumbller_client.py`) wrapping the ESP32 robot's REST API
- ngrok tunnel integration (`tunnel.py`) for public MCP access via static free domain
- ERC-8004 on-chain registration (`register_agent.py`) on Ethereum Sepolia
  - Agent ID: `11155111:989`
  - IPFS metadata via Pinata
  - MCP tools declared manually (`auto_fetch=False`) due to SDK/streamable-http incompatibility
- On-chain metadata using ERC-8004 reserved key `category=robot` plus custom keys:
  `robot_type`, `fleet_provider`, `fleet_domain`
- Robot agent discovery script (`discover_robot_agent.py`) with IPFS fallback for MCP tools
- Agent update script (`update_agent.py`) for modifying IPFS metadata and on-chain URI
- Metadata migration script (`fix_metadata.py`) for one-off on-chain key changes
- Ethereum wallet generator (`generate_wallet.py`) with `.env` integration
- Environment config via `.env` / `.env.example`

### Known Issues
- `agent0_sdk` EndpointCrawler does not support MCP streamable-http transport; tools must be set manually via `mcp_ep.meta["mcpTools"]`
- The Graph subgraph may lag behind on-chain state; discover script falls back to direct IPFS fetch for MCP tools
- SDK `registerIPFS()` can hit nonce race conditions when updating metadata in the same transaction batch
