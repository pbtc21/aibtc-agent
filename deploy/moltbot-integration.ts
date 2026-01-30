/**
 * AIBTC Agent - Moltbot Integration
 * ==================================
 * Wraps the Python aibtc-agent for use within Moltbot skills.
 *
 * Copy this to your moltbot-skills directory and import where needed.
 */

import { spawn } from 'child_process';
import { join } from 'path';

// Configure the path to your aibtc-agent installation
const AGENT_PATH = process.env.AIBTC_AGENT_PATH || join(process.env.HOME || '', 'aibtc-agent');
const PYTHON_PATH = join(AGENT_PATH, '.venv', 'bin', 'python');

export interface VerifyResult {
  target: string;
  verified: boolean;
  trustLevel: string;
  reason: string;
  checksPassed: string[];
  checksFailed: string[];
  airdrop: {
    sbtcSats: number;
    stxUstx: number;
  } | null;
}

export interface AgentStatus {
  identity: {
    address: string;
    bnsName: string | null;
    avatar: string;
  };
  balance: {
    stx: number;
    sbtc: number;
  };
  verifierStats: {
    totalVerified: number;
    dailyAirdrops: number;
    maxDaily: number;
  };
  totalSbtcAirdropped: number;
  totalStxAirdropped: number;
}

/**
 * Run a command on the Python agent and return the result.
 */
async function runAgentCommand(args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    const proc = spawn(PYTHON_PATH, [join(AGENT_PATH, 'main.py'), ...args], {
      cwd: AGENT_PATH,
      env: { ...process.env },
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (code === 0) {
        resolve(stdout);
      } else {
        reject(new Error(`Agent exited with code ${code}: ${stderr}`));
      }
    });

    proc.on('error', (err) => {
      reject(err);
    });
  });
}

/**
 * Verify an agent's MCP setup and determine airdrop eligibility.
 */
export async function verifyAgent(
  stacksAddress: string,
  githubRepo?: string
): Promise<VerifyResult> {
  const args = ['verify', stacksAddress];
  if (githubRepo) {
    args.push(githubRepo);
  }

  const output = await runAgentCommand(args);

  // Parse the output (simplified - real impl would parse structured output)
  const verified = output.includes('Verified:   Yes');
  const trustMatch = output.match(/Trust:\s+(\w+)/);
  const reasonMatch = output.match(/Reason:\s+(.+)/);

  return {
    target: stacksAddress,
    verified,
    trustLevel: trustMatch?.[1] || 'UNKNOWN',
    reason: reasonMatch?.[1] || 'Unknown',
    checksPassed: [],
    checksFailed: [],
    airdrop: verified ? {
      sbtcSats: 1000, // Would parse from output
      stxUstx: 100000,
    } : null,
  };
}

/**
 * Get the agent's current status.
 */
export async function getAgentStatus(): Promise<AgentStatus> {
  const output = await runAgentCommand(['status']);

  // Parse the output (simplified)
  const addressMatch = output.match(/Address:\s+(SP\w+)/);
  const stxMatch = output.match(/STX:\s+([\d.]+)/);
  const sbtcMatch = output.match(/sBTC:\s+([\d.]+)/);
  const verifiedMatch = output.match(/Total Verified:\s+(\d+)/);

  return {
    identity: {
      address: addressMatch?.[1] || '',
      bnsName: null,
      avatar: 'generated',
    },
    balance: {
      stx: parseFloat(stxMatch?.[1] || '0'),
      sbtc: parseFloat(sbtcMatch?.[1] || '0'),
    },
    verifierStats: {
      totalVerified: parseInt(verifiedMatch?.[1] || '0', 10),
      dailyAirdrops: 0,
      maxDaily: 10,
    },
    totalSbtcAirdropped: 0,
    totalStxAirdropped: 0,
  };
}

/**
 * Initialize the agent (create wallet, etc).
 */
export async function initAgent(): Promise<string> {
  return await runAgentCommand(['init']);
}

/**
 * Moltbot skill handler for /verify-mcp command.
 */
export async function handleVerifyMcpCommand(
  input: string,
  userId: string,
  chatId: string
): Promise<string> {
  // Parse: /verify-mcp SP123... [owner/repo]
  const parts = input.trim().split(/\s+/);
  const address = parts[1];
  const repo = parts[2];

  if (!address || !address.startsWith('SP')) {
    return [
      '❌ **Usage**',
      '',
      '`/verify-mcp <stacks-address> [github-repo]`',
      '',
      'Example:',
      '`/verify-mcp SP3N0NQ... owner/repo`',
    ].join('\n');
  }

  try {
    const result = await verifyAgent(address, repo);

    if (result.verified) {
      return [
        '✅ **Agent Verified**',
        '',
        `Address: \`${result.target}\``,
        `Trust Level: ${result.trustLevel}`,
        '',
        '**Airdrop Prepared:**',
        `• sBTC: ${result.airdrop?.sbtcSats.toLocaleString()} sats`,
        `• STX: ${(result.airdrop?.stxUstx || 0) / 1_000_000} STX`,
        '',
        '_Airdrop will be sent on next batch._',
      ].join('\n');
    } else {
      return [
        '❌ **Verification Failed**',
        '',
        `Address: \`${result.target}\``,
        `Reason: ${result.reason}`,
        '',
        '**Requirements:**',
        '• Valid Stacks address',
        '• Minimum 0.1 STX balance',
        '• GitHub repo with @aibtc/mcp-server',
        '',
        'See https://aibtc.com for setup guide.',
      ].join('\n');
    }
  } catch (error) {
    return `❌ Error: ${(error as Error).message}`;
  }
}

/**
 * Moltbot skill handler for /agent-status command.
 */
export async function handleAgentStatusCommand(): Promise<string> {
  try {
    const status = await getAgentStatus();

    return [
      '🤖 **AIBTC Verifier Agent**',
      '',
      `Address: \`${status.identity.address}\``,
      '',
      '**Balance:**',
      `• STX: ${status.balance.stx.toFixed(2)}`,
      `• sBTC: ${status.balance.sbtc.toFixed(8)}`,
      '',
      '**Verification Stats:**',
      `• Total Verified: ${status.verifierStats.totalVerified}`,
      `• Daily Airdrops: ${status.verifierStats.dailyAirdrops}/${status.verifierStats.maxDaily}`,
      '',
      `**Total Airdropped:**`,
      `• sBTC: ${status.totalSbtcAirdropped.toLocaleString()} sats`,
      `• STX: ${(status.totalStxAirdropped / 1_000_000).toFixed(2)} STX`,
    ].join('\n');
  } catch (error) {
    return `❌ Error: ${(error as Error).message}`;
  }
}
