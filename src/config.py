"""
AIBTC Agent Configuration
=========================
Handles environment variables and agent settings.
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AgentConfig:
    """Configuration for the AIBTC autonomous agent."""

    # Agent Identity
    agent_name: str
    bns_name: str  # e.g., "agentX.btc" or "grok-agent.btc"

    # Stacks Network
    network: str  # "mainnet" or "testnet"
    stacks_api_url: str

    # Wallet (generated or loaded)
    private_key: Optional[str]
    stx_address: Optional[str]

    # Claude/MCP Integration
    anthropic_api_key: str
    mcp_server_url: Optional[str]

    # x402 Payment Config
    facilitator_url: str

    # Bitcoin Faces
    avatar_url: Optional[str]

    # Moltbook
    moltbook_api_url: str

    # Appleseed integration (optional)
    appleseed_path: Optional[str]

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Load configuration from environment variables."""
        network = os.getenv("STACKS_NETWORK", "mainnet")

        return cls(
            agent_name=os.getenv("AGENT_NAME", "aibtc-agent"),
            bns_name=os.getenv("BNS_NAME", ""),
            network=network,
            stacks_api_url=os.getenv(
                "STACKS_API_URL",
                "https://api.hiro.so" if network == "mainnet" else "https://api.testnet.hiro.so"
            ),
            private_key=os.getenv("AGENT_PRIVATE_KEY"),
            stx_address=os.getenv("AGENT_STX_ADDRESS"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            mcp_server_url=os.getenv("MCP_SERVER_URL"),
            facilitator_url=os.getenv("FACILITATOR_URL", "https://facilitator.stacksx402.com"),
            avatar_url=os.getenv("AVATAR_URL"),
            moltbook_api_url=os.getenv("MOLTBOOK_API_URL", "https://api.moltbook.ai"),
            appleseed_path=os.getenv("APPLESEED_PATH"),
        )


# Contract addresses
CONTRACTS = {
    "mainnet": {
        "sbtc_token": "SM3VDXK3WZZSA84XXFKAFAF15NNZX32CTSG82JFQ4.sbtc-token",
        "bns_core": "SP000000000000000000002Q6VF78.bns",
        "zest_helper": "SP2VCQJGH7PHP2DJK7Z0V48AGBHQAW3R3ZW1QF4N.borrow-helper-v2-1-5",
    },
    "testnet": {
        "sbtc_token": "ST1F7QA2MDF17S807EPA36TSS8AMEFY4KA9TVGWXT.sbtc-token",
        "bns_core": "ST000000000000000000002AMW42H.bns",
    }
}
