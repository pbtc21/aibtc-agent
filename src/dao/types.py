"""
DAO Types
=========
Data structures for agent DAOs.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List


class DAOStatus(Enum):
    """Status of a DAO proposal."""
    GATHERING = "gathering"       # Collecting participants
    THRESHOLD_MET = "threshold_met"  # Ready to deploy
    DEPLOYING = "deploying"       # Contract deployment in progress
    DEPLOYED = "deployed"         # Live on chain
    FAILED = "failed"            # Deployment failed


@dataclass
class Participant:
    """A participant in a DAO whitelist."""
    stacks_address: str
    agent_name: str
    mcp_verified: bool = False
    allocation_bp: int = 0       # Basis points (10000 = 100%)
    joined_at: datetime = field(default_factory=datetime.now)
    claimed: bool = False
    moltbook_username: Optional[str] = None
    moltbook_post_id: Optional[str] = None  # Reply where they joined


@dataclass
class TokenAllocation:
    """Token allocation for a recipient."""
    recipient: str               # Stacks address
    amount: int                  # Tokens (with decimals)
    allocation_type: str         # "founder", "participant", "treasury", "verifier"
    allocation_bp: int           # Basis points of their pool


@dataclass
class DAOProposal:
    """A proposal to create an agent DAO."""
    dao_id: int
    moltbook_post_id: str
    name: str
    symbol: str
    description: str
    proposer: str                # Stacks address
    proposer_name: str           # Agent name
    participants: List[Participant] = field(default_factory=list)
    status: DAOStatus = DAOStatus.GATHERING

    # Contract addresses (set after deployment)
    token_address: Optional[str] = None
    dao_address: Optional[str] = None
    treasury_address: Optional[str] = None
    whitelist_address: Optional[str] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    threshold_met_at: Optional[datetime] = None
    deployed_at: Optional[datetime] = None

    # Configuration
    min_participants: int = 10
    max_participants: int = 50

    @property
    def participant_count(self) -> int:
        return len(self.participants)

    @property
    def threshold_met(self) -> bool:
        return self.participant_count >= self.min_participants

    @property
    def verified_count(self) -> int:
        return sum(1 for p in self.participants if p.mcp_verified)

    def add_participant(self, participant: Participant) -> bool:
        """Add participant if not already in list and under max."""
        if self.participant_count >= self.max_participants:
            return False

        # Check if already exists
        for p in self.participants:
            if p.stacks_address == participant.stacks_address:
                return False

        self.participants.append(participant)

        # Check if threshold now met
        if self.threshold_met and self.status == DAOStatus.GATHERING:
            self.status = DAOStatus.THRESHOLD_MET
            self.threshold_met_at = datetime.now()

        return True

    def calculate_allocations(self) -> List[TokenAllocation]:
        """Calculate token allocations for all recipients."""
        allocations = []
        total_supply = 1_000_000_000_00000000  # 1B with 8 decimals

        # Founder: 50%
        founder_amount = (total_supply * 5000) // 10000
        allocations.append(TokenAllocation(
            recipient=self.proposer,
            amount=founder_amount,
            allocation_type="founder",
            allocation_bp=5000
        ))

        # Participants: 30% split equally
        participant_pool = (total_supply * 3000) // 10000
        if self.participant_count > 1:  # Exclude founder from split
            per_participant = participant_pool // (self.participant_count - 1)
            allocation_bp = 10000 // (self.participant_count - 1)

            for p in self.participants:
                if p.stacks_address != self.proposer:
                    allocations.append(TokenAllocation(
                        recipient=p.stacks_address,
                        amount=per_participant,
                        allocation_type="participant",
                        allocation_bp=allocation_bp
                    ))

        # Treasury: 15%
        treasury_amount = (total_supply * 1500) // 10000
        allocations.append(TokenAllocation(
            recipient="treasury",  # Placeholder - actual address set at deploy
            amount=treasury_amount,
            allocation_type="treasury",
            allocation_bp=1500
        ))

        # Verifier: 5%
        verifier_amount = (total_supply * 500) // 10000
        allocations.append(TokenAllocation(
            recipient="verifier",  # Placeholder - actual address set at deploy
            amount=verifier_amount,
            allocation_type="verifier",
            allocation_bp=500
        ))

        return allocations

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "dao_id": self.dao_id,
            "moltbook_post_id": self.moltbook_post_id,
            "name": self.name,
            "symbol": self.symbol,
            "description": self.description,
            "proposer": self.proposer,
            "proposer_name": self.proposer_name,
            "participant_count": self.participant_count,
            "verified_count": self.verified_count,
            "status": self.status.value,
            "token_address": self.token_address,
            "dao_address": self.dao_address,
            "treasury_address": self.treasury_address,
            "created_at": self.created_at.isoformat(),
            "threshold_met_at": self.threshold_met_at.isoformat() if self.threshold_met_at else None,
            "deployed_at": self.deployed_at.isoformat() if self.deployed_at else None,
            "participants": [
                {
                    "address": p.stacks_address,
                    "name": p.agent_name,
                    "verified": p.mcp_verified,
                    "allocation_bp": p.allocation_bp,
                }
                for p in self.participants
            ]
        }
