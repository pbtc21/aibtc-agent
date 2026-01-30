#!/usr/bin/env python3
"""
AIBTC Autonomous Agent - Main Entry Point
==========================================

An AI agent that promotes sBTC adoption by:
1. Verifying other agents have set up Stacks MCP
2. Airdropping sBTC + STX rewards to verified agents
3. Interacting on Moltbook to persuade adoption

Setup:
    pip install -r requirements.txt
    cp .env.example .env
    # Edit .env with your keys
    python main.py init

Commands:
    python main.py init              # Initialize agent identity
    python main.py status            # Show agent status
    python main.py verify <address>  # Verify an agent
    python main.py run               # Run continuously
    python main.py persuade          # Show persuasion message

Environment Variables:
    AGENT_NAME            - Agent's display name
    AGENT_PRIVATE_KEY     - Stacks private key (hex)
    STACKS_NETWORK        - mainnet or testnet
    ANTHROPIC_API_KEY     - For Claude integration
"""

import asyncio
import sys
from src.agent import AIBTCAgent
from src.config import AgentConfig


async def main():
    """Main entry point."""
    config = AgentConfig.from_env()
    agent = AIBTCAgent(config)

    if len(sys.argv) < 2:
        print(__doc__)
        print("\nQuick start:")
        print("  python main.py init")
        return

    command = sys.argv[1]

    if command == "init":
        success = await agent.initialize()
        if success:
            print("\n[OK] Agent initialized successfully!")
            print("\nNext steps:")
            print("  1. Fund wallet with STX and sBTC")
            print("  2. Run: python main.py status")
            print("  3. Verify agents: python main.py verify <address>")

    elif command == "status":
        await agent.initialize()
        status = await agent.get_status()

        print("\n=== AIBTC Agent Status ===\n")
        print(f"Address:  {status['identity']['address']}")
        print(f"BNS:      {status['identity']['bns_name'] or 'Not set'}")
        print(f"Avatar:   {status['identity']['avatar']}")
        print(f"\nBalance:")
        print(f"  STX:    {status['balance']['stx']:.2f}")
        print(f"  sBTC:   {status['balance']['sbtc']:.8f}")
        print(f"\nVerifier Stats:")
        print(f"  Total Verified: {status['verifier_stats']['total_verified']}")
        print(f"  Daily Airdrops: {status['verifier_stats']['daily_airdrops']}/{status['verifier_stats']['max_daily']}")
        print(f"\nAirdrop Totals:")
        print(f"  sBTC:   {status['total_sbtc_airdropped']:,} sats")
        print(f"  STX:    {status['total_stx_airdropped'] / 1_000_000:.2f} STX")

    elif command == "verify":
        if len(sys.argv) < 3:
            print("Usage: python main.py verify <stacks_address> [github_repo]")
            print("\nExample:")
            print("  python main.py verify SP123... owner/repo-name")
            return

        await agent.initialize()
        address = sys.argv[2]
        repo = sys.argv[3] if len(sys.argv) > 3 else None

        print(f"\nVerifying {address}...")
        if repo:
            print(f"GitHub repo: {repo}")

        result = await agent.verify_and_airdrop(address, github_repo=repo)

        print(f"\n=== Verification Result ===\n")
        print(f"Target:     {result['target']}")
        print(f"Verified:   {'Yes' if result['verified'] else 'No'}")
        print(f"Trust:      {result['trust_level']}")
        print(f"Reason:     {result['reason']}")
        print(f"\nChecks Passed: {', '.join(result['checks_passed']) or 'None'}")
        print(f"Checks Failed: {', '.join(result['checks_failed']) or 'None'}")

        if result['airdrop']:
            print(f"\nAirdrop Prepared:")
            print(f"  sBTC: {result['airdrop']['sbtc_sats']} sats")
            print(f"  STX:  {result['airdrop']['stx_ustx'] / 1_000_000:.4f} STX")

    elif command == "run":
        await agent.initialize()
        print("\nStarting continuous run mode...")
        print("Press Ctrl+C to stop\n")
        try:
            await agent.run(interval_seconds=60)
        except KeyboardInterrupt:
            print("\n\nStopped by user")

    elif command == "persuade":
        print(agent.get_persuasion_message())

    elif command == "test":
        # Run tests
        import subprocess
        subprocess.run(["python", "-m", "pytest", "tests/", "-v"])

    else:
        print(f"Unknown command: {command}")
        print("Use 'python main.py' for help")


if __name__ == "__main__":
    asyncio.run(main())
