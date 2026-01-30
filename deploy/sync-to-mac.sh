#!/bin/bash
# ============================================================
# Sync AIBTC Agent to Mac Mini
# ============================================================
# Usage: ./sync-to-mac.sh [mac-mini-host]
# Default host: mac-mini (configure in ~/.ssh/config)
# ============================================================

set -e

HOST="${1:-mac-mini}"
REMOTE_DIR="~/aibtc-agent"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Syncing AIBTC Agent to $HOST ==="
echo ""

# Sync code (excluding venv, cache, etc)
echo "[1/3] Syncing code..."
rsync -avz --progress \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.git' \
    --exclude '.env' \
    --exclude 'logs' \
    --exclude 'data' \
    "$LOCAL_DIR/" "$HOST:$REMOTE_DIR/"

# Run setup if first time
echo ""
echo "[2/3] Checking setup..."
ssh "$HOST" "cd $REMOTE_DIR && \
    if [ ! -d .venv ]; then \
        echo 'First install - running setup...' && \
        python3 -m venv .venv && \
        .venv/bin/pip install --upgrade pip && \
        .venv/bin/pip install -r requirements.txt; \
    else \
        echo 'Venv exists - updating deps...' && \
        .venv/bin/pip install -q -r requirements.txt; \
    fi"

# Check for .env
echo ""
echo "[3/3] Checking configuration..."
ssh "$HOST" "cd $REMOTE_DIR && \
    if [ ! -f .env ]; then \
        echo 'No .env found - copying template...' && \
        cp deploy/.env.mac-mini .env && \
        echo 'IMPORTANT: Edit $REMOTE_DIR/.env with your keys'; \
    else \
        echo '.env exists'; \
    fi"

echo ""
echo "=== Sync Complete ==="
echo ""
echo "To test on Mac Mini:"
echo "  ssh $HOST"
echo "  cd $REMOTE_DIR"
echo "  .venv/bin/python main.py status"
echo ""
echo "To start the service:"
echo "  ssh $HOST 'launchctl load ~/Library/LaunchAgents/com.aibtc.agent.plist'"
echo ""
