#!/bin/bash
# ============================================================
# AIBTC Agent - Mac Mini Deployment Script
# ============================================================
# Sets up the agent to run as a background service on macOS
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENT_DIR="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="$HOME/aibtc-agent"
PLIST_NAME="com.aibtc.agent"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

echo "=== AIBTC Agent Mac Mini Setup ==="
echo ""

# Step 1: Copy agent to install directory
echo "[1/5] Installing agent to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cp -r "$AGENT_DIR"/* "$INSTALL_DIR/"
cd "$INSTALL_DIR"

# Step 2: Set up Python virtual environment
echo ""
echo "[2/5] Setting up Python environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Step 3: Create .env if not exists
echo ""
echo "[3/5] Configuring environment..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Created .env from template"
    echo ""
    echo "IMPORTANT: Edit $INSTALL_DIR/.env with your configuration:"
    echo "  - AGENT_PRIVATE_KEY"
    echo "  - AGENT_STX_ADDRESS"
    echo "  - APPLESEED_PATH (optional)"
fi

# Step 4: Create launchd plist
echo ""
echo "[4/5] Creating launchd service..."

cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>

    <key>ProgramArguments</key>
    <array>
        <string>$INSTALL_DIR/.venv/bin/python</string>
        <string>$INSTALL_DIR/main.py</string>
        <string>run</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>

    <key>RunAtLoad</key>
    <false/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/logs/agent.log</string>

    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/logs/agent.error.log</string>

    <key>ThrottleInterval</key>
    <integer>60</integer>
</dict>
</plist>
EOF

mkdir -p "$INSTALL_DIR/logs"
echo "Created $PLIST_PATH"

# Step 5: Print instructions
echo ""
echo "[5/5] Setup complete!"
echo ""
echo "=== Next Steps ==="
echo ""
echo "1. Edit configuration:"
echo "   nano $INSTALL_DIR/.env"
echo ""
echo "2. Fund your agent wallet with STX and sBTC"
echo ""
echo "3. Initialize agent:"
echo "   cd $INSTALL_DIR && .venv/bin/python main.py init"
echo ""
echo "4. Test verification:"
echo "   .venv/bin/python main.py verify SP123... owner/repo"
echo ""
echo "5. Start the service:"
echo "   launchctl load $PLIST_PATH"
echo "   launchctl start $PLIST_NAME"
echo ""
echo "6. Check logs:"
echo "   tail -f $INSTALL_DIR/logs/agent.log"
echo ""
echo "=== Service Commands ==="
echo "  Start:   launchctl start $PLIST_NAME"
echo "  Stop:    launchctl stop $PLIST_NAME"
echo "  Status:  launchctl list | grep aibtc"
echo "  Unload:  launchctl unload $PLIST_PATH"
echo ""
