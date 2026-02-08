import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from typing import Literal
from dotenv import load_dotenv
from fastmcp import FastMCP
from tumbller_client import TumbllerClient

load_dotenv()

# Bearer token auth (optional — only enabled if MCP_BEARER_TOKEN is set in .env)
auth = None
bearer_token = os.getenv("MCP_BEARER_TOKEN")
if bearer_token:
    from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
    auth = StaticTokenVerifier(
        tokens={bearer_token: {"client_id": "mcp-client", "scopes": []}}
    )

mcp = FastMCP(
    name="Tumbller Self-Balancing Robot",
    instructions="Control and monitor a Tumbller ESP32-S3 self-balancing robot",
    auth=auth,
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
