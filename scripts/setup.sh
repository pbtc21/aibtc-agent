#!/bin/bash
# ============================================================
# AIBTC Agent Setup Script
# ============================================================
# This script sets up the full AIBTC agent environment:
# 1. Install Claude Code
# 2. Add Stacks MCP tools
# 3. Create wallet
# 4. Generate avatar
# ============================================================

set -e

echo "=== AIBTC Agent Setup ==="
echo ""

# Step 1: Install Claude Code
echo "[1/4] Installing Claude Code..."
if ! command -v claude &> /dev/null; then
    curl -fsSL https://claude.ai/install.sh | sh
    echo "Claude Code installed"
else
    echo "Claude Code already installed"
fi

# Step 2: Add Stacks MCP tools
echo ""
echo "[2/4] Setting up Stacks MCP..."

# Check for existing MCP config
MCP_CONFIG="$HOME/.mcp.json"
if [ ! -f "$MCP_CONFIG" ]; then
    echo "Creating MCP config..."
    cat > "$MCP_CONFIG" << 'EOF'
{
  "mcpServers": {
    "stacks": {
      "command": "npx",
      "args": ["-y", "@aibtc/mcp-server"],
      "env": {
        "STACKS_NETWORK": "mainnet"
      }
    }
  }
}
EOF
    echo "MCP config created at $MCP_CONFIG"
else
    echo "MCP config already exists"
    echo "Add @aibtc/mcp-server manually if needed"
fi

# Step 3: Install Python dependencies
echo ""
echo "[3/4] Installing Python dependencies..."
pip install -r requirements.txt 2>/dev/null || pip3 install -r requirements.txt

# Step 4: Initialize agent
echo ""
echo "[4/4] Initializing agent..."

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Created .env from template"
    echo ""
    echo "IMPORTANT: Edit .env with your configuration"
fi

# Generate wallet if needed
if grep -q "AGENT_PRIVATE_KEY=$" .env 2>/dev/null; then
    echo ""
    echo "Generating new wallet..."
    python3 -c "
from src.wallet import create_wallet
w = create_wallet('mainnet')
print(f'Address: {w.stx_address}')
print(f'Private Key: {w.private_key}')
print()
print('Add to .env:')
print(f'AGENT_PRIVATE_KEY={w.private_key}')
print(f'AGENT_STX_ADDRESS={w.stx_address}')
"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env with your configuration"
echo "  2. Fund your wallet with STX and sBTC"
echo "  3. Run: python main.py init"
echo "  4. Run: python main.py status"
echo ""
echo "For help: python main.py"
