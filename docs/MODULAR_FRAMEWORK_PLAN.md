# Modular Robot MCP Framework — Design Plan

## 1. Problem Statement

Two robot repos (`tumbller-8004-mcp` and `tello-8004-mcp`) share ~80% identical code:

| File | Shared? | Robot-specific parts |
|------|---------|---------------------|
| `tunnel.py` | 100% identical | — |
| `discover_robot_agent.py` | 100% identical | — |
| `generate_wallet.py` | 100% identical | — |
| `register_agent.py` | Same structure | name, description, tool list, metadata values |
| `update_agent.py` | Same structure | agent ID, tool list |
| `fix_metadata.py` | Same structure | agent ID, metadata values |
| `server.py` | Same scaffolding | tool definitions, client class |
| `*_client.py` | — | 100% robot-specific |

Adding a third robot (e.g., a robotic arm) would mean copy-pasting the entire repo again and changing the same small set of values. This doesn't scale.

**Goals:**
1. One generic repo that works for any robot with minimal per-robot glue code
2. A plugin system where each robot type is a self-contained module declaring its affordances
3. The `discover_robot_agent` script exposed as an MCP tool so LLMs can discover and reason about available robots at runtime

---

## 2. Proposed Repository Structure

```
robot-fleet-mcp/
├── pyproject.toml                     # Core deps + optional extras per robot
├── .env.example
├── README.md
├── src/
│   ├── core/                          # Shared infrastructure (never changes per robot)
│   │   ├── __init__.py
│   │   ├── server.py                  # Generic MCP server bootstrap + plugin loader
│   │   ├── tunnel.py                  # ngrok tunnel (unchanged)
│   │   ├── discovery.py               # Robot discovery (from discover_robot_agent.py)
│   │   ├── registration.py            # Generic ERC-8004 register/update/fix
│   │   ├── wallet.py                  # Wallet generation (unchanged)
│   │   └── plugin.py                  # Plugin base class + registry
│   │
│   └── robots/                        # One sub-package per robot type
│       ├── __init__.py                # Robot registry auto-discovery
│       ├── tumbller/
│       │   ├── __init__.py            # Plugin registration entry point
│       │   ├── client.py              # TumbllerClient (unchanged)
│       │   └── tools.py               # MCP tool definitions (from server.py)
│       │
│       ├── tello/
│       │   ├── __init__.py
│       │   ├── client.py              # TelloClient (unchanged)
│       │   └── tools.py               # MCP tool definitions (from server.py)
│       │
│       └── _template/                 # Copyable template for new robots
│           ├── __init__.py
│           ├── client.py
│           └── tools.py
│
├── scripts/                           # CLI entry points
│   ├── serve.py                       # Start MCP server for one or more robots
│   ├── register.py                    # Register a robot on-chain
│   ├── discover.py                    # CLI wrapper for discovery
│   └── generate_wallet.py            # Wallet generation CLI
│
└── docs/
    ├── ADDING_A_ROBOT.md             # Step-by-step guide for contributors
    └── ARCHITECTURE.md
```

---

## 3. Plugin System Design

### 3.1. Plugin Base Class

Each robot plugin implements a single class that declares everything the framework needs:

```python
# src/core/plugin.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from fastmcp import FastMCP


@dataclass
class RobotMetadata:
    """On-chain classification for ERC-8004 registration."""
    name: str                          # e.g. "Tumbller Self-Balancing Robot"
    description: str                   # Human-readable description
    robot_type: str                    # e.g. "differential_drive", "quadrotor"
    fleet_provider: str = ""           # e.g. "yakrover"
    fleet_domain: str = ""             # e.g. "yakrover.com/finland"
    image: str = ""                    # Optional image URL


class RobotPlugin(ABC):
    """Base class for all robot plugins.

    A plugin is responsible for:
    1. Declaring its metadata (name, type, fleet info)
    2. Registering its MCP tools on a FastMCP server instance
    3. Providing its tool names for on-chain registration
    """

    @abstractmethod
    def metadata(self) -> RobotMetadata:
        """Return the robot's on-chain metadata."""
        ...

    @abstractmethod
    def register_tools(self, mcp: FastMCP) -> None:
        """Register this robot's MCP tools on the shared server.

        Use @mcp.tool to register each tool function.
        The plugin owns its client lifecycle internally.
        """
        ...

    @abstractmethod
    def tool_names(self) -> list[str]:
        """Return the list of MCP tool names this plugin registers.

        Must match the function names passed to @mcp.tool exactly.
        Used for on-chain registration in the mcpTools field.
        """
        ...
```

### 3.2. Example Plugin Implementation (Tumbller)

```python
# src/robots/tumbller/__init__.py

from core.plugin import RobotPlugin, RobotMetadata

class TumbllerPlugin(RobotPlugin):
    def metadata(self) -> RobotMetadata:
        return RobotMetadata(
            name="Tumbller Self-Balancing Robot",
            description="A physical ESP32-S3 two-wheeled robot controllable via MCP.",
            robot_type="differential_drive",
            fleet_provider="yakrover",
            fleet_domain="yakrover.com/finland",
        )

    def tool_names(self) -> list[str]:
        return ["tumbller_move", "tumbller_is_online", "tumbller_get_temperature_humidity"]

    def register_tools(self, mcp):
        from .client import TumbllerClient
        from .tools import register
        register(mcp, TumbllerClient())
```

```python
# src/robots/tumbller/tools.py

from typing import Literal
from fastmcp import FastMCP
from .client import TumbllerClient


def register(mcp: FastMCP, robot: TumbllerClient) -> None:
    """Register Tumbller MCP tools on the server."""

    @mcp.tool
    async def tumbller_move(direction: Literal["forward", "back", "left", "right", "stop"]) -> dict:
        """Move the Tumbller robot in a given direction."""
        return await robot.get(f"/motor/{direction}")

    @mcp.tool
    async def tumbller_is_online() -> dict:
        """Check if the Tumbller robot is online and reachable."""
        try:
            await robot.get("/info")
            return {"online": True}
        except Exception:
            return {"online": False}

    @mcp.tool
    async def tumbller_get_temperature_humidity() -> dict:
        """Read temperature (C) and humidity (%) from the Tumbller's SHT3x sensor."""
        return await robot.get("/sensor/ht")
```

### 3.3. Tool Naming Convention

When multiple robots are loaded into a single MCP server, tool names must be globally unique. Convention:

```
{robot_type_short}_{action}
```

Examples:
- `tumbller_move`, `tumbller_is_online`
- `tello_takeoff`, `tello_move`, `tello_get_status`

If only one robot is loaded (single-robot mode), the prefix can be omitted for backward compatibility.

### 3.4. Plugin Auto-Discovery

```python
# src/robots/__init__.py

import importlib
import pkgutil
from core.plugin import RobotPlugin

def discover_plugins() -> dict[str, type[RobotPlugin]]:
    """Scan src/robots/ for packages that export a RobotPlugin subclass."""
    plugins = {}
    package = importlib.import_module("robots")
    for importer, modname, ispkg in pkgutil.iter_modules(package.__path__):
        if not ispkg or modname.startswith("_"):
            continue
        mod = importlib.import_module(f"robots.{modname}")
        for attr in dir(mod):
            obj = getattr(mod, attr)
            if isinstance(obj, type) and issubclass(obj, RobotPlugin) and obj is not RobotPlugin:
                plugins[modname] = obj
    return plugins
```

This means adding a new robot is: create a package under `src/robots/`, implement the three methods, done.

---

## 4. Generic MCP Server

### 4.1. Server Bootstrap

```python
# src/core/server.py

import sys
import os
from dotenv import load_dotenv
from fastmcp import FastMCP
from core.plugin import RobotPlugin

load_dotenv()


def create_server(plugins: list[RobotPlugin]) -> FastMCP:
    """Create a FastMCP server with the given robot plugins loaded."""

    # Auth setup (shared across all robots)
    auth = None
    bearer_token = os.getenv("MCP_BEARER_TOKEN")
    if bearer_token:
        from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
        auth = StaticTokenVerifier(
            tokens={bearer_token: {"client_id": "mcp-client", "scopes": []}}
        )

    # Build server name and instructions from loaded plugins
    names = [p.metadata().name for p in plugins]
    mcp = FastMCP(
        name="Robot Fleet MCP" if len(plugins) > 1 else names[0],
        instructions=f"Control and monitor: {', '.join(names)}",
        auth=auth,
    )

    # Register each plugin's tools
    for plugin in plugins:
        plugin.register_tools(mcp)

    # Register discovery tool (always available)
    from core.discovery import register_discovery_tools
    register_discovery_tools(mcp)

    return mcp
```

### 4.2. Serve Script

```python
# scripts/serve.py

"""
Usage:
    # Serve all installed robot plugins
    uv run python scripts/serve.py --ngrok

    # Serve only specific robots
    uv run python scripts/serve.py --robots tumbller tello --ngrok

    # Single robot mode (no tool prefix)
    uv run python scripts/serve.py --robots tello --port 8001
"""

import argparse
from robots import discover_plugins
from core.server import create_server

parser = argparse.ArgumentParser()
parser.add_argument("--robots", nargs="*", help="Robot plugins to load (default: all)")
parser.add_argument("--port", type=int, default=8000)
parser.add_argument("--ngrok", action="store_true")
args = parser.parse_args()

# Discover and filter plugins
all_plugins = discover_plugins()
if args.robots:
    selected = {k: v for k, v in all_plugins.items() if k in args.robots}
else:
    selected = all_plugins

plugins = [cls() for cls in selected.values()]
mcp = create_server(plugins)

if args.ngrok:
    from core.tunnel import start_tunnel
    start_tunnel(args.port)

mcp.run(transport="streamable-http", host="0.0.0.0", port=args.port)
```

### 4.3. Modes of Operation

| Mode | Command | Behavior |
|------|---------|----------|
| **Fleet mode** | `serve.py` | Load all plugins, prefix tool names, single MCP endpoint |
| **Single robot** | `serve.py --robots tello` | Load one plugin, no prefix needed |
| **Multi-select** | `serve.py --robots tumbller tello` | Load specific subset |

---

## 5. Discovery as an MCP Tool

The key addition: `discover_robot_agent.py` becomes an MCP tool that any LLM can call at runtime.

### 5.1. Discovery Tool Implementation

```python
# src/core/discovery.py

from agent0_sdk import SDK
from fastmcp import FastMCP
import requests

IPFS_GATEWAY = "https://ipfs.io/ipfs/"


def _get_sdk() -> SDK:
    return SDK(
        chainId=11155111,
        rpcUrl="https://ethereum-sepolia-rpc.publicnode.com",
    )


def _fetch_ipfs_tools(sdk: SDK, agent_id_int: int) -> list:
    """Fetch MCP tools from IPFS (bypasses subgraph lag)."""
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


def discover_robots(robot_type: str | None = None, fleet_provider: str | None = None) -> list[dict]:
    """Query on-chain registry for robot agents, with optional filters."""
    sdk = _get_sdk()
    results = sdk.searchAgents(hasMetadataKey="category")
    robots = []

    for agent in results:
        agent_id_str = agent.get("agentId") if isinstance(agent, dict) else agent.agentId
        agent_id_int = int(str(agent_id_str).split(":")[-1])

        meta = sdk.identity_registry.functions.getMetadata(agent_id_int, "category").call()
        if meta != b"robot":
            continue

        rtype = sdk.identity_registry.functions.getMetadata(agent_id_int, "robot_type").call()
        provider = sdk.identity_registry.functions.getMetadata(agent_id_int, "fleet_provider").call()
        fleet = sdk.identity_registry.functions.getMetadata(agent_id_int, "fleet_domain").call()

        rtype_str = rtype.decode() if rtype else "unknown"
        provider_str = provider.decode() if provider else ""
        fleet_str = fleet.decode() if fleet else ""

        # Apply optional filters
        if robot_type and rtype_str != robot_type:
            continue
        if fleet_provider and provider_str != fleet_provider:
            continue

        name = agent.get("name") if isinstance(agent, dict) else agent.name
        tools = agent.get("mcpTools", []) if isinstance(agent, dict) else agent.mcpTools
        if not tools:
            tools = _fetch_ipfs_tools(sdk, agent_id_int)

        robots.append({
            "agent_id": agent_id_str,
            "name": name,
            "robot_type": rtype_str,
            "fleet_provider": provider_str,
            "fleet_domain": fleet_str,
            "mcp_tools": tools,
        })

    return robots


def register_discovery_tools(mcp: FastMCP) -> None:
    """Register robot discovery as MCP tools for LLM consumption."""

    @mcp.tool
    async def discover_robot_agents(
        robot_type: str | None = None,
        fleet_provider: str | None = None,
    ) -> dict:
        """Discover robot agents registered on the ERC-8004 identity registry.

        Searches the Ethereum Sepolia blockchain for physical robots that have
        been registered as on-chain agents. Returns their capabilities (MCP tools),
        classification (robot_type), and fleet information.

        Args:
            robot_type: Filter by robot type (e.g. "differential_drive", "quadrotor").
                        Pass None to return all robot types.
            fleet_provider: Filter by fleet operator (e.g. "yakrover").
                           Pass None to return all providers.

        Returns:
            A dict with a "robots" list, each entry containing:
            - agent_id: On-chain identifier
            - name: Human-readable robot name
            - robot_type: Locomotion/form-factor classification
            - fleet_provider: Organization operating the robot
            - fleet_domain: Regional fleet grouping
            - mcp_tools: List of MCP tool names the robot exposes
        """
        robots = discover_robots(robot_type=robot_type, fleet_provider=fleet_provider)
        return {"robots": robots, "count": len(robots)}
```

### 5.2. What This Enables for LLMs

An LLM connected to the fleet MCP server can:

1. **Discover** — call `discover_robot_agents()` to find all available robots on-chain
2. **Filter** — call `discover_robot_agents(robot_type="quadrotor")` to find only drones
3. **Inspect** — read the `mcp_tools` field to understand each robot's affordances
4. **Act** — call the robot's tools directly (e.g. `tello_takeoff`, `tumbller_move`)

This is a single MCP endpoint that gives the LLM both the discovery layer and the control layer.

---

## 6. Generic Registration

### 6.1. Registration Script

```python
# scripts/register.py

"""
Usage:
    uv run python scripts/register.py tumbller
    uv run python scripts/register.py tello
"""

import argparse
from robots import discover_plugins
from core.registration import register_robot

parser = argparse.ArgumentParser()
parser.add_argument("robot", help="Robot plugin name (e.g. tumbller, tello)")
args = parser.parse_args()

plugins = discover_plugins()
if args.robot not in plugins:
    print(f"Unknown robot: {args.robot}. Available: {list(plugins.keys())}")
    exit(1)

plugin = plugins[args.robot]()
register_robot(plugin)
```

### 6.2. Generic Registration Logic

```python
# src/core/registration.py

import os
from dotenv import load_dotenv
from agent0_sdk import SDK
from agent0_sdk.core.models import EndpointType
from core.plugin import RobotPlugin

load_dotenv()


def register_robot(plugin: RobotPlugin) -> None:
    """Register a robot plugin on ERC-8004."""
    meta = plugin.metadata()

    sdk = SDK(
        chainId=11155111,
        rpcUrl=os.environ["RPC_URL"],
        signer=os.environ["SIGNER_PVT_KEY"],
        ipfs="pinata",
        pinataJwt=os.environ["PINATA_JWT"],
    )

    agent = sdk.createAgent(
        name=meta.name,
        description=meta.description,
        image=meta.image,
    )

    ngrok_domain = os.environ["NGROK_DOMAIN"]
    agent.setMCP(f"https://{ngrok_domain}/mcp", auto_fetch=False)

    mcp_ep = next(ep for ep in agent.registration_file.endpoints if ep.type == EndpointType.MCP)
    mcp_ep.meta["mcpTools"] = plugin.tool_names()

    agent.setTrust(reputation=True)
    agent.setActive(True)
    agent.setX402Support(False)

    agent.setMetadata({
        "category": "robot",
        "robot_type": meta.robot_type,
        "fleet_provider": meta.fleet_provider,
        "fleet_domain": meta.fleet_domain,
    })

    print("Submitting registration transaction...")
    tx_handle = agent.registerIPFS()
    print(f"Transaction submitted: {tx_handle.tx_hash}")

    print("Waiting for transaction to be mined...")
    mined = tx_handle.wait_mined(timeout=120)
    reg_file = mined.result

    print(f"\nAgent registered on Ethereum Sepolia!")
    print(f"Agent ID: {reg_file.agentId}")
    print(f"Agent URI: {reg_file.agentURI}")
```

---

## 7. How to Add a New Robot

Adding a new robot (e.g., a robotic arm) requires creating **one directory with three files**:

### Step 1: Create the plugin package

```
src/robots/arm/
├── __init__.py
├── client.py
└── tools.py
```

### Step 2: Implement the client

`client.py` — handles communication with the physical robot (HTTP, UDP, serial, ROS, etc.). This is entirely robot-specific.

### Step 3: Implement the plugin

`__init__.py`:

```python
from core.plugin import RobotPlugin, RobotMetadata

class ArmPlugin(RobotPlugin):
    def metadata(self):
        return RobotMetadata(
            name="6-DOF Robotic Arm",
            description="A 6-axis robotic arm controllable via MCP.",
            robot_type="articulated_arm",
            fleet_provider="yakrover",
            fleet_domain="yakrover.com/finland",
        )

    def tool_names(self):
        return ["arm_move_joint", "arm_go_home", "arm_get_position", "arm_is_online"]

    def register_tools(self, mcp):
        from .client import ArmClient
        from .tools import register
        register(mcp, ArmClient())
```

### Step 4: Implement the tools

`tools.py`:

```python
def register(mcp, arm):
    @mcp.tool
    async def arm_move_joint(joint: int, angle: float) -> dict:
        """Move a joint to a target angle."""
        return await arm.move_joint(joint, angle)

    @mcp.tool
    async def arm_go_home() -> dict:
        """Move all joints to home position."""
        return await arm.go_home()

    # ... more tools
```

### Step 5: Add robot-specific dependencies (if any)

In `pyproject.toml`, add an optional dependency group:

```toml
[project.optional-dependencies]
tumbller = ["httpx>=0.28.1"]
tello = ["djitellopy>=2.5.0"]
arm = ["pyserial>=3.5"]
```

Install with: `uv sync --extra arm`

### That's it.

The framework auto-discovers the plugin, the server loads its tools, and `discover_robot_agents` returns it to any LLM. No framework code changes needed.

---

## 8. Dependency Management

### 8.1. pyproject.toml Structure

```toml
[project]
name = "robot-fleet-mcp"
version = "0.1.0"
description = "Modular MCP framework for multi-robot fleet control and discovery"
requires-python = ">=3.13"

# Core dependencies (always installed)
dependencies = [
    "agent0-sdk>=1.5.2",
    "fastmcp>=2.14.5",
    "pyngrok>=7.5.0",
    "python-dotenv>=1.2.1",
    "web3>=7.14.1",
    "requests>=2.31.0",
]

# Robot-specific dependencies (install only what you need)
[project.optional-dependencies]
tumbller = ["httpx>=0.28.1"]
tello = ["djitellopy>=2.5.0"]
all = ["httpx>=0.28.1", "djitellopy>=2.5.0"]  # everything
```

### 8.2. Install Commands

```bash
# Core only (discovery + registration, no robot control)
uv sync

# With specific robot support
uv sync --extra tumbller
uv sync --extra tello

# Everything
uv sync --extra all
```

---

## 9. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        LLM / AI Agent                           │
│  (Claude, GPT, etc. connected via MCP)                          │
└──────────────────────────────┬──────────────────────────────────┘
                               │ MCP (streamable-http)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastMCP Server (core/server.py)              │
│                                                                  │
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │ Discovery Tool   │  │ Tumbller Tools   │  │  Tello Tools  │  │
│  │                  │  │                  │  │               │  │
│  │ discover_robot   │  │ tumbller_move    │  │ tello_takeoff │  │
│  │ _agents()        │  │ tumbller_is      │  │ tello_land    │  │
│  │                  │  │ _online()        │  │ tello_move    │  │
│  │ Queries ERC-8004 │  │ tumbller_get     │  │ tello_rotate  │  │
│  │ on Sepolia       │  │ _temperature     │  │ tello_flip    │  │
│  │                  │  │ _humidity()      │  │ tello_get     │  │
│  │                  │  │                  │  │ _status()     │  │
│  └─────────────────┘  └───────┬──────────┘  └──────┬────────┘  │
│                               │                     │            │
└───────────────────────────────┼─────────────────────┼────────────┘
                                │                     │
                    ┌───────────▼──────┐   ┌──────────▼──────────┐
                    │ TumbllerClient   │   │   TelloClient       │
                    │ (HTTP/httpx)     │   │   (UDP/djitellopy)  │
                    └───────┬──────────┘   └──────────┬──────────┘
                            │                         │
                   HTTP :80 │                UDP :8889 │
                            ▼                         ▼
                    ┌───────────────┐       ┌──────────────────┐
                    │ ESP32-S3      │       │ DJI Tello        │
                    │ Tumbller      │       │ Drone            │
                    └───────────────┘       └──────────────────┘
```

---

## 10. Migration Path from Existing Repos

### Phase 1: Create the framework repo

1. Create `robot-fleet-mcp` repo with the structure from Section 2
2. Move shared code (`tunnel.py`, `generate_wallet.py`, discovery, registration) into `src/core/`
3. Create `RobotPlugin` base class in `src/core/plugin.py`

### Phase 2: Port the Tumbller plugin

1. Copy `tumbller_client.py` → `src/robots/tumbller/client.py` (unchanged)
2. Extract tool definitions from `server.py` → `src/robots/tumbller/tools.py`
3. Write `TumbllerPlugin` class in `src/robots/tumbller/__init__.py`
4. Verify: `uv run python scripts/serve.py --robots tumbller`

### Phase 3: Port the Tello plugin

1. Copy `tello_client.py` → `src/robots/tello/client.py` (unchanged)
2. Extract tool definitions from `server.py` → `src/robots/tello/tools.py`
3. Write `TelloPlugin` class in `src/robots/tello/__init__.py`
4. Verify: `uv run python scripts/serve.py --robots tello`

### Phase 4: Add discovery MCP tool

1. Implement `register_discovery_tools()` in `src/core/discovery.py`
2. Wire it into `create_server()` so it's always loaded
3. Verify: connect Claude, call `discover_robot_agents()`

### Phase 5: Deprecate single-robot repos

1. Update original repos' READMEs pointing to the new framework
2. Archive `tumbller-8004-mcp` and `tello-8004-mcp`

---

## 11. Open Design Questions

| # | Question | Options | Recommendation |
|---|----------|---------|----------------|
| 1 | **Single server or per-robot servers?** | (a) One MCP server exposes all robots (b) Each robot gets its own MCP server on a different port | (a) Single server with prefixed tools — simpler for LLMs, one connection |
| 2 | **Tool prefixing** | (a) Always prefix (`tumbller_move`) (b) Only in fleet mode (c) Configurable | (a) Always prefix — consistent, no ambiguity |
| 3 | **Plugin loading** | (a) Auto-discover all packages in `src/robots/` (b) Explicit list in config file (c) CLI `--robots` flag | (a)+(c) — auto-discover, allow CLI override |
| 4 | **One wallet per fleet or per robot?** | (a) Shared fleet wallet (b) Separate wallet per robot | (a) Shared wallet for simplicity; per-robot wallets for production isolation |
| 5 | **Where does this repo live?** | (a) New repo `robot-fleet-mcp` (b) Evolve one of the existing repos | (a) New repo — cleaner separation |

---

## 12. Summary

**What changes:**
- Shared infrastructure code lives in one place (`core/`)
- Robot-specific code is isolated in plugin packages (`robots/{name}/`)
- Registration/update/fix scripts become generic, driven by plugin metadata
- Discovery becomes an MCP tool callable by LLMs

**What stays the same:**
- Each robot's client code is untouched (`TumbllerClient`, `TelloClient`)
- ERC-8004 registration flow is preserved
- ngrok tunneling is preserved
- FastMCP as the MCP framework
- All existing robot affordances remain identical

**What's new:**
- `RobotPlugin` base class with 3 methods to implement
- Auto-discovery of plugins via package scanning
- `discover_robot_agents` MCP tool for LLM-driven robot discovery
- Single `serve.py` that can load any combination of robots
- `_template/` directory for quickly scaffolding new robot plugins
