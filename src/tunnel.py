"""Start an ngrok tunnel to the MCP server using a static free domain."""

import os
from pyngrok import ngrok, conf


def start_tunnel(port: int = 8000) -> str:
    auth_token = os.getenv("NGROK_AUTHTOKEN")
    domain = os.getenv("NGROK_DOMAIN")

    if not auth_token:
        raise RuntimeError("NGROK_AUTHTOKEN not set in .env")
    if not domain:
        raise RuntimeError("NGROK_DOMAIN not set in .env (claim at https://dashboard.ngrok.com/domains)")

    ngrok.set_auth_token(auth_token)
    tunnel = ngrok.connect(
        addr=str(port),
        proto="http",
        hostname=domain,
    )
    public_url = f"https://{domain}"
    print(f"ngrok tunnel: {public_url}")
    print(f"MCP endpoint: {public_url}/mcp")
    return public_url
