"""Generate or display Ethereum wallet for ERC-8004 registration.

Usage:
    uv run python src/generate_wallet.py          # Show existing wallet from .env
    uv run python src/generate_wallet.py --new     # Generate new wallet and save to .env
"""

import sys
import os
import re

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
from web3 import Web3

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")

load_dotenv(ENV_PATH)


def update_env(key, value):
    """Update or append a key=value in the .env file."""
    env_path = os.path.abspath(ENV_PATH)
    with open(env_path, "r") as f:
        content = f.read()

    if re.search(rf"^{key}=.*$", content, re.MULTILINE):
        content = re.sub(
            rf"^{key}=.*$",
            f"{key}={value}",
            content,
            flags=re.MULTILINE,
        )
    else:
        content += f"\n{key}={value}\n"

    with open(env_path, "w") as f:
        f.write(content)


def get_existing_wallet():
    key = os.getenv("SIGNER_PVT_KEY", "").strip()
    if not key:
        return None
    w3 = Web3()
    account = w3.eth.account.from_key(key)
    return account


def generate_and_save():
    w3 = Web3()
    account = w3.eth.account.create()

    update_env("SIGNER_PVT_KEY", account.key.hex())
    update_env("WALLET_ADDRESS", account.address)

    print("=== New Ethereum Wallet ===")
    print(f"Address: {account.address}")
    print(f"\nSaved to .env")
    print(f"\nNext step: Fund with Sepolia ETH:")
    print(f"  https://www.alchemy.com/faucets/ethereum-sepolia")
    return account


if __name__ == "__main__":
    if "--new" in sys.argv:
        generate_and_save()
    else:
        account = get_existing_wallet()
        if account:
            print("=== Existing Wallet (from .env) ===")
            print(f"Address: {account.address}")
        else:
            print("No wallet found in .env. Run with --new to generate one:")
            print("  uv run python src/generate_wallet.py --new")
