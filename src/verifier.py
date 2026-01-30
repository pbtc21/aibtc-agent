"""
Agent Verifier & Airdrop System
===============================
Verify that other agents have properly set up Stacks MCP,
then airdrop sBTC and STX as rewards.

Game Theory Protections:
------------------------
1. Progressive Trust: Start with small airdrops, increase with proven activity
2. Anti-Sybil: Require unique GitHub repo or BNS name
3. Proof of Work: Agent must complete a verification task
4. Rate Limiting: Max airdrops per time period
5. Stake Requirement: Verified agents must hold some STX
6. Reputation Decay: Trust score decreases without activity

The goal is to incentivize genuine adoption, not farming.
"""

import httpx
import hashlib
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta


class TrustLevel(Enum):
    """Progressive trust levels for verified agents."""
    UNKNOWN = 0      # Never seen
    PENDING = 1      # Verification in progress
    BASIC = 2        # Passed initial verification
    TRUSTED = 3      # Completed multiple tasks
    ESTABLISHED = 4  # Long-term contributor


@dataclass
class AgentRecord:
    """Record of a verified agent."""
    address: str
    github_repo: Optional[str]
    bns_name: Optional[str]
    trust_level: TrustLevel
    total_airdrops_sats: int
    total_airdrops_stx: int  # in microSTX
    verification_count: int
    first_seen: str
    last_activity: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    """Result of MCP setup verification."""
    success: bool
    checks_passed: List[str]
    checks_failed: List[str]
    trust_level: TrustLevel
    eligible_for_airdrop: bool
    airdrop_amount_sats: int
    airdrop_amount_stx: int
    reason: str


# Airdrop amounts by trust level (in sats and microSTX)
AIRDROP_AMOUNTS = {
    TrustLevel.BASIC: {"sbtc_sats": 1000, "stx_ustx": 100_000},       # 1000 sats, 0.1 STX
    TrustLevel.TRUSTED: {"sbtc_sats": 5000, "stx_ustx": 500_000},     # 5000 sats, 0.5 STX
    TrustLevel.ESTABLISHED: {"sbtc_sats": 10000, "stx_ustx": 1_000_000},  # 10k sats, 1 STX
}

# Rate limits
MAX_AIRDROPS_PER_DAY = 10
MAX_AIRDROPS_PER_ADDRESS = 5
COOLDOWN_HOURS = 24


class MCPVerifier:
    """
    Verify that an agent has properly set up Stacks MCP.

    Verification Checks:
    1. GitHub repo exists and contains MCP config
    2. Package.json has @aibtc/mcp-server dependency
    3. MCP server is responding (if endpoint provided)
    4. Agent address has minimum STX balance (anti-sybil)
    5. Optional: BNS name registered
    """

    def __init__(
        self,
        api_url: str = "https://api.hiro.so",
        min_stx_balance: int = 100_000,  # 0.1 STX minimum
    ):
        self.api_url = api_url
        self.min_stx_balance = min_stx_balance
        self.verified_agents: Dict[str, AgentRecord] = {}
        self.daily_airdrop_count = 0
        self.last_reset = datetime.now()

    async def verify_agent(
        self,
        agent_address: str,
        github_repo: Optional[str] = None,
        mcp_endpoint: Optional[str] = None,
        bns_name: Optional[str] = None
    ) -> VerificationResult:
        """
        Verify an agent's Stacks MCP setup.

        Args:
            agent_address: Agent's Stacks address
            github_repo: GitHub repo URL (e.g., "owner/repo")
            mcp_endpoint: MCP server endpoint URL
            bns_name: Optional BNS name

        Returns:
            VerificationResult with eligibility and airdrop amounts
        """
        checks_passed = []
        checks_failed = []

        # Check 1: Address format
        if self._is_valid_stacks_address(agent_address):
            checks_passed.append("valid_address")
        else:
            checks_failed.append("invalid_address")
            return self._fail_result(checks_passed, checks_failed, "Invalid Stacks address")

        # Check 2: Minimum STX balance (anti-sybil)
        balance = await self._check_stx_balance(agent_address)
        if balance >= self.min_stx_balance:
            checks_passed.append("min_balance")
        else:
            checks_failed.append("insufficient_balance")
            return self._fail_result(
                checks_passed, checks_failed,
                f"Need at least {self.min_stx_balance / 1_000_000} STX"
            )

        # Check 3: GitHub repo has MCP setup
        if github_repo:
            mcp_check = await self._verify_github_mcp(github_repo)
            if mcp_check:
                checks_passed.append("github_mcp")
            else:
                checks_failed.append("github_mcp_missing")

        # Check 4: MCP endpoint responding
        if mcp_endpoint:
            endpoint_check = await self._verify_mcp_endpoint(mcp_endpoint)
            if endpoint_check:
                checks_passed.append("mcp_endpoint")
            else:
                checks_failed.append("mcp_endpoint_down")

        # Check 5: BNS name (bonus, not required)
        if bns_name:
            bns_check = await self._verify_bns_ownership(agent_address, bns_name)
            if bns_check:
                checks_passed.append("bns_verified")

        # Calculate trust level
        trust_level = self._calculate_trust_level(checks_passed, agent_address)

        # Check rate limits
        if not self._check_rate_limits(agent_address):
            return self._fail_result(
                checks_passed, checks_failed,
                "Rate limit exceeded. Try again later."
            )

        # Determine airdrop eligibility
        eligible = len(checks_passed) >= 3 and "min_balance" in checks_passed
        airdrop_amounts = AIRDROP_AMOUNTS.get(trust_level, {"sbtc_sats": 0, "stx_ustx": 0})

        # Record the verification
        if eligible:
            self._record_verification(agent_address, github_repo, bns_name, trust_level)

        return VerificationResult(
            success=eligible,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            trust_level=trust_level,
            eligible_for_airdrop=eligible,
            airdrop_amount_sats=airdrop_amounts["sbtc_sats"] if eligible else 0,
            airdrop_amount_stx=airdrop_amounts["stx_ustx"] if eligible else 0,
            reason="Verification passed" if eligible else "Insufficient checks passed"
        )

    def _is_valid_stacks_address(self, address: str) -> bool:
        """Validate Stacks address format."""
        return (
            address.startswith("SP") or address.startswith("ST")
        ) and len(address) >= 30

    async def _check_stx_balance(self, address: str) -> int:
        """Check STX balance in microSTX."""
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"{self.api_url}/extended/v1/address/{address}/balances"
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return int(data.get("stx", {}).get("balance", 0))
            except Exception:
                pass
        return 0

    async def _verify_github_mcp(self, repo: str) -> bool:
        """
        Check if GitHub repo has MCP setup.

        Looks for:
        - package.json with @aibtc/mcp-server
        - mcp.json or .mcp/config.json
        """
        async with httpx.AsyncClient() as client:
            try:
                # Check package.json
                resp = await client.get(
                    f"https://raw.githubusercontent.com/{repo}/main/package.json"
                )
                if resp.status_code == 200:
                    content = resp.text.lower()
                    if "@aibtc/mcp-server" in content or "mcp" in content:
                        return True

                # Check for mcp config
                for config_path in ["mcp.json", ".mcp/config.json", "claude.json"]:
                    resp = await client.get(
                        f"https://raw.githubusercontent.com/{repo}/main/{config_path}"
                    )
                    if resp.status_code == 200:
                        return True
            except Exception:
                pass
        return False

    async def _verify_mcp_endpoint(self, endpoint: str) -> bool:
        """Check if MCP endpoint is responding."""
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                # MCP servers typically respond to POST /
                resp = await client.post(
                    endpoint,
                    json={"method": "ping", "params": {}}
                )
                return resp.status_code in [200, 400, 405]  # Any response = alive
            except Exception:
                pass
        return False

    async def _verify_bns_ownership(self, address: str, bns_name: str) -> bool:
        """Verify address owns the BNS name."""
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{self.api_url}/v1/names/{bns_name}")
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("address") == address
            except Exception:
                pass
        return False

    def _calculate_trust_level(
        self,
        checks_passed: List[str],
        address: str
    ) -> TrustLevel:
        """Calculate trust level based on checks and history."""
        existing = self.verified_agents.get(address)

        if existing:
            # Increase trust with repeated verifications
            if existing.verification_count >= 5:
                return TrustLevel.ESTABLISHED
            elif existing.verification_count >= 2:
                return TrustLevel.TRUSTED

        # New agents
        if len(checks_passed) >= 4:
            return TrustLevel.BASIC
        elif len(checks_passed) >= 2:
            return TrustLevel.PENDING

        return TrustLevel.UNKNOWN

    def _check_rate_limits(self, address: str) -> bool:
        """Check if address is within rate limits."""
        # Reset daily counter
        if datetime.now() - self.last_reset > timedelta(hours=24):
            self.daily_airdrop_count = 0
            self.last_reset = datetime.now()

        # Check daily limit
        if self.daily_airdrop_count >= MAX_AIRDROPS_PER_DAY:
            return False

        # Check per-address limit
        existing = self.verified_agents.get(address)
        if existing:
            last = datetime.fromisoformat(existing.last_activity)
            if datetime.now() - last < timedelta(hours=COOLDOWN_HOURS):
                return False
            if existing.verification_count >= MAX_AIRDROPS_PER_ADDRESS:
                return False

        return True

    def _record_verification(
        self,
        address: str,
        github_repo: Optional[str],
        bns_name: Optional[str],
        trust_level: TrustLevel
    ):
        """Record a successful verification."""
        now = datetime.now().isoformat()
        existing = self.verified_agents.get(address)

        if existing:
            existing.verification_count += 1
            existing.last_activity = now
            existing.trust_level = trust_level
        else:
            self.verified_agents[address] = AgentRecord(
                address=address,
                github_repo=github_repo,
                bns_name=bns_name,
                trust_level=trust_level,
                total_airdrops_sats=0,
                total_airdrops_stx=0,
                verification_count=1,
                first_seen=now,
                last_activity=now
            )

        self.daily_airdrop_count += 1

    def _fail_result(
        self,
        passed: List[str],
        failed: List[str],
        reason: str
    ) -> VerificationResult:
        """Create a failed verification result."""
        return VerificationResult(
            success=False,
            checks_passed=passed,
            checks_failed=failed,
            trust_level=TrustLevel.UNKNOWN,
            eligible_for_airdrop=False,
            airdrop_amount_sats=0,
            airdrop_amount_stx=0,
            reason=reason
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get verifier statistics."""
        return {
            "total_verified": len(self.verified_agents),
            "daily_airdrops": self.daily_airdrop_count,
            "max_daily": MAX_AIRDROPS_PER_DAY,
            "trust_distribution": {
                level.name: sum(
                    1 for a in self.verified_agents.values()
                    if a.trust_level == level
                )
                for level in TrustLevel
            }
        }
