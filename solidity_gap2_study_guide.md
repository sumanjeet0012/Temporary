# Gap 2 — Ethereum Testnets + Wallet Tooling
### From Zero to Your First Deployed Contract on Base Sepolia

---

## Table of Contents

1. [How Testnets Work](#1-how-testnets-work)
2. [The Network Landscape](#2-the-network-landscape)
3. [MetaMask Setup](#3-metamask-setup)
4. [Adding Base Sepolia to MetaMask](#4-adding-base-sepolia-to-metamask)
5. [Getting Testnet ETH — Faucets](#5-getting-testnet-eth--faucets)
6. [RPC Endpoints — What They Are and Why You Need One](#6-rpc-endpoints--what-they-are-and-why-you-need-one)
7. [Setting Up Alchemy](#7-setting-up-alchemy)
8. [Gas — The Transaction Fee System](#8-gas--the-transaction-fee-system)
9. [Nonces — Transaction Ordering](#9-nonces--transaction-ordering)
10. [Transaction Lifecycle — From Submission to Confirmation](#10-transaction-lifecycle--from-submission-to-confirmation)
11. [Block Explorers — Etherscan and Basescan](#11-block-explorers--etherscan-and-basescan)
12. [Hardhat Project Setup](#12-hardhat-project-setup)
13. [Deploying the MiniAgentRegistry to Base Sepolia](#13-deploying-the-miniagentregistry-to-base-sepolia)
14. [Verifying Your Contract on Basescan](#14-verifying-your-contract-on-basescan)
15. [Interacting With Your Deployed Contract](#15-interacting-with-your-deployed-contract)
16. [Putting It All Together — Deployment Checklist](#16-putting-it-all-together--deployment-checklist)

---

## 1. How Testnets Work

When you write a contract and want to test it, you absolutely **do not** use Ethereum mainnet — that costs real money. Instead, you use a **testnet**: a parallel blockchain that mirrors mainnet's behaviour exactly, but uses worthless test ETH that you get for free from faucets.

```
Ethereum Mainnet       ← real ETH, real money, production
       │
       │  mirrors behaviour
       ▼
Ethereum Sepolia       ← test ETH (worthless), for testing
Base Sepolia           ← test ETH on Base L2 (what we'll use for ERC-8004)
Filecoin Calibration   ← test FIL (what you'll use for Filecoin later)
```

> **Why Base Sepolia specifically?** ERC-8004's Identity Registry is deployed on Base (an Ethereum L2 by Coinbase). Base Sepolia is its testnet. Gas fees are near-zero compared to Ethereum mainnet, making it ideal for frequent deployments during development.

**The mental model:**

```
Testnet  ≈  localhost:8545 for blockchain
Mainnet  ≈  production server
```

Just like you'd test an API on localhost before deploying to production, you test contracts on testnets before deploying to mainnet.

---

## 2. The Network Landscape

Understanding the hierarchy before you start clicking things:

```
Layer 0: Ethereum Mainnet (Chain ID: 1)
         └── The root of trust, most decentralized

Layer 1 Testnets:
         └── Ethereum Sepolia (Chain ID: 11155111)
             └── Test version of mainnet

Layer 2 (L2) — Built on top of Ethereum:
         └── Base Mainnet (Chain ID: 8453)      ← production, real money
             └── Base Sepolia (Chain ID: 84532)  ← testnet, we use this

Layer 2 Testnet:
         └── Filecoin Calibration (Chain ID: 314159)  ← for Filecoin work later
```

**Chain IDs matter** — MetaMask and Hardhat use them to distinguish networks. You'll see `84532` a lot when configuring Base Sepolia.

---

## 3. MetaMask Setup

MetaMask is a browser wallet — it stores your private key locally and signs transactions. Think of it as your blockchain "SSH key manager" with a GUI.

### Install

1. Go to [metamask.io](https://metamask.io) — **only download from the official site**
2. Add the browser extension (Chrome/Firefox/Brave)
3. Click **Create a new wallet**
4. Set a strong password
5. **Write down your 12-word Secret Recovery Phrase on paper** — never store it digitally

> ⚠️ **Critical:** Your 12-word seed phrase = full access to all your funds. Anyone with it owns your wallet. Never share it, never type it anywhere except MetaMask's official recovery screen.

### What MetaMask Actually Does

```
Your Action               MetaMask Does
─────────────────────────────────────────────────────
Click "Deploy"         →  Signs transaction with your private key
Click "Send ETH"       →  Constructs + signs a transfer transaction
Click "Connect Wallet" →  Shares your public address (safe, like sharing email)
Enter seed phrase      →  Derives your private key (DANGER ZONE)
```

### Key Concepts in MetaMask

```
Public Address  → Like your bank account number. Safe to share.
                  Example: 0x71C7656EC7ab88b098defB751B7401B5f6d8976F

Private Key     → Like your PIN + the physical card combined.
                  Never share. Never export unless you know exactly why.

Seed Phrase     → Master key that generates all your accounts.
                  12 words. Write on paper. Store safely.
```

---

## 4. Adding Base Sepolia to MetaMask

MetaMask doesn't include Base Sepolia by default. Here's how to add it:

### Method 1 — One Click via Chainlist (Recommended)

1. Go to [chainlist.org](https://chainlist.org)
2. Toggle **"Include Testnets"**
3. Search for **"Base Sepolia"**
4. Click **"Add to MetaMask"** → Approve

### Method 2 — Manual Configuration

In MetaMask → Settings → Networks → Add Network → Add manually:

```
Network Name:    Base Sepolia Testnet
New RPC URL:     https://sepolia.base.org
Chain ID:        84532
Currency Symbol: ETH
Block Explorer:  https://sepolia.basescan.org
```

### Verify It Worked

After adding, MetaMask's network dropdown (top-left) should show **"Base Sepolia Testnet"**. Your balance will show `0 ETH` — time to get some test ETH.

---

## 5. Getting Testnet ETH — Faucets

Faucets are websites that give you free test ETH. They exist specifically for developers.

### Base Sepolia Faucets

| Faucet | URL | Amount | Requirement |
|--------|-----|--------|-------------|
| Coinbase Developer Platform | `faucet.coinbase.com` | 0.1 ETH/day | Coinbase account |
| Alchemy Base Sepolia Faucet | `basefaucet.alchemy.com` | 0.5 ETH/day | Alchemy account |
| QuickNode Faucet | `faucet.quicknode.com` | 0.1 ETH/day | QuickNode account |

### How to Use a Faucet

```
1. Copy your MetaMask address  (click the address shown under your account name)
2. Paste into the faucet's address field
3. Click "Send" / "Drip"
4. Wait 30–60 seconds
5. Check MetaMask — balance should update
```

> **Tip:** Use at least 2–3 faucets to stock up. Each deployment + transaction costs a tiny bit of test ETH. Having 1–2 ETH of test funds means you won't run dry mid-project.

### Checking Your Balance

```
In MetaMask:      Look at the balance on the home screen
On Basescan:      https://sepolia.basescan.org/address/YOUR_ADDRESS
Via command line: (covered in Hardhat section)
```

---

## 6. RPC Endpoints — What They Are and Why You Need One

When your code (Hardhat, web3.py, etc.) wants to talk to the blockchain, it needs a **gateway** — a server that accepts JSON-RPC requests and forwards them to actual blockchain nodes.

```
Your Code (Hardhat / web3.py)
         │
         │  HTTP POST JSON-RPC request
         ▼
   RPC Endpoint (Alchemy / Infura / public)
         │
         │  forwards to
         ▼
   Blockchain Node
         │
         │  response
         ▼
   Back to your code
```

**What a raw RPC call looks like** (this is what Hardhat/web3.py send automatically):

```json
POST https://base-sepolia.g.alchemy.com/v2/YOUR_KEY

{
  "jsonrpc": "2.0",
  "method": "eth_getBalance",
  "params": ["0xYourAddress", "latest"],
  "id": 1
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": "0x38D7EA4C68000"   ← balance in hex wei
}
```

You never write these raw calls manually — Hardhat and web3.py handle this for you. But understanding the underlying mechanism helps when debugging.

### Public RPC vs Dedicated RPC

```
Public RPC (https://sepolia.base.org):
  ✅ Free, no setup
  ❌ Rate limited, unreliable for production
  ❌ Sometimes slow
  ✅ Fine for quick Remix experiments

Dedicated RPC (Alchemy / Infura):
  ✅ Reliable, fast, high rate limits
  ✅ Dashboard with request analytics
  ✅ Free tier is generous enough for development
  ✅ Required for Hardhat deployments to avoid timeouts
```

---

## 7. Setting Up Alchemy

Alchemy is the most popular RPC provider. Their free tier is more than enough.

### Step-by-Step

```
1. Go to dashboard.alchemy.com
2. Sign up for a free account
3. Click "Create new app"
4. Name: "ERC8004-dev"  (or anything)
5. Chain: Base
6. Network: Base Sepolia
7. Click "Create app"
8. Click "API Key" → copy the HTTPS URL

Your URL will look like:
https://base-sepolia.g.alchemy.com/v2/abc123XYZyourKeyHere
```

> **Security:** This API key is semi-sensitive. Don't commit it to GitHub. Store it in a `.env` file (shown in the Hardhat section). Unlike your private key, a leaked API key can't drain your wallet — but it can rack up usage on your Alchemy account.

### Verify Your RPC Works

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  https://base-sepolia.g.alchemy.com/v2/YOUR_KEY
```

Expected response:
```json
{"jsonrpc":"2.0","id":1,"result":"0x123abc"}
```

If you see a hex block number, your RPC is working.

---

## 8. Gas — The Transaction Fee System

Gas is the fee mechanism that prevents spam and compensates validators. You need to understand this to debug failed transactions.

### The Analogy

```
Gas  ≈  fuel for a car journey
  gasLimit   = tank size  (max gas you allow)
  gasPrice   = price per litre (set by network demand)
  total fee  = gas used × gas price
```

### Key Concepts

```
Gas Unit     → unit of computational work
               reading a variable = 200 gas
               writing to storage = 20,000 gas
               deploying a contract = 1–3 million gas

Gas Limit    → max gas you're willing to spend
               set too low → transaction reverts ("out of gas")
               set too high → unused gas refunded, no penalty

Gas Price    → price per gas unit, denominated in Gwei
               1 ETH = 1,000,000,000 Gwei (10^9)
               Base fee = minimum set by network
               Priority fee (tip) = extra to speed up inclusion

EIP-1559     → the current fee model on Ethereum + Base
               maxFeePerGas       = absolute max you'll pay per gas
               maxPriorityFeeGas  = your tip to validators
```

### Real Transaction Breakdown

```
Contract deployment on Base Sepolia:

Gas Used:        1,234,567 gas
Base Fee:        0.000000100 Gwei (near-zero on Base Sepolia!)
Priority Fee:    0.000000001 Gwei
─────────────────────────────────
Total Fee:       ~0.0000001 ETH   (essentially free on testnet)

On Ethereum mainnet at 30 Gwei:
Gas Used:        1,234,567 gas
Gas Price:       30 Gwei
─────────────────────────────────
Total Fee:       ~0.037 ETH  ≈ $100+  ← why we use Base L2!
```

### Why Transactions Fail

```
"out of gas"          → gasLimit too low, increase it
"insufficient funds"  → not enough ETH for gas, get more from faucet
"revert"              → your require() condition failed
"nonce too low"       → nonce conflict (see next section)
```

> **On Base Sepolia:** Gas fees are near-zero. Don't stress about gas optimization during learning — that comes much later.

---

## 9. Nonces — Transaction Ordering

Every transaction from your address has a **nonce** — a sequential counter starting at 0. This prevents replay attacks and ensures ordering.

```
Your first ever transaction:   nonce = 0
Your second transaction:       nonce = 1
Your third transaction:        nonce = 2
...and so on forever
```

**Why this matters in practice:**

```
Scenario: You submit two transactions quickly

TX1 (nonce=5) → deploy contract       ← sent first
TX2 (nonce=6) → call registerAgent()  ← sent second

If TX1 fails → TX2 is stuck (pending forever, wrong nonce order)
```

**You'll rarely manage nonces manually** — Hardhat and web3.py handle this automatically. But when you see `"nonce too low"` or a stuck pending transaction, this is why.

**Fix a stuck transaction in MetaMask:**
```
Settings → Advanced → Reset Account
(clears pending transactions, resets local nonce counter)
```

---

## 10. Transaction Lifecycle — From Submission to Confirmation

This is the full journey of a transaction, from your click to permanent on-chain state:

```
Step 1: SIGNED
  Your wallet signs the transaction with your private key
  Creates a unique signature proving you authorized it
        │
        ▼
Step 2: BROADCASTED
  Transaction is sent to the RPC endpoint (Alchemy)
  Alchemy forwards it to blockchain nodes
        │
        ▼
Step 3: PENDING (in mempool)
  Transaction sits in the "mempool" — a waiting room
  Validators pick transactions to include (highest tip first)
  Duration: 1–30 seconds on Base Sepolia
        │
        ▼
Step 4: INCLUDED IN BLOCK
  Validator includes your TX in a new block
  Block is proposed and attested by other validators
        │
        ▼
Step 5: CONFIRMED
  Block is finalized
  State changes are permanent
  Event logs are emitted
  Your contract is live
```

**In Hardhat, this is how you wait for confirmation:**

```javascript
const tx = await contract.registerAgent("my-agent", "ipfs://...");
console.log("TX submitted:", tx.hash);

const receipt = await tx.wait();  // waits for Step 5
console.log("Confirmed in block:", receipt.blockNumber);
console.log("Gas used:", receipt.gasUsed.toString());
```

**Transaction receipt contains:**

```javascript
receipt = {
  transactionHash: "0xabc...",   // unique TX identifier
  blockNumber: 12345678,          // which block included it
  gasUsed: 234567n,               // actual gas consumed
  status: 1,                      // 1 = success, 0 = reverted
  logs: [...],                    // emitted events
  contractAddress: "0x..."        // set if you deployed a contract
}
```

---

## 11. Block Explorers — Etherscan and Basescan

Block explorers are web interfaces to read blockchain state. For Base Sepolia, use **Basescan**.

### Basescan for Base Sepolia

```
URL: https://sepolia.basescan.org
```

### What You Can Do on Basescan

```
Search by address  → See all transactions, token holdings, contracts
Search by TX hash  → See full transaction details, logs, revert reason
Search by block    → See all transactions in a block
Contract page      → Read/write contract functions directly (after verification)
```

### Reading a Transaction on Basescan

After deploying, paste your TX hash into Basescan:

```
Transaction Hash:  0xabc123...
Status:            ✅ Success
Block:             12,345,678
From:              0xYourAddress
To:                Contract Creation
Contract Created:  0xNewContractAddress   ← copy this!
Gas Used:          1,234,567 (41%)
Input Data:        Contract bytecode...
Logs:              [your emitted events]
```

> **Bookmark your contract address** from the deployment TX. You'll use it in every subsequent interaction.

### Reading Contract State on Basescan

Once your contract is **verified** (covered in Section 14):
- Click the **"Contract"** tab on Basescan
- Click **"Read Contract"** → call view functions without MetaMask
- Click **"Write Contract"** → send transactions directly from the browser

---

## 12. Hardhat Project Setup

Hardhat is the professional development environment for Ethereum. Think of it as pytest + virtualenv + deployment scripts, all in one.

### Project Initialization

```bash
mkdir erc8004-dev && cd erc8004-dev
npm init -y
npm install --save-dev hardhat @nomicfoundation/hardhat-toolbox
npm install @openzeppelin/contracts
npx hardhat init
# Choose: "Create a JavaScript project"
# Accept all defaults
```

Your project structure:
```
erc8004-dev/
├── contracts/
│   └── MiniAgentRegistry.sol    ← your contracts go here
├── scripts/
│   └── deploy.js                ← deployment scripts
├── test/
│   └── MiniAgentRegistry.js     ← test files
├── hardhat.config.js            ← network configuration
├── .env                         ← secrets (never commit!)
└── package.json
```

### Environment Variables (.env)

```bash
# Install dotenv
npm install dotenv

# Create .env file
touch .env
```

```bash
# .env — NEVER commit this to git
PRIVATE_KEY=your_metamask_private_key_here
ALCHEMY_API_KEY=your_alchemy_api_key_here
BASESCAN_API_KEY=your_basescan_api_key_here  # for contract verification
```

**Get your private key from MetaMask:**
```
MetaMask → Click 3 dots → Account Details → Show Private Key
Enter password → Copy the key (starts with 0x or without)
```

> ⚠️ **This is your real private key, even on testnet.** The same key controls your mainnet wallet. Treat it like a password. Add `.env` to `.gitignore` immediately.

```bash
echo ".env" >> .gitignore
```

### hardhat.config.js — Full Configuration

```javascript
require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config();

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
    },
  },

  networks: {
    // Local development network (instant, free, no setup)
    hardhat: {
      chainId: 31337,
    },

    // Base Sepolia testnet
    "base-sepolia": {
      url: `https://base-sepolia.g.alchemy.com/v2/${process.env.ALCHEMY_API_KEY}`,
      accounts: [process.env.PRIVATE_KEY],
      chainId: 84532,
      gasPrice: "auto",
    },

    // Base Mainnet (for when you're ready for production)
    "base-mainnet": {
      url: `https://base-mainnet.g.alchemy.com/v2/${process.env.ALCHEMY_API_KEY}`,
      accounts: [process.env.PRIVATE_KEY],
      chainId: 8453,
    },
  },

  etherscan: {
    apiKey: {
      "base-sepolia": process.env.BASESCAN_API_KEY,
    },
    customChains: [
      {
        network: "base-sepolia",
        chainId: 84532,
        urls: {
          apiURL: "https://api-sepolia.basescan.org/api",
          browserURL: "https://sepolia.basescan.org",
        },
      },
    ],
  },
};
```

### Add Contract File

```bash
# Copy the MiniAgentRegistry from Gap 1 guide
# Save as: contracts/MiniAgentRegistry.sol

# Compile to verify no errors
npx hardhat compile
```

Expected output:
```
Compiled 15 Solidity files successfully (evm target: paris).
```

---

## 13. Deploying the MiniAgentRegistry to Base Sepolia

### Step 1 — Write the Deployment Script

```javascript
// scripts/deploy.js
const { ethers } = require("hardhat");

async function main() {
  // Get the deployer account (from PRIVATE_KEY in .env)
  const [deployer] = await ethers.getSigners();

  console.log("Deploying with address:", deployer.address);

  // Check balance before deploying
  const balance = await ethers.provider.getBalance(deployer.address);
  console.log("Account balance:", ethers.formatEther(balance), "ETH");

  if (balance === 0n) {
    throw new Error("No ETH! Get some from a faucet first.");
  }

  // Deploy the contract
  console.log("\nDeploying MiniAgentRegistry...");
  const Registry = await ethers.getContractFactory("MiniAgentRegistry");
  const registry = await Registry.deploy();

  // Wait for deployment transaction to be confirmed
  await registry.waitForDeployment();

  const address = await registry.getAddress();
  console.log("✅ MiniAgentRegistry deployed to:", address);
  console.log("View on Basescan:", `https://sepolia.basescan.org/address/${address}`);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
```

### Step 2 — Test Locally First

```bash
# Always test on local Hardhat network before testnet
npx hardhat run scripts/deploy.js --network hardhat
```

Expected output:
```
Deploying with address: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
Account balance: 10000.0 ETH
Deploying MiniAgentRegistry...
✅ MiniAgentRegistry deployed to: 0x5FbDB2315678afecb367f032d93F642f64180aa3
```

### Step 3 — Deploy to Base Sepolia

```bash
npx hardhat run scripts/deploy.js --network base-sepolia
```

Expected output:
```
Deploying with address: 0xYourRealAddress
Account balance: 0.5 ETH
Deploying MiniAgentRegistry...
✅ MiniAgentRegistry deployed to: 0xAbCd1234...
View on Basescan: https://sepolia.basescan.org/address/0xAbCd1234...
```

> **Save your contract address.** You'll need it for every subsequent interaction, verification, and for the web3.py work in Gap 3.

### Common Deployment Errors and Fixes

```
Error: "insufficient funds for gas"
Fix:   Get more testnet ETH from faucets (Section 5)

Error: "could not detect network"
Fix:   Check your ALCHEMY_API_KEY in .env, verify the URL format

Error: "invalid private key"
Fix:   Make sure PRIVATE_KEY in .env starts without 0x, or includes it
       (Hardhat accepts both formats)

Error: "nonce too low"
Fix:   A previous transaction is still pending. Wait for it or reset MetaMask

Error: "HardhatError: Cannot find module..."
Fix:   Run: npm install
```

---

## 14. Verifying Your Contract on Basescan

Contract verification uploads your source code to Basescan so anyone can read it. It also enables the Read/Write Contract UI. This is expected practice in production.

### Get a Basescan API Key

```
1. Go to basescan.org
2. Sign up for a free account
3. Go to: My Profile → API Keys → Add
4. Name it "hardhat-verify"
5. Copy the API key to .env as BASESCAN_API_KEY
```

### Verify the Contract

```bash
npx hardhat verify --network base-sepolia YOUR_CONTRACT_ADDRESS
```

Example:
```bash
npx hardhat verify --network base-sepolia 0xAbCd1234...
```

Expected output:
```
Verifying implementation: 0xAbCd1234...
Successfully submitted source code for contract
contracts/MiniAgentRegistry.sol:MiniAgentRegistry at 0xAbCd1234...
for verification on the block explorer. Waiting for verification result...

Successfully verified contract MiniAgentRegistry on Etherscan.
https://sepolia.basescan.org/address/0xAbCd1234#code
```

### After Verification

Go to your contract on Basescan → click the **"Contract"** tab. You'll see:
- **Code** → full Solidity source, ABI, bytecode
- **Read Contract** → call view functions in the browser
- **Write Contract** → connect MetaMask and call state-changing functions

Try calling `totalAgents()` — it should return `0` since no agents are registered yet.

---

## 15. Interacting With Your Deployed Contract

### Method 1 — Hardhat Console (Interactive REPL)

```bash
npx hardhat console --network base-sepolia
```

```javascript
// Inside the Hardhat console:

// Attach to your deployed contract
const Registry = await ethers.getContractFactory("MiniAgentRegistry");
const registry = await Registry.attach("0xYourContractAddress");

// Read total agents (free, no gas)
const count = await registry.totalAgents();
console.log("Total agents:", count.toString());
// Output: Total agents: 0

// Register an agent (costs gas, sends transaction)
const tx = await registry.registerAgent(
  "TestAgent",
  "ipfs://bafybeig6emgxjb6test",
  { value: ethers.parseEther("0.001") }   // the registration fee
);
console.log("TX hash:", tx.hash);

// Wait for confirmation
const receipt = await tx.wait();
console.log("Confirmed! Block:", receipt.blockNumber);

// Read back the agent
const [owner, name, uri, active] = await registry.getAgent(1);
console.log("Owner:", owner);
console.log("Name:", name);
console.log("URI:", uri);
console.log("Active:", active);
```

### Method 2 — Hardhat Script

```javascript
// scripts/interact.js
const { ethers } = require("hardhat");

const CONTRACT_ADDRESS = "0xYourContractAddress";

async function main() {
  const [signer] = await ethers.getSigners();
  const Registry = await ethers.getContractFactory("MiniAgentRegistry");
  const registry = Registry.attach(CONTRACT_ADDRESS);

  // ── Register an Agent ──────────────────────────────────────────
  console.log("Registering agent...");
  const tx = await registry.registerAgent(
    "MyFirstAgent",
    "ipfs://bafybeig6emgxjb6calpnftest123",
    { value: ethers.parseEther("0.001") }
  );
  await tx.wait();
  console.log("✅ Agent registered! TX:", tx.hash);

  // ── Read Agent Data ────────────────────────────────────────────
  const tokenId = 1;
  const [owner, name, uri, active] = await registry.getAgent(tokenId);
  console.log("\n── Agent #1 ──────────────────────");
  console.log("Owner:  ", owner);
  console.log("Name:   ", name);
  console.log("URI:    ", uri);
  console.log("Active: ", active);

  // ── Verify ownerOf and tokenURI ────────────────────────────────
  const nftOwner = await registry.ownerOf(tokenId);
  const nftURI   = await registry.tokenURI(tokenId);
  console.log("\n── ERC-721 Checks ────────────────");
  console.log("ownerOf(1):  ", nftOwner);
  console.log("tokenURI(1): ", nftURI);

  // ── Total agents ───────────────────────────────────────────────
  const total = await registry.totalAgents();
  console.log("\nTotal agents registered:", total.toString());
}

main().catch(console.error);
```

```bash
npx hardhat run scripts/interact.js --network base-sepolia
```

### Method 3 — Read Contract Via Basescan

```
1. Go to: https://sepolia.basescan.org/address/YOUR_ADDRESS#readContract
2. Click "totalAgents" → returns: 1
3. Click "getAgent" → enter tokenId: 1 → returns all agent data
4. Click "ownerOf" → enter 1 → returns your address
5. Click "tokenURI" → enter 1 → returns the IPFS CID
```

---

## 16. Putting It All Together — Deployment Checklist

Work through this sequentially. Don't skip ahead.

### Environment Setup
- [ ] MetaMask installed and wallet created
- [ ] Seed phrase written on paper and stored safely
- [ ] Base Sepolia network added to MetaMask (Chain ID: 84532)
- [ ] Alchemy account created, Base Sepolia app set up
- [ ] Alchemy HTTPS RPC URL copied
- [ ] Hardhat project initialized (`npx hardhat init`)
- [ ] `.env` file created with `PRIVATE_KEY` and `ALCHEMY_API_KEY`
- [ ] `.env` added to `.gitignore`
- [ ] `hardhat.config.js` updated with Base Sepolia network config

### Funding
- [ ] Test ETH received from at least one faucet
- [ ] Balance visible in MetaMask and on Basescan

### Deployment
- [ ] `MiniAgentRegistry.sol` copied to `contracts/` folder
- [ ] `npx hardhat compile` succeeds with no errors
- [ ] Local deployment tested: `npx hardhat run scripts/deploy.js --network hardhat`
- [ ] Base Sepolia deployment done: `npx hardhat run scripts/deploy.js --network base-sepolia`
- [ ] Contract address saved somewhere safe

### Verification
- [ ] Basescan API key obtained and added to `.env`
- [ ] Contract verified on Basescan
- [ ] Source code visible on Basescan's "Contract" tab

### Interaction
- [ ] `registerAgent()` called successfully (TX confirmed on Basescan)
- [ ] `ownerOf(1)` returns your wallet address
- [ ] `tokenURI(1)` returns your IPFS URI string
- [ ] `getAgent(1)` returns all four fields correctly
- [ ] `AgentRegistered` event visible in Basescan's "Logs" tab

---

## Quick Reference Cheatsheet

```bash
# Compile contracts
npx hardhat compile

# Run tests
npx hardhat test

# Deploy locally
npx hardhat run scripts/deploy.js --network hardhat

# Deploy to Base Sepolia
npx hardhat run scripts/deploy.js --network base-sepolia

# Open interactive console on Base Sepolia
npx hardhat console --network base-sepolia

# Verify contract on Basescan
npx hardhat verify --network base-sepolia CONTRACT_ADDRESS

# Check your ETH balance
npx hardhat console --network base-sepolia
> const [s] = await ethers.getSigners()
> ethers.formatEther(await ethers.provider.getBalance(s.address))
```

```
Networks:
  Hardhat local:    chainId 31337  (instant, fake ETH)
  Base Sepolia:     chainId 84532  (test ETH, real network)
  Base Mainnet:     chainId 8453   (real ETH, production)

Faucets:
  faucet.coinbase.com
  basefaucet.alchemy.com

Explorer:
  https://sepolia.basescan.org

Units:
  1 ETH = 10^18 wei
  1 ETH = 10^9 Gwei
  ethers.parseEther("0.001")  → 1000000000000000n (wei)
  ethers.formatEther(bigint)  → "0.001" (ETH string)
```

---

## What's Next (Gap 3)

You've now deployed a real contract to Base Sepolia and interacted with it through Hardhat's console and scripts. In **Gap 3 — web3.py**, you'll do the exact same interactions from Python:

- Connect to Base Sepolia using your Alchemy RPC URL
- Load your deployed contract using its ABI and address
- Call `registerAgent()`, `ownerOf()`, `tokenURI()` from Python
- Listen for `AgentRegistered` events in Python

Since you already know REST APIs and HTTP clients in Python, web3.py will feel very familiar — it's essentially a typed HTTP client for the Ethereum JSON-RPC API.
