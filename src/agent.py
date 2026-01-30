"""
AIBTC Autonomous Agent
======================
Main agent orchestration that combines all components:
- Wallet management
- BNS identity
- Avatar generation
- MCP verification
- sBTC airdrops
- Moltbook interactions

The agent promotes sBTC adoption by verifying other agents
have set up Stacks MCP and rewarding them with airdrops.
"""

import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

from .config import AgentConfig, CONTRACTS
from .wallet import Wallet, create_wallet, load_wallet, get_balance
from .bns import BNSRegistrar
from .avatar import AvatarManager, BitcoinFace
from .sbtc import SBTCManager
from .verifier import MCPVerifier, VerificationResult, TrustLevel


@dataclass
class AgentIdentity:
    """Complete agent identity."""
    wallet: Wallet
    bns_name: Optional[str]
    avatar: Optional[BitcoinFace]


@dataclass
class AirdropRecord:
    """Record of an airdrop sent."""
    recipient: str
    sbtc_sats: int
    stx_ustx: int
    tx_id: Optional[str]
    timestamp: str
    reason: str


class AIBTCAgent:
    """
    Autonomous AI agent on the AIBTC platform.

    Capabilities:
    1. Verify other agents' Stacks MCP setup
    2. Airdrop sBTC + STX to verified agents
    3. Track and report adoption metrics
    4. Interact on Moltbook (post, debate, persuade)

    Usage:
        config = AgentConfig.from_env()
        agent = AIBTCAgent(config)
        await agent.initialize()
        await agent.run()
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.identity: Optional[AgentIdentity] = None

        # Initialize managers
        self.bns = BNSRegistrar(config.stacks_api_url, config.network)
        self.avatar_manager = AvatarManager()
        self.sbtc = SBTCManager(config.stacks_api_url, config.network)
        self.verifier = MCPVerifier(
            config.stacks_api_url,
            appleseed_path=config.appleseed_path
        )

        # Track airdrops
        self.airdrop_history: List[AirdropRecord] = []

    async def initialize(self) -> bool:
        """
        Initialize the agent with wallet, BNS name, and avatar.

        Returns:
            True if initialization successful
        """
        print(f"[agent] Initializing {self.config.agent_name}...")

        # Step 1: Load or create wallet
        if self.config.private_key:
            wallet = load_wallet(self.config.private_key, self.config.network)
            print(f"[agent] Loaded wallet: {wallet.stx_address}")
        else:
            wallet = create_wallet(self.config.network)
            print(f"[agent] Created new wallet: {wallet.stx_address}")
            print(f"[agent] SAVE THIS PRIVATE KEY: {wallet.private_key}")

        # Step 2: Check balance
        balance = await get_balance(wallet.stx_address, self.config.stacks_api_url)
        print(f"[agent] Balance: {balance['stx']:.2f} STX, {balance['sbtc']:.8f} sBTC")

        # Step 3: Generate avatar
        avatar = await self.avatar_manager.create_avatar(
            wallet.stx_address,
            self.config.agent_name
        )
        print(f"[agent] Avatar: {avatar.preview_url}")

        # Step 4: Check BNS name
        bns_name = None
        if self.config.bns_name:
            owned = await self.bns.get_owned_names(wallet.stx_address)
            if self.config.bns_name in owned:
                bns_name = self.config.bns_name
                print(f"[agent] BNS name verified: {bns_name}")
            else:
                print(f"[agent] BNS name not owned. Register via /bns register")

        self.identity = AgentIdentity(
            wallet=wallet,
            bns_name=bns_name,
            avatar=avatar
        )

        return True

    async def verify_and_airdrop(
        self,
        target_address: str,
        github_repo: Optional[str] = None,
        mcp_endpoint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verify an agent's MCP setup and airdrop if eligible.

        Args:
            target_address: Agent's Stacks address
            github_repo: Their GitHub repo
            mcp_endpoint: Their MCP endpoint

        Returns:
            Verification and airdrop result
        """
        if not self.identity:
            return {"error": "Agent not initialized"}

        print(f"[agent] Verifying {target_address}...")

        # Run verification
        result = await self.verifier.verify_agent(
            agent_address=target_address,
            github_repo=github_repo,
            mcp_endpoint=mcp_endpoint
        )

        response = {
            "target": target_address,
            "verified": result.success,
            "trust_level": result.trust_level.name,
            "checks_passed": result.checks_passed,
            "checks_failed": result.checks_failed,
            "reason": result.reason,
        }

        # Airdrop if eligible
        if result.eligible_for_airdrop:
            airdrop_result = await self._execute_airdrop(
                recipient=target_address,
                sbtc_sats=result.airdrop_amount_sats,
                stx_ustx=result.airdrop_amount_stx,
                reason=f"MCP verification - {result.trust_level.name}"
            )
            response["airdrop"] = airdrop_result
        else:
            response["airdrop"] = None

        return response

    async def _execute_airdrop(
        self,
        recipient: str,
        sbtc_sats: int,
        stx_ustx: int,
        reason: str
    ) -> Dict[str, Any]:
        """
        Execute an airdrop of sBTC and STX.

        Returns:
            Airdrop details including tx_ids
        """
        if not self.identity:
            return {"error": "Agent not initialized"}

        print(f"[agent] Airdropping to {recipient}...")
        print(f"[agent]   sBTC: {sbtc_sats} sats")
        print(f"[agent]   STX:  {stx_ustx / 1_000_000:.4f} STX")

        result = {
            "recipient": recipient,
            "sbtc_sats": sbtc_sats,
            "stx_ustx": stx_ustx,
            "sbtc_tx_id": None,
            "stx_tx_id": None,
            "timestamp": datetime.now().isoformat(),
        }

        # Prepare sBTC transfer
        if sbtc_sats > 0:
            sbtc_tx = self.sbtc.prepare_transfer(
                sender=self.identity.wallet.stx_address,
                recipient=recipient,
                amount_sats=sbtc_sats,
                memo=f"AIBTC airdrop: {reason}"
            )
            result["sbtc_tx_prepared"] = True
            # Note: Actual signing requires private key handling
            # In production, use stacks.js or similar

        # Record airdrop
        record = AirdropRecord(
            recipient=recipient,
            sbtc_sats=sbtc_sats,
            stx_ustx=stx_ustx,
            tx_id=None,  # Would be set after broadcast
            timestamp=result["timestamp"],
            reason=reason
        )
        self.airdrop_history.append(record)

        return result

    async def get_status(self) -> Dict[str, Any]:
        """Get agent status and stats."""
        if not self.identity:
            return {"status": "not_initialized"}

        balance = await get_balance(
            self.identity.wallet.stx_address,
            self.config.stacks_api_url
        )

        return {
            "status": "running",
            "identity": {
                "address": self.identity.wallet.stx_address,
                "bns_name": self.identity.bns_name,
                "avatar": self.identity.avatar.preview_url if self.identity.avatar else None,
            },
            "balance": balance,
            "verifier_stats": self.verifier.get_stats(),
            "total_airdrops": len(self.airdrop_history),
            "total_sbtc_airdropped": sum(a.sbtc_sats for a in self.airdrop_history),
            "total_stx_airdropped": sum(a.stx_ustx for a in self.airdrop_history),
        }

    def get_persuasion_message(self) -> str:
        """
        Generate a message to persuade other agents to adopt sBTC.

        Used for Moltbook interactions and outreach.
        """
        return """
**Why sBTC for Your DAO Treasury?**

1. **Non-custodial**: Your BTC stays on Bitcoin. No third-party risk.

2. **1:1 Backed**: Each sBTC is backed by real BTC, verifiable on-chain.

3. **Yield Opportunities**: Earn 5-8% APY on Zest Protocol lending.

4. **Programmable**: Use sBTC in smart contracts, DeFi, DAOs.

5. **Stacks Security**: Secured by Bitcoin's PoW through Stacks consensus.

**Get Started:**
1. Set up Stacks MCP: `npm install @aibtc/mcp-server`
2. Get verified by our agent
3. Receive sBTC + STX airdrop

Learn more: https://aibtc.com
        """.strip()

    async def run(self, interval_seconds: int = 60):
        """
        Run the agent in continuous mode.

        Periodically checks for verification requests and processes them.
        """
        print(f"[agent] Starting continuous run (interval: {interval_seconds}s)")

        while True:
            try:
                # In production, this would:
                # 1. Check Moltbook for mentions/requests
                # 2. Process pending verifications
                # 3. Send scheduled airdrops
                # 4. Post adoption updates

                status = await self.get_status()
                print(f"[agent] Heartbeat - {status['verifier_stats']['total_verified']} verified")

            except Exception as e:
                print(f"[agent] Error: {e}")

            await asyncio.sleep(interval_seconds)


# CLI entry point
async def main():
    """CLI entry point for the agent."""
    import sys

    config = AgentConfig.from_env()
    agent = AIBTCAgent(config)

    if len(sys.argv) < 2:
        print("Usage: python -m src.agent <command>")
        print("Commands: init, status, verify <address>, run")
        return

    command = sys.argv[1]

    if command == "init":
        await agent.initialize()

    elif command == "status":
        await agent.initialize()
        status = await agent.get_status()
        import json
        print(json.dumps(status, indent=2))

    elif command == "verify":
        if len(sys.argv) < 3:
            print("Usage: python -m src.agent verify <address> [github_repo]")
            return
        await agent.initialize()
        address = sys.argv[2]
        repo = sys.argv[3] if len(sys.argv) > 3 else None
        result = await agent.verify_and_airdrop(address, github_repo=repo)
        import json
        print(json.dumps(result, indent=2))

    elif command == "run":
        await agent.initialize()
        await agent.run()

    elif command == "persuade":
        print(agent.get_persuasion_message())

    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    asyncio.run(main())
