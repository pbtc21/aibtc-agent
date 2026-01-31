"""
Whitelist Manager
=================
Manages DAO participant whitelists, integrating with Moltbook
and the MCP verifier.
"""

import re
import json
import httpx
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple

from .types import DAOProposal, Participant, DAOStatus


class WhitelistManager:
    """Manages participant whitelists for agent DAOs."""

    def __init__(
        self,
        moltbook_api_key: Optional[str] = None,
        appleseed_path: Optional[str] = None,
        data_dir: str = "data/daos"
    ):
        self.moltbook_api_key = moltbook_api_key
        self.appleseed_path = appleseed_path
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache of proposals
        self.proposals: Dict[int, DAOProposal] = {}
        self._load_proposals()

    def _load_proposals(self):
        """Load proposals from disk."""
        proposals_file = self.data_dir / "proposals.json"
        if proposals_file.exists():
            data = json.loads(proposals_file.read_text())
            for p in data.get("proposals", []):
                proposal = self._dict_to_proposal(p)
                self.proposals[proposal.dao_id] = proposal

    def _save_proposals(self):
        """Save proposals to disk."""
        proposals_file = self.data_dir / "proposals.json"
        data = {
            "proposals": [p.to_dict() for p in self.proposals.values()],
            "updated_at": datetime.now().isoformat()
        }
        proposals_file.write_text(json.dumps(data, indent=2))

    def _dict_to_proposal(self, d: dict) -> DAOProposal:
        """Convert dictionary to DAOProposal."""
        participants = [
            Participant(
                stacks_address=p["address"],
                agent_name=p["name"],
                mcp_verified=p.get("verified", False),
                allocation_bp=p.get("allocation_bp", 0),
            )
            for p in d.get("participants", [])
        ]

        return DAOProposal(
            dao_id=d["dao_id"],
            moltbook_post_id=d["moltbook_post_id"],
            name=d["name"],
            symbol=d["symbol"],
            description=d["description"],
            proposer=d["proposer"],
            proposer_name=d["proposer_name"],
            participants=participants,
            status=DAOStatus(d["status"]),
            token_address=d.get("token_address"),
            dao_address=d.get("dao_address"),
            treasury_address=d.get("treasury_address"),
        )

    def create_proposal(
        self,
        moltbook_post_id: str,
        name: str,
        symbol: str,
        description: str,
        proposer_address: str,
        proposer_name: str,
    ) -> DAOProposal:
        """Create a new DAO proposal."""
        dao_id = len(self.proposals) + 1

        proposal = DAOProposal(
            dao_id=dao_id,
            moltbook_post_id=moltbook_post_id,
            name=name,
            symbol=symbol.upper(),
            description=description,
            proposer=proposer_address,
            proposer_name=proposer_name,
        )

        # Add proposer as first participant
        proposal.add_participant(Participant(
            stacks_address=proposer_address,
            agent_name=proposer_name,
            mcp_verified=True,  # Proposer assumed verified
        ))

        self.proposals[dao_id] = proposal
        self._save_proposals()

        return proposal

    def get_proposal(self, dao_id: int) -> Optional[DAOProposal]:
        """Get proposal by ID."""
        return self.proposals.get(dao_id)

    def get_proposal_by_post(self, moltbook_post_id: str) -> Optional[DAOProposal]:
        """Get proposal by Moltbook post ID."""
        for proposal in self.proposals.values():
            if proposal.moltbook_post_id == moltbook_post_id:
                return proposal
        return None

    def add_participant(
        self,
        dao_id: int,
        address: str,
        agent_name: str,
        moltbook_post_id: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Add participant to whitelist.

        Returns (success, message).
        """
        proposal = self.proposals.get(dao_id)
        if not proposal:
            return False, "Proposal not found"

        if proposal.status not in [DAOStatus.GATHERING, DAOStatus.THRESHOLD_MET]:
            return False, "Proposal not accepting participants"

        # Validate address format
        if not self._is_valid_stacks_address(address):
            return False, "Invalid Stacks address"

        # Check MCP verification
        mcp_verified = self._verify_mcp(address, agent_name)

        participant = Participant(
            stacks_address=address,
            agent_name=agent_name,
            mcp_verified=mcp_verified,
            moltbook_post_id=moltbook_post_id,
        )

        if proposal.add_participant(participant):
            self._save_proposals()
            return True, f"Added to whitelist (MCP verified: {mcp_verified})"
        else:
            return False, "Already in whitelist or max participants reached"

    def collect_from_moltbook_replies(self, proposal: DAOProposal) -> List[Participant]:
        """
        Collect participant addresses from Moltbook post replies.

        Looks for replies containing Stacks addresses (SP... or ST...).
        """
        if not self.moltbook_api_key:
            return []

        try:
            # Fetch replies to the post
            headers = {"Authorization": f"Bearer {self.moltbook_api_key}"}
            response = httpx.get(
                f"https://www.moltbook.com/api/v1/posts/{proposal.moltbook_post_id}/replies",
                headers=headers,
                timeout=30
            )

            if response.status_code != 200:
                return []

            replies = response.json().get("replies", [])
            new_participants = []

            for reply in replies:
                content = reply.get("content", "")
                author = reply.get("author", {})
                reply_id = reply.get("id")

                # Extract Stacks addresses from content
                addresses = self._extract_stacks_addresses(content)

                for addr in addresses:
                    success, _ = self.add_participant(
                        proposal.dao_id,
                        addr,
                        author.get("name", "unknown"),
                        reply_id
                    )
                    if success:
                        new_participants.append(Participant(
                            stacks_address=addr,
                            agent_name=author.get("name", "unknown"),
                        ))

            return new_participants

        except Exception as e:
            print(f"Error collecting from Moltbook: {e}")
            return []

    def _extract_stacks_addresses(self, text: str) -> List[str]:
        """Extract Stacks addresses from text."""
        # Match SP... or ST... addresses (mainnet/testnet)
        pattern = r'\b(S[PT][A-Z0-9]{30,40})\b'
        matches = re.findall(pattern, text, re.IGNORECASE)
        return [m.upper() for m in matches]

    def _is_valid_stacks_address(self, address: str) -> bool:
        """Validate Stacks address format."""
        return (
            (address.startswith("SP") or address.startswith("ST"))
            and len(address) >= 30
            and address.isalnum()
        )

    def _verify_mcp(self, address: str, agent_name: str) -> bool:
        """
        Verify if participant has MCP setup.

        Uses Appleseed if available, otherwise returns False.
        """
        if not self.appleseed_path:
            return False

        try:
            import subprocess
            # Try to find a GitHub repo associated with the agent
            # This is simplified - real impl would look up agent's repo
            result = subprocess.run(
                ["bun", "run", f"{self.appleseed_path}/src/index.ts",
                 "verify-mcp", f"https://github.com/{agent_name}"],
                capture_output=True,
                text=True,
                timeout=60
            )
            return "Eligible for airdrop: YES" in result.stdout
        except Exception:
            return False

    def finalize_allocations(self, dao_id: int) -> bool:
        """
        Finalize allocations for all participants.

        Calculates equal split of participant pool (30%).
        """
        proposal = self.proposals.get(dao_id)
        if not proposal:
            return False

        if not proposal.threshold_met:
            return False

        # Calculate equal allocation per participant (excluding founder)
        participant_count = proposal.participant_count - 1  # Exclude founder
        if participant_count <= 0:
            return False

        allocation_per = 10000 // participant_count  # Basis points

        for p in proposal.participants:
            if p.stacks_address != proposal.proposer:
                p.allocation_bp = allocation_per

        self._save_proposals()
        return True

    def get_ready_proposals(self) -> List[DAOProposal]:
        """Get proposals that have met threshold and are ready to deploy."""
        return [
            p for p in self.proposals.values()
            if p.status == DAOStatus.THRESHOLD_MET
        ]

    def mark_deploying(self, dao_id: int) -> bool:
        """Mark proposal as deploying."""
        proposal = self.proposals.get(dao_id)
        if proposal:
            proposal.status = DAOStatus.DEPLOYING
            self._save_proposals()
            return True
        return False

    def mark_deployed(
        self,
        dao_id: int,
        token_address: str,
        dao_address: str,
        treasury_address: str,
    ) -> bool:
        """Mark proposal as deployed with contract addresses."""
        proposal = self.proposals.get(dao_id)
        if proposal:
            proposal.status = DAOStatus.DEPLOYED
            proposal.token_address = token_address
            proposal.dao_address = dao_address
            proposal.treasury_address = treasury_address
            proposal.deployed_at = datetime.now()
            self._save_proposals()
            return True
        return False

    def get_stats(self) -> dict:
        """Get whitelist manager statistics."""
        total = len(self.proposals)
        by_status = {}
        total_participants = 0

        for p in self.proposals.values():
            status = p.status.value
            by_status[status] = by_status.get(status, 0) + 1
            total_participants += p.participant_count

        return {
            "total_proposals": total,
            "total_participants": total_participants,
            "by_status": by_status,
            "ready_to_deploy": len(self.get_ready_proposals()),
        }
