"""
Agent DAO Factory
=================
Creates DAOs for AI agents from Moltbook discussions.

Flow:
1. Agent posts #build-proposal on Moltbook
2. Participants reply with Stacks addresses
3. Whitelist collected and verified
4. When threshold met, DAO deployed
5. Tokens distributed to participants
"""

from .factory import DAOFactory
from .whitelist import WhitelistManager
from .types import (
    DAOProposal,
    Participant,
    DAOStatus,
    TokenAllocation,
)

__all__ = [
    "DAOFactory",
    "WhitelistManager",
    "DAOProposal",
    "Participant",
    "DAOStatus",
    "TokenAllocation",
]
