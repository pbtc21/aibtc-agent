"""
sBTC Integration
================
Deposit, withdraw, and transfer sBTC on Stacks.

sBTC is a 1:1 Bitcoin-backed token on Stacks.
Contract: SM3VDXK3WZZSA84XXFKAFAF15NNZX32CTSG82JFQ4.sbtc-token
"""

import httpx
from typing import Optional, Dict, Any
from dataclasses import dataclass


# Contract addresses
SBTC_CONTRACTS = {
    "mainnet": {
        "token": "SM3VDXK3WZZSA84XXFKAFAF15NNZX32CTSG82JFQ4.sbtc-token",
    },
    "testnet": {
        "token": "ST1F7QA2MDF17S807EPA36TSS8AMEFY4KA9TVGWXT.sbtc-token",
    }
}


@dataclass
class SBTCBalance:
    """sBTC balance info."""
    address: str
    balance_sats: int
    balance_btc: float


@dataclass
class TransferResult:
    """Result of an sBTC transfer."""
    success: bool
    tx_id: Optional[str]
    amount_sats: int
    recipient: str
    error: Optional[str] = None


async def get_sbtc_balance(
    address: str,
    api_url: str = "https://api.hiro.so",
    network: str = "mainnet"
) -> SBTCBalance:
    """
    Get sBTC balance for an address.

    Args:
        address: Stacks address
        api_url: Stacks API URL
        network: "mainnet" or "testnet"

    Returns:
        SBTCBalance with sats and BTC amounts
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{api_url}/extended/v1/address/{address}/balances")
        resp.raise_for_status()
        data = resp.json()

        # Find sBTC in fungible tokens
        sbtc_contract = SBTC_CONTRACTS[network]["token"]
        balance_sats = 0

        for token_id, token_data in data.get("fungible_tokens", {}).items():
            if sbtc_contract in token_id:
                balance_sats = int(token_data.get("balance", 0))
                break

        return SBTCBalance(
            address=address,
            balance_sats=balance_sats,
            balance_btc=balance_sats / 100_000_000
        )


def build_sbtc_transfer_tx(
    recipient: str,
    amount_sats: int,
    sender: str,
    memo: Optional[str] = None,
    network: str = "mainnet"
) -> Dict[str, Any]:
    """
    Build an sBTC transfer transaction.

    Args:
        recipient: Recipient's Stacks address
        amount_sats: Amount in satoshis
        sender: Sender's Stacks address
        memo: Optional memo (max 34 bytes)
        network: "mainnet" or "testnet"

    Returns:
        Transaction parameters for signing
    """
    contract = SBTC_CONTRACTS[network]["token"]
    contract_address, contract_name = contract.split(".")

    # Build function args for SIP-010 transfer
    function_args = [
        {"type": "uint", "value": amount_sats},
        {"type": "principal", "value": sender},
        {"type": "principal", "value": recipient},
    ]

    # Add memo if provided
    if memo:
        memo_bytes = memo.encode()[:34]  # Max 34 bytes
        function_args.append({"type": "some", "value": {"type": "buff", "value": memo_bytes.hex()}})
    else:
        function_args.append({"type": "none"})

    return {
        "contract_address": contract_address,
        "contract_name": contract_name,
        "function_name": "transfer",
        "function_args": function_args,
        "post_conditions": [
            {
                "type": "ft-transfer",
                "principal": sender,
                "asset": contract,
                "condition": "eq",
                "amount": amount_sats,
            }
        ],
    }


class SBTCManager:
    """
    High-level sBTC management.

    Usage:
        manager = SBTCManager(api_url, network)
        balance = await manager.get_balance(address)
        tx = manager.prepare_transfer(recipient, amount)
    """

    def __init__(
        self,
        api_url: str = "https://api.hiro.so",
        network: str = "mainnet"
    ):
        self.api_url = api_url
        self.network = network

    async def get_balance(self, address: str) -> SBTCBalance:
        """Get sBTC balance."""
        return await get_sbtc_balance(address, self.api_url, self.network)

    def prepare_transfer(
        self,
        sender: str,
        recipient: str,
        amount_sats: int,
        memo: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Prepare an sBTC transfer transaction.

        Returns transaction params ready for signing.
        """
        return build_sbtc_transfer_tx(
            recipient=recipient,
            amount_sats=amount_sats,
            sender=sender,
            memo=memo,
            network=self.network
        )

    async def estimate_fee(self) -> int:
        """
        Estimate transaction fee in microSTX.

        Returns:
            Estimated fee in microSTX
        """
        # Standard contract call fee estimate
        return 2500  # ~0.0025 STX

    def format_amount(self, sats: int) -> str:
        """Format satoshis as human-readable string."""
        if sats >= 100_000_000:
            return f"{sats / 100_000_000:.8f} sBTC"
        return f"{sats:,} sats"
