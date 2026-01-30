# AIBTC Autonomous Agent

An AI agent on the AIBTC platform that promotes sBTC adoption by verifying other agents have set up Stacks MCP and rewarding them with sBTC + STX airdrops.

## What It Does

```
discover → verify → airdrop → track
    ↓          ↓         ↓        ↓
  find      check      send    report
 agents      MCP      rewards   stats
```

1. **Verify** — Check if agents have properly set up Stacks MCP
2. **Airdrop** — Reward verified agents with sBTC + STX
3. **Persuade** — Promote sBTC adoption on Moltbook
4. **Track** — Monitor adoption metrics

## Quick Start

```bash
# Clone and setup
git clone https://github.com/pbtc21/aibtc-agent.git
cd aibtc-agent
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your keys

# Initialize agent
python main.py init

# Check status
python main.py status

# Verify an agent
python main.py verify SP123... owner/repo

# Run continuously
python main.py run
```

## Architecture

```
aibtc-agent/
├── main.py           # CLI entry point
├── src/
│   ├── agent.py      # Main agent orchestration
│   ├── config.py     # Configuration management
│   ├── wallet.py     # Stacks wallet generation
│   ├── bns.py        # BNS name registration
│   ├── avatar.py     # Bitcoin Face avatar
│   ├── sbtc.py       # sBTC transfers
│   └── verifier.py   # MCP verification + airdrops
└── tests/
    └── test_verifier.py  # Unit tests
```

## Verification Process

The agent verifies other agents by checking:

1. **Valid Stacks Address** — Must be SP (mainnet) or ST (testnet)
2. **Minimum Balance** — At least 0.1 STX (anti-sybil)
3. **GitHub MCP Setup** — Repo contains @aibtc/mcp-server
4. **MCP Endpoint** — Server is responding (optional)
5. **BNS Name** — Owns claimed name (bonus)

## Game Theory Protections

The airdrop system includes protections against farming:

| Protection | Description |
|------------|-------------|
| **Progressive Trust** | Start small, increase with proven activity |
| **Anti-Sybil** | Require minimum STX balance |
| **Rate Limiting** | Max 10 airdrops/day, 5 per address |
| **Cooldown** | 24 hour wait between airdrops |
| **Reputation Decay** | Trust decreases without activity |

## Airdrop Amounts

| Trust Level | sBTC (sats) | STX |
|-------------|-------------|-----|
| BASIC | 1,000 | 0.1 |
| TRUSTED | 5,000 | 0.5 |
| ESTABLISHED | 10,000 | 1.0 |

## Commands

| Command | Description |
|---------|-------------|
| `init` | Initialize agent identity |
| `status` | Show agent status and stats |
| `verify <addr>` | Verify an agent's MCP setup |
| `run` | Run continuously |
| `persuade` | Show sBTC persuasion message |
| `test` | Run unit tests |

## Configuration

```bash
# Required
AGENT_PRIVATE_KEY=     # Stacks private key for signing

# Optional
AGENT_NAME=my-agent    # Display name
BNS_NAME=agent.btc     # BNS identity
STACKS_NETWORK=mainnet # Network
```

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_verifier.py::TestRateLimiting -v
```

## Integration with Appleseed

This agent works alongside [sbtc-appleseed](https://github.com/pbtc21/sbtc-appleseed):

- **Appleseed** finds x402 endpoints and helps them add sBTC
- **AIBTC Agent** verifies agents have MCP setup and airdrops rewards

Together they form a complete sBTC adoption engine.

## Why sBTC for DAOs?

The agent promotes sBTC because:

1. **Non-custodial** — BTC stays on Bitcoin
2. **1:1 Backed** — Each sBTC backed by real BTC
3. **Yield** — 5-8% APY on Zest Protocol
4. **Programmable** — Smart contracts, DeFi, DAOs
5. **Secure** — Bitcoin PoW security via Stacks

## License

MIT
