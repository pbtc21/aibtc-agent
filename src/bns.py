"""
BNS (Bitcoin Name System) Integration
=====================================
Register and manage .btc names on Stacks for agent identity.

BNS allows registering names like "agentX.btc" or "grok-agent.btc"
Cost: ~2 STX for registration
"""

import httpx
import hashlib
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class BNSName:
    """Registered BNS name."""
    name: str           # e.g., "agentX"
    namespace: str      # e.g., "btc"
    full_name: str      # e.g., "agentX.btc"
    owner: str          # STX address
    zonefile_hash: Optional[str] = None


# BNS Contract addresses
BNS_CONTRACTS = {
    "mainnet": {
        "core": "SP000000000000000000002Q6VF78.bns",
        "namespace_preorder": "SP000000000000000000002Q6VF78.bns",
    },
    "testnet": {
        "core": "ST000000000000000000002AMW42H.bns",
    }
}


async def check_name_availability(
    name: str,
    namespace: str = "btc",
    api_url: str = "https://api.hiro.so"
) -> bool:
    """
    Check if a BNS name is available for registration.

    Args:
        name: The name to check (e.g., "agentX")
        namespace: The namespace (default: "btc")
        api_url: Stacks API URL

    Returns:
        True if name is available, False otherwise
    """
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{api_url}/v1/names/{name}.{namespace}"
            )
            # 404 means name is available
            return resp.status_code == 404
        except Exception:
            return False


async def get_name_info(
    name: str,
    namespace: str = "btc",
    api_url: str = "https://api.hiro.so"
) -> Optional[Dict[str, Any]]:
    """
    Get information about a registered BNS name.

    Returns:
        Name info dict or None if not found
    """
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{api_url}/v1/names/{name}.{namespace}"
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception:
            return None


async def get_names_owned_by(
    address: str,
    api_url: str = "https://api.hiro.so"
) -> list:
    """
    Get all BNS names owned by an address.

    Returns:
        List of name strings
    """
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{api_url}/v1/addresses/stacks/{address}"
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("names", [])
            return []
        except Exception:
            return []


def generate_name_hash(name: str, salt: bytes) -> bytes:
    """Generate hash for BNS name preorder."""
    name_bytes = name.encode('utf-8')
    return hashlib.sha256(name_bytes + salt).digest()


def build_name_preorder_tx(
    name: str,
    namespace: str,
    stx_to_burn: int,
    sender: str,
    network: str = "mainnet"
) -> Dict[str, Any]:
    """
    Build a BNS name-preorder transaction.

    This is step 1 of the 2-step registration process:
    1. name-preorder: Commit to the name with a hash
    2. name-register: Reveal the name and complete registration

    Args:
        name: Name to register (e.g., "agentX")
        namespace: Namespace (e.g., "btc")
        stx_to_burn: Amount of STX to burn (in microSTX)
        sender: Sender's STX address
        network: "mainnet" or "testnet"

    Returns:
        Transaction parameters for signing
    """
    import secrets

    # Generate random salt for commitment
    salt = secrets.token_bytes(20)

    # Generate hashed salted name
    full_name = f"{name}.{namespace}"
    hashed_name = generate_name_hash(full_name, salt)

    contract = BNS_CONTRACTS[network]["core"]

    return {
        "contract_address": contract.split(".")[0],
        "contract_name": contract.split(".")[1],
        "function_name": "name-preorder",
        "function_args": [
            {"type": "buff", "value": hashed_name.hex()},
            {"type": "uint", "value": stx_to_burn},
        ],
        "salt": salt.hex(),  # Save this for the register step!
        "name": name,
        "namespace": namespace,
    }


def build_name_register_tx(
    name: str,
    namespace: str,
    salt_hex: str,
    zonefile_hash: Optional[str],
    sender: str,
    network: str = "mainnet"
) -> Dict[str, Any]:
    """
    Build a BNS name-register transaction.

    This is step 2 of registration, must be called after preorder confirms.

    Args:
        name: Name being registered
        namespace: Namespace
        salt_hex: Salt used in preorder (hex encoded)
        zonefile_hash: Optional zonefile hash for DNS-like records
        sender: Sender's STX address
        network: "mainnet" or "testnet"

    Returns:
        Transaction parameters for signing
    """
    contract = BNS_CONTRACTS[network]["core"]

    return {
        "contract_address": contract.split(".")[0],
        "contract_name": contract.split(".")[1],
        "function_name": "name-register",
        "function_args": [
            {"type": "buff", "value": namespace.encode().hex()},
            {"type": "buff", "value": name.encode().hex()},
            {"type": "buff", "value": salt_hex},
            {"type": "buff", "value": zonefile_hash or "00" * 20},
        ],
        "name": name,
        "namespace": namespace,
    }


async def estimate_registration_cost(
    namespace: str = "btc",
    api_url: str = "https://api.hiro.so"
) -> int:
    """
    Estimate the cost to register a name in a namespace.

    Returns:
        Cost in microSTX
    """
    # .btc namespace has a base price of ~2 STX
    # Shorter names cost more
    BASE_PRICE = 2_000_000  # 2 STX in microSTX

    return BASE_PRICE


class BNSRegistrar:
    """
    High-level BNS registration manager.

    Usage:
        registrar = BNSRegistrar(wallet, api_url)
        await registrar.register_name("myagent", "btc")
    """

    def __init__(self, api_url: str = "https://api.hiro.so", network: str = "mainnet"):
        self.api_url = api_url
        self.network = network

    async def is_available(self, name: str, namespace: str = "btc") -> bool:
        """Check if name is available."""
        return await check_name_availability(name, namespace, self.api_url)

    async def get_owned_names(self, address: str) -> list:
        """Get names owned by address."""
        return await get_names_owned_by(address, self.api_url)

    async def prepare_registration(
        self,
        name: str,
        namespace: str = "btc"
    ) -> Dict[str, Any]:
        """
        Prepare a name registration.

        Returns preorder transaction and salt to save.
        """
        # Check availability
        if not await self.is_available(name, namespace):
            raise ValueError(f"Name {name}.{namespace} is not available")

        # Estimate cost
        cost = await estimate_registration_cost(namespace, self.api_url)

        # Build preorder transaction
        preorder_tx = build_name_preorder_tx(
            name=name,
            namespace=namespace,
            stx_to_burn=cost,
            sender="",  # Will be filled by signer
            network=self.network
        )

        return {
            "step": "preorder",
            "transaction": preorder_tx,
            "cost_ustx": cost,
            "cost_stx": cost / 1_000_000,
            "name": f"{name}.{namespace}",
            "next_step": "After preorder confirms, call complete_registration with the salt"
        }

    def prepare_registration_complete(
        self,
        name: str,
        namespace: str,
        salt_hex: str,
        zonefile_hash: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Prepare the registration completion transaction.

        Call this after preorder has confirmed (~10 blocks).
        """
        register_tx = build_name_register_tx(
            name=name,
            namespace=namespace,
            salt_hex=salt_hex,
            zonefile_hash=zonefile_hash,
            sender="",
            network=self.network
        )

        return {
            "step": "register",
            "transaction": register_tx,
            "name": f"{name}.{namespace}",
        }
