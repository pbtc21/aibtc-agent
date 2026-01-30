# Mac Mini Deployment

Deploy aibtc-agent to run on your Mac Mini with Moltbot.

## Quick Start

```bash
# From this VM - sync to Mac Mini
./sync-to-mac.sh mac-mini

# Then SSH to Mac Mini
ssh mac-mini
cd ~/aibtc-agent

# Edit config
nano .env

# Initialize
.venv/bin/python main.py init

# Test
.venv/bin/python main.py status
.venv/bin/python main.py verify SP3N0NQ47ABAZV68PQSJY7V2H4F2J709ATTESYBRD pbtc21/aibtc-agent
```

## Files

| File | Purpose |
|------|---------|
| `sync-to-mac.sh` | Rsync code to Mac Mini |
| `mac-mini-setup.sh` | Full install (run on Mac) |
| `.env.mac-mini` | Template config for Mac |
| `moltbot-integration.ts` | TS wrapper for Moltbot skills |

## Service Management

```bash
# Load service
launchctl load ~/Library/LaunchAgents/com.aibtc.agent.plist

# Start/stop
launchctl start com.aibtc.agent
launchctl stop com.aibtc.agent

# Check status
launchctl list | grep aibtc

# View logs
tail -f ~/aibtc-agent/logs/agent.log
```

## Moltbot Integration

Copy `moltbot-integration.ts` to your moltbot-skills and use:

```typescript
import { verifyAgent, handleVerifyMcpCommand } from './moltbot-integration';

// In your skill handler:
case 'verify-mcp':
  return await handleVerifyMcpCommand(input, userId, chatId);
```

## Requirements

- Python 3.10+
- STX + sBTC in agent wallet for airdrops
- (Optional) Appleseed for enhanced verification
