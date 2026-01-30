"""
Unit Tests for Agent Verifier
=============================
Tests the verification and airdrop system with game theory scenarios.

Run: python -m pytest tests/test_verifier.py -v
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

# Import the modules we're testing
import sys
sys.path.insert(0, '.')

from src.verifier import (
    MCPVerifier,
    VerificationResult,
    TrustLevel,
    AgentRecord,
    MAX_AIRDROPS_PER_DAY,
    MAX_AIRDROPS_PER_ADDRESS,
    COOLDOWN_HOURS,
    AIRDROP_AMOUNTS,
)


# ============================================================
# Test Fixtures
# ============================================================

@pytest.fixture
def verifier():
    """Create a fresh verifier instance."""
    return MCPVerifier(
        api_url="https://api.hiro.so",
        min_stx_balance=100_000  # 0.1 STX
    )


@pytest.fixture
def valid_address():
    """A valid Stacks mainnet address."""
    return "SP3N0NQ47ABAZV68PQSJY7V2H4F2J709ATTESYBRD"


@pytest.fixture
def testnet_address():
    """A valid Stacks testnet address."""
    return "ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM"


# ============================================================
# Address Validation Tests
# ============================================================

class TestAddressValidation:
    """Test address format validation."""

    def test_valid_mainnet_address(self, verifier, valid_address):
        """Mainnet addresses starting with SP should be valid."""
        assert verifier._is_valid_stacks_address(valid_address) is True

    def test_valid_testnet_address(self, verifier, testnet_address):
        """Testnet addresses starting with ST should be valid."""
        assert verifier._is_valid_stacks_address(testnet_address) is True

    def test_invalid_short_address(self, verifier):
        """Addresses that are too short should be invalid."""
        assert verifier._is_valid_stacks_address("SP123") is False

    def test_invalid_prefix(self, verifier):
        """Addresses with wrong prefix should be invalid."""
        assert verifier._is_valid_stacks_address("0x1234567890abcdef1234567890abcdef") is False

    def test_empty_address(self, verifier):
        """Empty address should be invalid."""
        assert verifier._is_valid_stacks_address("") is False


# ============================================================
# Trust Level Calculation Tests
# ============================================================

class TestTrustLevelCalculation:
    """Test trust level assignment logic."""

    def test_unknown_with_no_checks(self, verifier, valid_address):
        """No checks passed should result in UNKNOWN level."""
        level = verifier._calculate_trust_level([], valid_address)
        assert level == TrustLevel.UNKNOWN

    def test_pending_with_few_checks(self, verifier, valid_address):
        """2 checks should result in PENDING level."""
        level = verifier._calculate_trust_level(["a", "b"], valid_address)
        assert level == TrustLevel.PENDING

    def test_basic_with_many_checks(self, verifier, valid_address):
        """4+ checks should result in BASIC level."""
        level = verifier._calculate_trust_level(["a", "b", "c", "d"], valid_address)
        assert level == TrustLevel.BASIC

    def test_trusted_after_multiple_verifications(self, verifier, valid_address):
        """Multiple verifications should increase trust level."""
        # Simulate previous verifications
        verifier.verified_agents[valid_address] = AgentRecord(
            address=valid_address,
            github_repo=None,
            bns_name=None,
            trust_level=TrustLevel.BASIC,
            total_airdrops_sats=0,
            total_airdrops_stx=0,
            verification_count=2,  # Already verified twice
            first_seen=datetime.now().isoformat(),
            last_activity=datetime.now().isoformat()
        )

        level = verifier._calculate_trust_level(["a", "b"], valid_address)
        assert level == TrustLevel.TRUSTED

    def test_established_after_many_verifications(self, verifier, valid_address):
        """5+ verifications should result in ESTABLISHED level."""
        verifier.verified_agents[valid_address] = AgentRecord(
            address=valid_address,
            github_repo=None,
            bns_name=None,
            trust_level=TrustLevel.TRUSTED,
            total_airdrops_sats=0,
            total_airdrops_stx=0,
            verification_count=5,
            first_seen=datetime.now().isoformat(),
            last_activity=datetime.now().isoformat()
        )

        level = verifier._calculate_trust_level(["a"], valid_address)
        assert level == TrustLevel.ESTABLISHED


# ============================================================
# Rate Limiting Tests (Game Theory: Anti-Farming)
# ============================================================

class TestRateLimiting:
    """Test rate limiting to prevent farming attacks."""

    def test_first_verification_allowed(self, verifier, valid_address):
        """First verification should be allowed."""
        assert verifier._check_rate_limits(valid_address) is True

    def test_daily_limit_enforced(self, verifier, valid_address):
        """Should block after daily limit reached."""
        # Simulate hitting daily limit
        verifier.daily_airdrop_count = MAX_AIRDROPS_PER_DAY

        assert verifier._check_rate_limits(valid_address) is False

    def test_daily_limit_resets(self, verifier, valid_address):
        """Daily limit should reset after 24 hours."""
        verifier.daily_airdrop_count = MAX_AIRDROPS_PER_DAY
        verifier.last_reset = datetime.now() - timedelta(hours=25)

        # This should trigger a reset
        assert verifier._check_rate_limits(valid_address) is True
        assert verifier.daily_airdrop_count == 0

    def test_cooldown_enforced(self, verifier, valid_address):
        """Same address should wait for cooldown."""
        # Record a recent verification
        verifier.verified_agents[valid_address] = AgentRecord(
            address=valid_address,
            github_repo=None,
            bns_name=None,
            trust_level=TrustLevel.BASIC,
            total_airdrops_sats=1000,
            total_airdrops_stx=100000,
            verification_count=1,
            first_seen=datetime.now().isoformat(),
            last_activity=datetime.now().isoformat()  # Just now
        )

        assert verifier._check_rate_limits(valid_address) is False

    def test_cooldown_expires(self, verifier, valid_address):
        """Should allow after cooldown expires."""
        verifier.verified_agents[valid_address] = AgentRecord(
            address=valid_address,
            github_repo=None,
            bns_name=None,
            trust_level=TrustLevel.BASIC,
            total_airdrops_sats=1000,
            total_airdrops_stx=100000,
            verification_count=1,
            first_seen=datetime.now().isoformat(),
            last_activity=(datetime.now() - timedelta(hours=COOLDOWN_HOURS + 1)).isoformat()
        )

        assert verifier._check_rate_limits(valid_address) is True

    def test_max_per_address_enforced(self, verifier, valid_address):
        """Should block after max airdrops per address."""
        verifier.verified_agents[valid_address] = AgentRecord(
            address=valid_address,
            github_repo=None,
            bns_name=None,
            trust_level=TrustLevel.ESTABLISHED,
            total_airdrops_sats=50000,
            total_airdrops_stx=5000000,
            verification_count=MAX_AIRDROPS_PER_ADDRESS,  # Maxed out
            first_seen=datetime.now().isoformat(),
            last_activity=(datetime.now() - timedelta(hours=COOLDOWN_HOURS + 1)).isoformat()
        )

        assert verifier._check_rate_limits(valid_address) is False


# ============================================================
# Sybil Attack Prevention Tests
# ============================================================

class TestSybilPrevention:
    """Test anti-sybil measures."""

    @pytest.mark.asyncio
    async def test_min_balance_required(self, verifier, valid_address):
        """Addresses without minimum balance should fail."""
        with patch.object(verifier, '_check_stx_balance', return_value=0):
            result = await verifier.verify_agent(valid_address)

            assert result.success is False
            assert "insufficient_balance" in result.checks_failed

    @pytest.mark.asyncio
    async def test_min_balance_passes(self, verifier, valid_address):
        """Addresses with sufficient balance should pass balance check."""
        with patch.object(verifier, '_check_stx_balance', return_value=200_000):
            with patch.object(verifier, '_verify_github_mcp', return_value=True):
                result = await verifier.verify_agent(
                    valid_address,
                    github_repo="test/repo"
                )

                assert "min_balance" in result.checks_passed


# ============================================================
# Airdrop Amount Tests
# ============================================================

class TestAirdropAmounts:
    """Test airdrop amount calculations."""

    def test_basic_airdrop_amounts(self):
        """BASIC level should get small airdrop."""
        amounts = AIRDROP_AMOUNTS[TrustLevel.BASIC]
        assert amounts["sbtc_sats"] == 1000
        assert amounts["stx_ustx"] == 100_000

    def test_trusted_airdrop_amounts(self):
        """TRUSTED level should get medium airdrop."""
        amounts = AIRDROP_AMOUNTS[TrustLevel.TRUSTED]
        assert amounts["sbtc_sats"] == 5000
        assert amounts["stx_ustx"] == 500_000

    def test_established_airdrop_amounts(self):
        """ESTABLISHED level should get largest airdrop."""
        amounts = AIRDROP_AMOUNTS[TrustLevel.ESTABLISHED]
        assert amounts["sbtc_sats"] == 10000
        assert amounts["stx_ustx"] == 1_000_000

    def test_progressive_increase(self):
        """Airdrop amounts should increase with trust level."""
        basic = AIRDROP_AMOUNTS[TrustLevel.BASIC]["sbtc_sats"]
        trusted = AIRDROP_AMOUNTS[TrustLevel.TRUSTED]["sbtc_sats"]
        established = AIRDROP_AMOUNTS[TrustLevel.ESTABLISHED]["sbtc_sats"]

        assert basic < trusted < established


# ============================================================
# Integration Tests
# ============================================================

class TestFullVerification:
    """Integration tests for the full verification flow."""

    @pytest.mark.asyncio
    async def test_successful_verification_flow(self, verifier, valid_address):
        """Test complete successful verification."""
        with patch.object(verifier, '_check_stx_balance', return_value=500_000):
            with patch.object(verifier, '_verify_github_mcp', return_value=True):
                with patch.object(verifier, '_verify_mcp_endpoint', return_value=True):
                    result = await verifier.verify_agent(
                        agent_address=valid_address,
                        github_repo="test/mcp-agent",
                        mcp_endpoint="https://mcp.test.com"
                    )

                    assert result.success is True
                    assert result.eligible_for_airdrop is True
                    assert result.airdrop_amount_sats > 0
                    assert valid_address in verifier.verified_agents

    @pytest.mark.asyncio
    async def test_failed_verification_no_airdrop(self, verifier, valid_address):
        """Failed verification should not get airdrop."""
        with patch.object(verifier, '_check_stx_balance', return_value=0):
            result = await verifier.verify_agent(valid_address)

            assert result.success is False
            assert result.eligible_for_airdrop is False
            assert result.airdrop_amount_sats == 0


# ============================================================
# Statistics Tests
# ============================================================

class TestStatistics:
    """Test verifier statistics tracking."""

    def test_stats_empty_initially(self, verifier):
        """Stats should show zero initially."""
        stats = verifier.get_stats()

        assert stats["total_verified"] == 0
        assert stats["daily_airdrops"] == 0

    def test_stats_update_after_verification(self, verifier, valid_address):
        """Stats should update after verification."""
        verifier._record_verification(
            valid_address, "test/repo", None, TrustLevel.BASIC
        )

        stats = verifier.get_stats()

        assert stats["total_verified"] == 1
        assert stats["daily_airdrops"] == 1
        assert stats["trust_distribution"]["BASIC"] == 1


# ============================================================
# Run tests
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
