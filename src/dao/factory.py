"""
DAO Factory
===========
Deploys agent DAOs from proposals that have met participant threshold.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List
from datetime import datetime

from .types import DAOProposal, DAOStatus, TokenAllocation
from .whitelist import WhitelistManager


class DAOFactory:
    """
    Factory for deploying agent DAOs.

    Uses aibtcdev-daos contracts as base, customized per DAO.
    """

    def __init__(
        self,
        whitelist_manager: WhitelistManager,
        contracts_dir: str = "contracts/templates",
        network: str = "mainnet",
        deployer_key: Optional[str] = None,
        verifier_address: Optional[str] = None,
    ):
        self.whitelist = whitelist_manager
        self.contracts_dir = Path(contracts_dir)
        self.network = network
        self.deployer_key = deployer_key or os.getenv("AGENT_PRIVATE_KEY")
        self.verifier_address = verifier_address or os.getenv("AGENT_STX_ADDRESS")

    def deploy_dao(self, dao_id: int) -> Tuple[bool, str, dict]:
        """
        Deploy a DAO from a proposal.

        Returns (success, message, deployment_info).
        """
        proposal = self.whitelist.get_proposal(dao_id)
        if not proposal:
            return False, "Proposal not found", {}

        if not proposal.threshold_met:
            return False, "Threshold not met", {}

        if proposal.status == DAOStatus.DEPLOYED:
            return False, "Already deployed", {}

        # Mark as deploying
        self.whitelist.mark_deploying(dao_id)

        try:
            # Step 1: Finalize allocations
            self.whitelist.finalize_allocations(dao_id)

            # Step 2: Generate customized contracts
            contracts = self._generate_contracts(proposal)

            # Step 3: Deploy contracts (simulated for now)
            # In production, this would use Clarinet or direct API
            deployment = self._deploy_contracts(proposal, contracts)

            if not deployment["success"]:
                proposal.status = DAOStatus.FAILED
                return False, deployment["error"], {}

            # Step 4: Distribute tokens
            distributions = self._distribute_tokens(proposal, deployment)

            # Step 5: Mark as deployed
            self.whitelist.mark_deployed(
                dao_id,
                deployment["token_address"],
                deployment["dao_address"],
                deployment["treasury_address"],
            )

            return True, "DAO deployed successfully", {
                "dao_id": dao_id,
                "name": proposal.name,
                "symbol": proposal.symbol,
                "token_address": deployment["token_address"],
                "dao_address": deployment["dao_address"],
                "treasury_address": deployment["treasury_address"],
                "participants": proposal.participant_count,
                "distributions": distributions,
            }

        except Exception as e:
            proposal.status = DAOStatus.FAILED
            return False, f"Deployment failed: {str(e)}", {}

    def _generate_contracts(self, proposal: DAOProposal) -> dict:
        """
        Generate customized contracts for the DAO.

        Replaces placeholders in templates with DAO-specific values.
        """
        # Load token template
        token_template = (self.contracts_dir / "agent-dao-token.clar").read_text()

        # Customize for this DAO
        token_contract = token_template.replace(
            'TOKEN_NAME "Agent DAO Token"',
            f'TOKEN_NAME "{proposal.name}"'
        ).replace(
            'TOKEN_SYMBOL "ADT"',
            f'TOKEN_SYMBOL "{proposal.symbol}"'
        ).replace(
            'TOKEN_URI (some u"https://aibtc.dev/tokens/agent-dao.json")',
            f'TOKEN_URI (some u"https://aibtc.dev/tokens/{proposal.symbol.lower()}.json")'
        )

        return {
            "token": token_contract,
            "name": proposal.name,
            "symbol": proposal.symbol,
        }

    def _deploy_contracts(self, proposal: DAOProposal, contracts: dict) -> dict:
        """
        Deploy contracts to Stacks.

        In MVP, this generates deployment instructions.
        In production, this would use Clarinet deploy or Stacks API.
        """
        # For MVP: Generate deployment manifest
        # Real deployment would use:
        # - Clarinet for testnet: clarinet deploy --testnet
        # - Stacks.js for mainnet: broadcastTransaction()

        # Simulated addresses (would be real after deployment)
        prefix = "SP" if self.network == "mainnet" else "ST"
        base = "AGENT" + proposal.symbol.upper()[:8]

        return {
            "success": True,
            "token_address": f"{prefix}{base}TOKEN",
            "dao_address": f"{prefix}{base}DAO",
            "treasury_address": f"{prefix}{base}TREASURY",
            "tx_ids": [],
            "deployed_at": datetime.now().isoformat(),
        }

    def _distribute_tokens(
        self,
        proposal: DAOProposal,
        deployment: dict
    ) -> List[dict]:
        """
        Distribute tokens to participants.

        Returns list of distribution records.
        """
        allocations = proposal.calculate_allocations()
        distributions = []

        for alloc in allocations:
            # Set actual addresses for treasury and verifier
            recipient = alloc.recipient
            if recipient == "treasury":
                recipient = deployment["treasury_address"]
            elif recipient == "verifier":
                recipient = self.verifier_address or deployment["dao_address"]

            distributions.append({
                "recipient": recipient,
                "amount": alloc.amount,
                "type": alloc.allocation_type,
                "allocation_bp": alloc.allocation_bp,
                "tokens_formatted": f"{alloc.amount / 100_000_000:,.2f}",
            })

        return distributions

    def preview_deployment(self, dao_id: int) -> dict:
        """
        Preview what would happen if DAO were deployed.

        Useful for verification before actual deployment.
        """
        proposal = self.whitelist.get_proposal(dao_id)
        if not proposal:
            return {"error": "Proposal not found"}

        allocations = proposal.calculate_allocations()

        return {
            "dao_id": dao_id,
            "name": proposal.name,
            "symbol": proposal.symbol,
            "status": proposal.status.value,
            "threshold_met": proposal.threshold_met,
            "participant_count": proposal.participant_count,
            "verified_count": proposal.verified_count,
            "allocations": [
                {
                    "recipient": a.recipient,
                    "type": a.allocation_type,
                    "tokens": f"{a.amount / 100_000_000:,.2f}",
                    "percent": f"{a.allocation_bp / 100:.1f}%",
                }
                for a in allocations
            ],
            "total_supply": "1,000,000,000",
            "network": self.network,
        }

    def generate_deployment_script(self, dao_id: int) -> str:
        """
        Generate a Clarinet deployment script for manual deployment.

        Useful when automated deployment isn't available.
        """
        proposal = self.whitelist.get_proposal(dao_id)
        if not proposal:
            return "# Error: Proposal not found"

        contracts = self._generate_contracts(proposal)
        allocations = proposal.calculate_allocations()

        script = f"""#!/bin/bash
# ============================================================
# {proposal.name} DAO Deployment Script
# Generated: {datetime.now().isoformat()}
# ============================================================

# Prerequisites:
# - Clarinet installed
# - Testnet/Mainnet credentials configured

cd {proposal.symbol.lower()}-dao

# Deploy token contract
clarinet deploy {proposal.symbol.lower()}-token.clar --{"testnet" if self.network == "testnet" else "mainnet"}

# Wait for confirmation
sleep 30

# Distribute tokens
echo "Distributing tokens..."

"""
        for alloc in allocations:
            script += f"""
# {alloc.allocation_type}: {alloc.amount / 100_000_000:,.0f} tokens
# Recipient: {alloc.recipient}
"""

        script += """
echo "Deployment complete!"
echo "Token: $TOKEN_ADDRESS"
echo "DAO: $DAO_ADDRESS"
"""

        return script

    def create_dao_from_moltbook(
        self,
        post_id: str,
        name: str,
        symbol: str,
        description: str,
        proposer_address: str,
        proposer_name: str,
    ) -> DAOProposal:
        """
        Create a new DAO proposal from a Moltbook post.

        This is the main entry point for the Moltbook → DAO flow.
        """
        return self.whitelist.create_proposal(
            moltbook_post_id=post_id,
            name=name,
            symbol=symbol,
            description=description,
            proposer_address=proposer_address,
            proposer_name=proposer_name,
        )

    def check_and_deploy_ready(self) -> List[dict]:
        """
        Check for proposals ready to deploy and deploy them.

        Returns list of deployment results.
        """
        ready = self.whitelist.get_ready_proposals()
        results = []

        for proposal in ready:
            success, message, info = self.deploy_dao(proposal.dao_id)
            results.append({
                "dao_id": proposal.dao_id,
                "name": proposal.name,
                "success": success,
                "message": message,
                "info": info,
            })

        return results

    def get_stats(self) -> dict:
        """Get factory statistics."""
        stats = self.whitelist.get_stats()
        stats["network"] = self.network
        stats["contracts_dir"] = str(self.contracts_dir)
        return stats
