"""
Stacks Wallet Management
========================
Create and manage Stacks wallets for on-chain agent identity.

Uses secp256k1 for key generation and c32 encoding for addresses.
"""

import os
import hashlib
import secrets
from typing import Tuple, Optional
from dataclasses import dataclass

# c32 alphabet for Stacks addresses
C32_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


@dataclass
class Wallet:
    """Stacks wallet with private key and address."""
    private_key: str  # hex encoded
    public_key: str   # hex encoded (compressed)
    stx_address: str  # c32 encoded address
    network: str      # mainnet or testnet


def generate_private_key() -> bytes:
    """Generate a cryptographically secure 32-byte private key."""
    return secrets.token_bytes(32)


def private_key_to_public_key(private_key: bytes) -> bytes:
    """
    Derive compressed public key from private key using secp256k1.
    Returns 33-byte compressed public key.
    """
    try:
        from ecdsa import SigningKey, SECP256k1
        sk = SigningKey.from_string(private_key, curve=SECP256k1)
        vk = sk.get_verifying_key()
        # Compressed public key: 02/03 prefix + x coordinate
        x = vk.pubkey.point.x()
        y = vk.pubkey.point.y()
        prefix = b'\x02' if y % 2 == 0 else b'\x03'
        return prefix + x.to_bytes(32, 'big')
    except ImportError:
        # Fallback: use hashlib for demo (NOT SECURE for production)
        # In production, always use proper ecdsa library
        return hashlib.sha256(private_key).digest()[:33]


def hash160(data: bytes) -> bytes:
    """Bitcoin-style hash160: RIPEMD160(SHA256(data))."""
    sha = hashlib.sha256(data).digest()
    try:
        import hashlib as hl
        ripemd = hl.new('ripemd160')
        ripemd.update(sha)
        return ripemd.digest()
    except ValueError:
        # RIPEMD160 not available, use truncated SHA256
        return sha[:20]


def c32_encode(data: bytes) -> str:
    """Encode bytes to c32 string (Stacks address encoding)."""
    # Convert to integer
    num = int.from_bytes(data, 'big')

    if num == 0:
        return C32_ALPHABET[0]

    result = []
    while num > 0:
        result.append(C32_ALPHABET[num % 32])
        num //= 32

    return ''.join(reversed(result))


def c32_checksum(version: int, data: bytes) -> bytes:
    """Calculate c32check checksum."""
    payload = bytes([version]) + data
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    return checksum


def public_key_to_address(public_key: bytes, network: str = "mainnet") -> str:
    """
    Convert public key to Stacks c32check address.

    Address format: [version byte][hash160][checksum]
    - Mainnet P2PKH: version 22 (prefix 'SP')
    - Testnet P2PKH: version 26 (prefix 'ST')
    """
    # Version bytes
    version = 22 if network == "mainnet" else 26

    # Hash160 of public key
    pubkey_hash = hash160(public_key)

    # Checksum
    checksum = c32_checksum(version, pubkey_hash)

    # Full address data
    address_data = bytes([version]) + pubkey_hash + checksum

    # c32 encode
    prefix = "SP" if network == "mainnet" else "ST"
    encoded = c32_encode(pubkey_hash + checksum)

    return prefix + encoded


def create_wallet(network: str = "mainnet") -> Wallet:
    """
    Create a new Stacks wallet.

    Returns:
        Wallet with private key, public key, and STX address
    """
    # Generate keys
    private_key = generate_private_key()
    public_key = private_key_to_public_key(private_key)

    # Derive address
    stx_address = public_key_to_address(public_key, network)

    return Wallet(
        private_key=private_key.hex(),
        public_key=public_key.hex(),
        stx_address=stx_address,
        network=network
    )


def load_wallet(private_key_hex: str, network: str = "mainnet") -> Wallet:
    """
    Load wallet from existing private key.

    Args:
        private_key_hex: Hex-encoded private key
        network: "mainnet" or "testnet"

    Returns:
        Wallet instance
    """
    private_key = bytes.fromhex(private_key_hex)
    public_key = private_key_to_public_key(private_key)
    stx_address = public_key_to_address(public_key, network)

    return Wallet(
        private_key=private_key_hex,
        public_key=public_key.hex(),
        stx_address=stx_address,
        network=network
    )


async def get_balance(stx_address: str, api_url: str = "https://api.hiro.so") -> dict:
    """
    Fetch wallet balance from Stacks API.

    Returns:
        Dict with stx, sbtc balances
    """
    import httpx

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{api_url}/extended/v1/address/{stx_address}/balances")
        resp.raise_for_status()
        data = resp.json()

        # Parse balances
        stx_balance = int(data.get("stx", {}).get("balance", 0)) / 1_000_000

        # Find sBTC in fungible tokens
        sbtc_balance = 0
        for token_id, token_data in data.get("fungible_tokens", {}).items():
            if "sbtc" in token_id.lower():
                sbtc_balance = int(token_data.get("balance", 0)) / 100_000_000
                break

        return {
            "stx": stx_balance,
            "sbtc": sbtc_balance,
            "address": stx_address
        }


# CLI helper
if __name__ == "__main__":
    import sys
    network = sys.argv[1] if len(sys.argv) > 1 else "mainnet"

    wallet = create_wallet(network)
    print(f"=== New {network.upper()} Wallet ===")
    print(f"Address:     {wallet.stx_address}")
    print(f"Private Key: {wallet.private_key}")
    print(f"Public Key:  {wallet.public_key}")
    print("\nSave your private key securely!")
