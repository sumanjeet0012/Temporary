# Complete User Guide - Canteen: Decentralized Container Orchestration

## Table of Contents
1. [Introduction](#introduction)
2. [What is This Project?](#what-is-this-project)
3. [Prerequisites & Installation](#prerequisites--installation)
4. [Understanding the Architecture](#understanding-the-architecture)
5. [Getting Started](#getting-started)
6. [Using the Application](#using-the-application)
7. [Web3 Concepts Explained](#web3-concepts-explained)
8. [Advanced Usage](#advanced-usage)
9. [Troubleshooting](#troubleshooting)
10. [API Reference](#api-reference)

---

## Introduction

Welcome! This guide will teach you how to use **Canteen**, a decentralized container orchestration system. Think of it as a blockchain-based alternative to Kubernetes that uses Ethereum smart contracts to coordinate Docker containers across multiple servers.

**Perfect for beginners**: This guide explains every Web3 concept you'll encounter!

---

## What is This Project?

### The Big Picture

Canteen is a system that:
1. **Manages Docker containers** (like Kubernetes or Docker Swarm)
2. **Uses blockchain** (Ethereum) to coordinate decisions
3. **Runs across multiple servers** (cluster of nodes)
4. **Automatically distributes workloads** fairly across all nodes

### Why Use Blockchain for This?

Traditional orchestration systems (like Kubernetes) have a "master node" that makes all decisions. If it fails, the whole system stops. Canteen uses a **smart contract** on Ethereum as the decision-maker:
- ✅ **No single point of failure** - The blockchain is always available
- ✅ **Transparent** - All scheduling decisions are recorded on-chain
- ✅ **Trustless** - No single entity controls the cluster

### Real-World Use Case

Imagine you have 3 servers and want to run 2 replicas each of App A and App B:
- Server 1 runs: App A
- Server 2 runs: App B  
- Server 3 runs: App A
- When you add Server 4, Canteen automatically schedules App B on it

All coordination happens through the Ethereum smart contract!

---

## Node.js Version Compatibility

### Summary

✅ **Yes, it works on the latest Node.js versions!**

After modernizing the project (replacing SWIM with Hyperswarm and updating Solidity to 0.8.x), Canteen now works seamlessly across all modern Node.js LTS versions.

### Tested Versions

| Node Version | Status | Notes |
|-------------|--------|-------|
| v16.20.2 | ✅ Fully Working | Most stable, original development version |
| v18.x | ✅ Fully Working | Compatible, no issues |
| v20.19.5 | ✅ Fully Working | Tested and confirmed working |
| v22.20.0 | ✅ Fully Working | Latest LTS, fully compatible |

### Why It Works

1. **Babel Transpilation**: The project uses Babel to convert modern JavaScript (ES6+) to compatible code, ensuring broad Node.js support.

2. **Modern Dependencies**: 
   - Replaced `swim@0.5.0` (had native msgpack issues) with `hyperswarm@4.8.0` (pure JavaScript)
   - Updated `web3@1.0.0-beta.30` to `web3@1.10.0` (stable, maintained)
   - Updated Solidity from 0.4.x to 0.8.19 (current standard)

3. **No Native Addons**: After removing SWIM (which had C++ dependencies), all remaining packages work across Node versions.

### Recommendations

**For Learning/Development:**
- Use **Node.js v20** or **v22** (latest LTS)
- Best performance and newest features

**For Production Stability:**
- Use **Node.js v16** or **v18**
- Longer track record, maximum stability

### Switching Node Versions

```bash
# Check available versions:
nvm ls

# Install a specific version:
nvm install 20

# Switch to a version:
nvm use 20

# Set default version:
nvm alias default 20

# Verify:
node --version
```

After switching Node versions, you may need to reinstall dependencies:

```bash
rm -rf node_modules package-lock.json
npm install
```

---

## Prerequisites & Installation

### What You Need

1. **Node.js v16+ (LTS)** - Compatible with v16, v18, v20, and v22
2. **Docker Desktop** (for running containers)
3. **Ganache** (local Ethereum blockchain)
4. **A code editor** (VS Code recommended)
5. **Basic terminal knowledge**

#### Node.js Version Compatibility

✅ **Tested and Working:**
- Node.js v16.20.2 (LTS Gallium) - Recommended for stability
- Node.js v18.x (LTS Hydrogen)
- Node.js v20.19.5 (LTS Iron)
- Node.js v22.20.0 (LTS Jod) - Latest LTS

⚠️ **Note:** The project uses Babel to transpile ES6+ code, which provides excellent compatibility across Node versions. After our modernization (replacing SWIM with Hyperswarm and updating Solidity), it works seamlessly on all modern Node.js LTS versions!

### Step-by-Step Installation

#### 0. Install Node.js (If Not Already Installed)

**Using NVM (Recommended):**
```bash
# Install NVM:
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# Restart terminal or run:
source ~/.bashrc  # or ~/.zshrc

# Install Node.js LTS (any of these work):
nvm install 16    # Stable, well-tested
nvm install 20    # Recent LTS
nvm install 22    # Latest LTS

# Use your preferred version:
nvm use 16        # or 20, or 22

# Verify installation:
node --version    # Should show v16.x.x, v20.x.x, or v22.x.x
npm --version     # Should show 8.x.x or higher
```

**Or download directly:** https://nodejs.org/ (choose LTS version)

#### 1. Install Docker Desktop

```bash
# Download from: https://www.docker.com/products/docker-desktop/
# Or install via Homebrew:
brew install --cask docker

# Verify installation:
docker --version
# Should show: Docker version 20.x.x or higher
```

**What is Docker?** It's like a virtual machine but lighter. It packages applications with all their dependencies into "containers" that run consistently anywhere.

#### 2. Install Ganache (Local Blockchain)

```bash
# Install globally:
npm install -g ganache

# Start Ganache:
ganache --port 7545

# Keep this terminal open! Ganache must run while using Canteen.
```

**What is Ganache?** It's a personal Ethereum blockchain for testing. Think of it as a "practice blockchain" that runs on your computer. You get:
- 10 accounts pre-funded with 100 ETH each (fake money for testing)
- Instant transaction confirmation (no waiting)
- Complete control over the blockchain state

**Expected Output:**
```
ganache v7.x.x (@ganache/cli: 0.x.x, @ganache/core: 0.x.x)
Starting RPC server

Available Accounts
==================
(0) 0x5c7C0B956C58FCcB14E3436A508688052Da4B210 (100 ETH)
(1) 0x742d35Cc6634C0532925a3b844Bc454e4438f44e (100 ETH)
...

Private Keys
==================
(0) 0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d
(1) 0x6cbed15c793ce57650b9877cf6fa156fbef513c4e6134f022a85b1ffdd59b2a1
...

Listening on 127.0.0.1:7545
```

#### 3. Verify Project Installation

```bash
cd /Users/sumanjeet/code/py-libp2p-experiment

# Check dependencies are installed:
npm list --depth=0

# Should show:
# ├── bignumber.js@9.1.2
# ├── dockerode@2.5.3
# ├── express@4.18.2
# ├── hyperswarm@4.8.0
# ├── lodash@4.17.21
# └── web3@1.10.0
```

---

## Understanding the Architecture

### Components Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Canteen Architecture                      │
└─────────────────────────────────────────────────────────────┘

┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Ganache        │     │  Smart Contract  │     │   Dashboard      │
│  (Blockchain)    │────▶│   (Coordinator)  │◀────│   (React UI)     │
│  Port: 7545      │     │   On-chain       │     │   Port: 3001     │
└──────────────────┘     └──────────────────┘     └──────────────────┘
         ▲                        ▲                        ▲
         │                        │                        │
         └────────────────────────┴────────────────────────┘
                                  │
         ┌────────────────────────┴────────────────────────┐
         │                                                  │
         ▼                                                  ▼
┌──────────────────┐                              ┌──────────────────┐
│  Canteen Node 1  │◀───── Hyperswarm P2P ──────▶│  Canteen Node 2  │
│  Port: 5000      │                              │  Port: 5001      │
│  Web: 3000       │                              │  Web: 3001       │
│                  │                              │                  │
│  ┌────────────┐  │                              │  ┌────────────┐  │
│  │Docker      │  │                              │  │Docker      │  │
│  │Containers  │  │                              │  │Containers  │  │
│  └────────────┘  │                              │  └────────────┘  │
└──────────────────┘                              └──────────────────┘
```

### Components Explained

#### 1. **Ganache (Local Blockchain)**
- **What**: Your personal Ethereum blockchain
- **Port**: 7545
- **Purpose**: Stores the smart contract and all scheduling decisions
- **Analogy**: Like a shared database that no one person controls

#### 2. **Smart Contract (Canteen.sol)**
- **What**: A program that runs on the blockchain
- **Language**: Solidity (like JavaScript for Ethereum)
- **Purpose**: Decides which server runs which container
- **Key Functions**:
  - `addMember()` - Register a server in the cluster
  - `addImage()` - Add a Docker image to deploy
  - `getMemberDetails()` - Check what a server is running

#### 3. **Canteen Node (index.js, scheduler.js)**
- **What**: The main application running on each server
- **Ports**: 
  - 5000 (Hyperswarm P2P networking)
  - 3000 (Web API)
- **Purpose**: 
  - Watches the smart contract for instructions
  - Pulls and runs Docker containers
  - Reports status to the cluster

#### 4. **Hyperswarm (Cluster Protocol)**
- **What**: P2P networking library for node discovery
- **Purpose**: Helps nodes find each other automatically
- **Replaces**: SWIM protocol (old gossip-based system)

#### 5. **Docker Engine**
- **What**: Runs the actual containers
- **Purpose**: Executes the applications Canteen schedules
- **Socket**: `/var/run/docker.sock`

#### 6. **Dashboard (React App)**
- **What**: Web-based UI
- **Port**: 3001 (when running)
- **Purpose**: Visualize cluster status and container distribution

---

## Getting Started

### Step 1: Deploy the Smart Contract

The smart contract is the "brain" of the system. Deploy it to Ganache:

```bash
# Make sure Ganache is running on port 7545!

# Deploy the contract:
npx truffle migrate --network development --reset
```

**Expected Output:**
```
Compiling your contracts...
===========================
✓ Compiling ./contracts/Canteen.sol
✓ Compiled successfully

Starting migrations...
======================
> Network name:    'development'
> Network id:      5777

2_deploy_contracts.js
=====================
   Deploying 'Canteen'
   -------------------
   > transaction hash:    0xd6348b32...
   > contract address:    0x81b85E74bDC1CD6Ef96479A1970fcB59Bb87A963
   > block number:        4
   > account:             0x5c7C0B956C58FCcB14E3436A508688052Da4B210
   > balance:             99.99 ETH
   > gas used:            2230742
   > gas price:           3.1 gwei
   > total cost:          0.0069 ETH

Summary
=======
> Total deployments:   2
> Final cost:          0.0079 ETH
```

**Important**: Copy the **contract address** (e.g., `0x81b85E74bDC1CD6Ef96479A1970fcB59Bb87A963`)

**What just happened?**
1. Truffle compiled your Solidity code into bytecode
2. It sent a transaction to Ganache to deploy the contract
3. The contract now lives on the blockchain at that address
4. It cost 0.0069 ETH in "gas" (transaction fees - fake money in Ganache)

### Step 2: Update the Contract Address (Already Done!)

The contract address is already configured in `index.js`:

```javascript
scheduler.start(new Web3.providers.HttpProvider('http://localhost:7545'),
  '0x81b85E74bDC1CD6Ef96479A1970fcB59Bb87A963', // Your deployed contract
  null)
```

**If you redeploy**, update this address with the new one from the migration output.

### Step 3: Start Your First Canteen Node

```bash
npm run start
```

**Expected Output:**
```
> canteen@0.0.0 start
> babel-node --presets=env,stage-2 --plugins=transform-runtime index.js

Starting Hyperswarm on port 5000...
Joining 0 specified bootstrap node(s).
Cluster health check web service is listening on port 3000
Using Ganache account: 0x5c7C0B956C58FCcB14E3436A508688052Da4B210
Node has been registered on Canteen.
Cluster topic announced
```

**What's happening?**
1. **Hyperswarm starts** on port 5000 to find other nodes
2. **Web API starts** on port 3000 for monitoring
3. **Connects to Ganache** and uses the first account (with 100 ETH)
4. **Registers with smart contract** by calling `addMember()`
5. **Starts polling** the contract every second for new instructions

### Step 4: Verify the Node is Running

Open your browser or use curl:

```bash
# Check cluster members:
curl http://localhost:3000/cluster

# Response:
{
  "members": ["127.0.0.1:5000"]
}
```

**Congratulations!** 🎉 You now have a single-node Canteen cluster running!

---

## Using the Application

### Understanding Web3 Concepts

Before we dive into usage, let's understand key Web3 terms:

#### **1. Account (Wallet)**
- **What**: A unique identity on Ethereum
- **Address**: Like an email address (e.g., `0x5c7C0B956C58FCcB14E3436A508688052Da4B210`)
- **Private Key**: Like a password (e.g., `0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d`)
- **Balance**: How much ETH you have (100 ETH in Ganache)

**Security Note**: Never share private keys! In production, use hardware wallets.

#### **2. Transaction**
- **What**: Any action that changes blockchain state
- **Gas**: Fee paid to miners (in Ganache, it's fake)
- **Gas Price**: How much you pay per unit of gas
- **Examples**: 
  - Deploying a contract
  - Calling `addMember()`
  - Updating container assignments

#### **3. Smart Contract Call Types**

**A. Write Operations (Transactions)**
- Change the blockchain state
- Cost gas (ETH)
- Take time to confirm
- Examples: `addMember()`, `addImage()`, `removeImage()`

```javascript
// This costs gas:
await contract.methods.addImage('nginx:latest', 2).send({
  from: account.address,
  gas: 500000
})
```

**B. Read Operations (Calls)**
- Just read data
- Free (no gas cost)
- Instant
- Examples: `getMemberDetails()`, `getImageDetails()`

```javascript
// This is free:
const details = await contract.methods.getMemberDetails('127.0.0.1:5000').call()
```

#### **4. ABI (Application Binary Interface)**
- **What**: A JSON file that describes your contract's functions
- **Location**: `build/contracts/Canteen.json`
- **Purpose**: Web3.js needs this to interact with your contract
- **Analogy**: Like an API documentation for your smart contract

### Basic Operations

#### Operation 1: Check Cluster Status

```bash
# View all registered nodes:
curl http://localhost:3000/cluster

# Response shows active members:
{
  "members": ["127.0.0.1:5000"]
}
```

#### Operation 2: Add a Docker Image to Schedule

You need to interact with the smart contract. Let's use Truffle console:

```bash
# Open Truffle console:
npx truffle console --network development
```

Inside the console:

```javascript
// Get the deployed contract:
const Canteen = await artifacts.require('Canteen')
const instance = await Canteen.deployed()

// Get the contract owner (your account):
const accounts = await web3.eth.getAccounts()
const owner = accounts[0]

// Add an image to deploy (2 replicas of nginx):
await instance.addImage('nginx:latest', 2, { from: owner })

// Check the image was added:
const imageDetails = await instance.getImageDetails('nginx:latest')
console.log('Replicas required:', imageDetails[0].toString())
console.log('Replicas deployed:', imageDetails[1].toString())
console.log('Is active:', imageDetails[2])
```

**Expected Output:**
```
Replicas required: 2
Replicas deployed: 1
Is active: true
```

**What happened?**
1. You called `addImage()` on the smart contract
2. The contract stored: "Deploy 2 replicas of nginx:latest"
3. Your Canteen node (running `npm run start`) detected this change
4. It automatically pulled the nginx Docker image
5. It started a container on your server
6. It updated the contract: "1 replica deployed"

**View in Ganache**: You'll see a new transaction recorded!

#### Operation 3: Check What's Running on Your Node

```bash
# In Truffle console:
const details = await instance.getMemberDetails('127.0.0.1:5000')
console.log('Assigned image:', details[0])
console.log('Is active:', details[1])
```

**Expected Output:**
```
Assigned image: nginx:latest
Is active: true
```

#### Operation 4: View Running Docker Containers

```bash
# Check Docker:
docker ps

# You should see nginx running:
CONTAINER ID   IMAGE           COMMAND                  PORTS
abc123def456   nginx:latest    "/docker-entrypoint.…"   0.0.0.0:32768->80/tcp
```

**Congratulations!** You just scheduled a container using blockchain! 🎉

### Multi-Node Setup

Want to run multiple nodes? Here's how to create a cluster:

#### Start Node 1 (Already Running)

```bash
# Terminal 1:
npm run start
# Running on ports 5000 (P2P) and 3000 (Web)
```

#### Start Node 2

```bash
# Terminal 2:
npm run start -- port=5001
```

**Wait, this will fail!** You need to:
1. Pass a different port
2. Make sure the web server also uses a different port

Let me show you how to properly configure multi-node setup:

#### Multi-Node Configuration

Create a second script in `package.json`:

```json
"scripts": {
  "start": "babel-node --presets=env,stage-2 --plugins=transform-runtime index.js",
  "start:node2": "babel-node --presets=env,stage-2 --plugins=transform-runtime index.js port=5001"
}
```

But the web server port is hardcoded! Let's fix that first. For now, you can:

**Option A: Run nodes on different machines**
- Each physical server runs one Canteen node
- All connect to the same Ganache blockchain (use a public RPC URL)

**Option B: Use Docker to run multiple nodes locally**
- Each in its own container with port mapping

**Option C: Modify the code** (requires changes to web-server.js)

For simplicity, let's focus on single-node usage first. Most concepts apply to multi-node setups too!

### Adding More Container Images

```bash
# In Truffle console:
await instance.addImage('redis:latest', 1, { from: owner })
await instance.addImage('postgres:14', 2, { from: owner })

// List all images:
const imageCount = await instance.getImagesCount()
console.log('Total images:', imageCount.toString())

for(let i = 0; i < imageCount; i++) {
  const imageName = await instance.images(i)
  const details = await instance.getImageDetails(imageName)
  console.log(`Image: ${imageName}`)
  console.log(`  Replicas: ${details[0].toString()}`)
  console.log(`  Deployed: ${details[1].toString()}`)
}
```

**The Canteen node will automatically**:
1. Detect the new images
2. Pull them from Docker Hub
3. Start containers
4. Update the contract

### Removing Images

```bash
// Remove an image:
await instance.removeImage('redis:latest', { from: owner })

// The node will automatically:
// 1. Stop the redis container
// 2. Remove the container
// 3. Update the contract
```

### Viewing Events

Smart contracts emit "events" - like notifications. View them:

```bash
// Get all MemberJoin events:
const events = await instance.getPastEvents('MemberJoin', {
  fromBlock: 0,
  toBlock: 'latest'
})

events.forEach(event => {
  console.log('Node joined:', event.returnValues.host)
})

// Get all MemberImageUpdate events:
const updates = await instance.getPastEvents('MemberImageUpdate', {
  fromBlock: 0,
  toBlock: 'latest'
})

updates.forEach(event => {
  console.log(`${event.returnValues.host} now running: ${event.returnValues.image}`)
})
```

**Why are events useful?**
- They're logged on the blockchain permanently
- You can audit the entire history
- The dashboard uses them to show real-time updates

---

## Web3 Concepts Explained

### Deep Dive: How Canteen Uses Web3

#### 1. **Connecting to the Blockchain**

```javascript
// In scheduler.js:
const web3 = new Web3(provider)
// provider = http://localhost:7545 (Ganache)
```

**What is Web3.js?**
- A JavaScript library to interact with Ethereum
- Provides functions to send transactions, read data, etc.
- Like an SDK for blockchain

#### 2. **Managing Accounts**

```javascript
// Get accounts from Ganache:
const accounts = await web3.eth.getAccounts()
// Returns: ['0x5c7C0B956C58FCcB14E3436A508688052Da4B210', ...]

// Check balance:
const balance = await web3.eth.getBalance(accounts[0])
console.log('Balance:', web3.utils.fromWei(balance, 'ether'), 'ETH')
```

**Wei vs Ether:**
- 1 ETH = 1,000,000,000,000,000,000 wei (10^18)
- Wei is the smallest unit (like cents for dollars)
- Use `web3.utils.fromWei()` to convert

#### 3. **Interacting with Contracts**

```javascript
// Create contract instance:
const contract = new web3.eth.Contract(Canteen.abi, contractAddress)

// Read data (free):
const memberCount = await contract.methods.getMembersCount().call()

// Write data (costs gas):
const tx = await contract.methods.addMember('127.0.0.1:5000').send({
  from: accounts[0],
  gas: 500000,
  gasPrice: web3.utils.toWei('3', 'gwei')
})

console.log('Transaction hash:', tx.transactionHash)
console.log('Block number:', tx.blockNumber)
console.log('Gas used:', tx.gasUsed)
```

#### 4. **Understanding Gas**

**What is Gas?**
- Payment for computation on Ethereum
- Prevents infinite loops and spam
- Measured in "gas units"

**Gas Price:**
- How much you pay per gas unit
- Measured in "gwei" (1 gwei = 10^9 wei = 0.000000001 ETH)
- Higher price = faster confirmation (in real Ethereum)

**Example Calculation:**
```
Gas Used: 250,000 units
Gas Price: 3 gwei
Total Cost: 250,000 × 3 gwei = 750,000 gwei = 0.00075 ETH
```

**In Ganache:**
- Gas is fake (not real money)
- Transactions are instant
- Perfect for testing!

#### 5. **Listening for Events**

```javascript
// Watch for new images added:
contract.events.MemberImageUpdate({
  fromBlock: 'latest'
}, (error, event) => {
  if (error) {
    console.error(error)
    return
  }
  
  console.log('Node updated:')
  console.log('  Host:', event.returnValues.host)
  console.log('  Image:', event.returnValues.image)
  console.log('  Block:', event.blockNumber)
  console.log('  Transaction:', event.transactionHash)
})
```

**Why Events?**
- Cheaper than storing data in contract state
- Can subscribe to real-time updates
- Indexed for fast searching

---

## Advanced Usage

### Using the Dashboard (React UI)

The dashboard provides a visual interface:

```bash
# In a new terminal:
cd dashboard
npm install
npm start

# Opens browser at http://localhost:3001
```

**Dashboard Features:**
- **Cluster Visualization**: See all nodes and their connections
- **Container Status**: View what's running on each node
- **Real-Time Updates**: Uses Web3.js to watch contract events
- **Add Images**: GUI for calling `addImage()`

### Interacting via Web API

The REST API provides programmatic access:

#### Get Cluster Members
```bash
curl http://localhost:3000/cluster
```

**Response:**
```json
{
  "members": ["127.0.0.1:5000"]
}
```

### Using Truffle for Contract Management

#### Compile Contracts
```bash
npx truffle compile
# Compiles .sol files to bytecode and generates ABI
```

#### Run Tests
```bash
npx truffle test
# Runs test/canteen_test.js
```

#### Migrate to Different Networks

**Local Development (Ganache):**
```bash
npx truffle migrate --network development
```

**Public Testnet (e.g., Sepolia):**
```javascript
// In truffle.js:
networks: {
  sepolia: {
    provider: () => new HDWalletProvider(
      'your mnemonic here',
      'https://sepolia.infura.io/v3/YOUR_INFURA_KEY'
    ),
    network_id: 11155111,
    gas: 5500000
  }
}
```

```bash
npx truffle migrate --network sepolia
```

**Cost:** Real ETH required for gas on public networks!

### Deploying to Production

#### Requirements for Production:

1. **Public Ethereum Network**
   - Mainnet (expensive)
   - Or Layer 2 (Polygon, Arbitrum - cheaper)

2. **Infura/Alchemy Account**
   - RPC provider to connect to Ethereum
   - Sign up at infura.io or alchemy.com

3. **Real ETH**
   - Buy from exchanges (Coinbase, Binance)
   - Transfer to your deployment account

4. **Secure Key Management**
   - Use environment variables for private keys
   - Never commit keys to Git!

```bash
# .env file (NEVER COMMIT THIS):
PRIVATE_KEY=0x1234...
INFURA_KEY=abc123...
CONTRACT_ADDRESS=0x456...

# Load in index.js:
require('dotenv').config()
const privateKey = process.env.PRIVATE_KEY
```

#### Production Checklist:

- [ ] Audit smart contract (security review)
- [ ] Test on testnet thoroughly
- [ ] Set up monitoring (Sentry, DataDog)
- [ ] Configure SSL/TLS for web API
- [ ] Set up proper Docker security
- [ ] Implement authentication for API
- [ ] Use a process manager (PM2, systemd)
- [ ] Set up logging (Winston, Bunyan)
- [ ] Configure firewall rules
- [ ] Plan for contract upgrades (proxy pattern)

---

## Troubleshooting

### Common Issues

#### Issue 1: "Error: CONNECTION ERROR: Couldn't connect to node"

**Cause:** Ganache is not running or wrong port

**Solution:**
```bash
# Make sure Ganache is running:
lsof -i :7545

# If nothing, start Ganache:
ganache --port 7545

# If running on different port, update truffle.js and index.js
```

#### Issue 2: "Error: Returned error: insufficient funds"

**Cause:** Account has no ETH for gas

**Solution:**
- In Ganache, all accounts start with 100 ETH
- If you're using a custom account, fund it:

```javascript
// In Truffle console:
const accounts = await web3.eth.getAccounts()
await web3.eth.sendTransaction({
  from: accounts[0], // funded account
  to: '0xYourAccount',
  value: web3.utils.toWei('10', 'ether')
})
```

#### Issue 3: "Error: Returned values aren't valid"

**Cause:** Wrong contract address or contract not deployed

**Solution:**
```bash
# Redeploy contract:
npx truffle migrate --network development --reset

# Copy new address to index.js
```

#### Issue 4: "TypeError: swim.whoami is not a function"

**Cause:** Code still using old SWIM protocol

**Solution:** Already fixed! If you see this, pull latest changes.

#### Issue 5: Docker containers won't start

**Cause:** Docker daemon not running or permission issues

**Solution:**
```bash
# Check Docker is running:
docker ps

# If error, start Docker Desktop

# Check socket permissions:
ls -la /var/run/docker.sock

# If permission denied, add user to docker group:
sudo usermod -aG docker $USER
# Then logout and login again
```

#### Issue 6: Port already in use

**Cause:** Previous instance still running

**Solution:**
```bash
# Kill process on port 3000:
lsof -ti:3000 | xargs kill -9

# Kill process on port 5000:
lsof -ti:5000 | xargs kill -9

# Then restart:
npm run start
```

#### Issue 7: "Error: Invalid JSON RPC response"

**Cause:** Ganache crashed or network issue

**Solution:**
1. Restart Ganache
2. Redeploy contract
3. Update contract address in index.js
4. Restart Canteen node

#### Issue 8: Node version compatibility concerns

**Cause:** Worried if project works on your Node version

**Solution:**
```bash
# Check your version:
node --version

# The project works on:
# ✅ Node v16.x (LTS Gallium)
# ✅ Node v18.x (LTS Hydrogen)  
# ✅ Node v20.x (LTS Iron)
# ✅ Node v22.x (LTS Jod) - Latest

# If you have issues, try Node v16:
nvm install 16
nvm use 16
npm install
```

**Still having issues?** Make sure you've run:
```bash
rm -rf node_modules package-lock.json
npm install
```

This clears any cached native modules that might be version-specific.

### Debugging Tips

#### Enable Verbose Logging

Add to scheduler.js:
```javascript
// At the top:
const DEBUG = true

// In functions:
if (DEBUG) console.log('State:', this.scheduledImage)
```

#### View Ganache Logs

```bash
# Ganache shows every transaction:
# Watch for:
# - eth_sendTransaction (write operations)
# - eth_call (read operations)  
# - Contract creations
# - Gas usage
```

#### Check Docker Logs

```bash
# List all containers:
docker ps -a

# View logs:
docker logs <container_id>

# Follow logs:
docker logs -f <container_id>
```

#### Inspect Smart Contract State

```javascript
// In Truffle console:
const instance = await Canteen.deployed()

// View all members:
const count = await instance.getMembersCount()
for(let i = 0; i < count; i++) {
  const member = await instance.members(i)
  const details = await instance.getMemberDetails(member)
  console.log(`${member}: ${details[0]} (${details[1] ? 'active' : 'inactive'})`)
}
```

---

## API Reference

### Smart Contract Functions

#### Write Functions (Cost Gas)

##### `addMember(string host)`
Registers a new node in the cluster.

**Parameters:**
- `host`: IP:Port (e.g., "127.0.0.1:5000")

**Requirements:**
- Only owner can call
- Host must not already exist

**Example:**
```javascript
await contract.methods.addMember('192.168.1.100:5000').send({
  from: owner,
  gas: 500000
})
```

**Emits:** `MemberJoin(host)`

##### `removeMember(string host)`
Unregisters a node from the cluster.

**Parameters:**
- `host`: IP:Port of node to remove

**Requirements:**
- Only owner can call
- Host must exist and be active

**Example:**
```javascript
await contract.methods.removeMember('192.168.1.100:5000').send({
  from: owner,
  gas: 500000
})
```

**Emits:** `MemberLeave(host)`

##### `addImage(string name, uint replicas)`
Adds a Docker image to deploy across the cluster.

**Parameters:**
- `name`: Docker image name (e.g., "nginx:latest")
- `replicas`: Number of instances to run

**Requirements:**
- Only owner can call
- Image name must not be empty
- Replicas must be > 0
- Image must not already exist

**Example:**
```javascript
await contract.methods.addImage('nginx:latest', 3).send({
  from: owner,
  gas: 1000000
})
```

**What happens:**
- Contract adds image to list
- Triggers rebalancing algorithm
- Nodes automatically pull and start containers

##### `removeImage(string name)`
Removes a Docker image from the cluster.

**Parameters:**
- `name`: Image name to remove

**Requirements:**
- Only owner can call
- Image must exist

**Example:**
```javascript
await contract.methods.removeImage('nginx:latest').send({
  from: owner,
  gas: 1000000
})
```

**What happens:**
- Marks image as inactive
- All nodes running this image get reassigned
- Containers are stopped and removed

##### `addPortForImage(string name, uint from, uint to)`
Configures port mapping for an image.

**Parameters:**
- `name`: Image name
- `from`: Host port
- `to`: Container port

**Example:**
```javascript
await contract.methods.addPortForImage('nginx:latest', 8080, 80).send({
  from: owner,
  gas: 200000
})
```

#### Read Functions (Free)

##### `getMemberDetails(string host) returns (string image, bool active)`
Gets information about a cluster member.

**Parameters:**
- `host`: IP:Port of node

**Returns:**
- `image`: Currently assigned Docker image
- `active`: Whether node is active

**Example:**
```javascript
const details = await contract.methods.getMemberDetails('127.0.0.1:5000').call()
console.log('Image:', details[0])
console.log('Active:', details[1])
```

##### `getImageDetails(string name) returns (uint replicas, uint deployed, bool active)`
Gets information about a Docker image.

**Parameters:**
- `name`: Image name

**Returns:**
- `replicas`: Desired number of replicas
- `deployed`: Current number of running replicas
- `active`: Whether image is active

**Example:**
```javascript
const details = await contract.methods.getImageDetails('nginx:latest').call()
console.log('Desired replicas:', details[0])
console.log('Running replicas:', details[1])
console.log('Active:', details[2])
```

##### `getMembersCount() returns (uint)`
Returns total number of registered nodes.

**Example:**
```javascript
const count = await contract.methods.getMembersCount().call()
console.log('Total nodes:', count)
```

##### `getImagesCount() returns (uint)`
Returns total number of registered images.

**Example:**
```javascript
const count = await contract.methods.getImagesCount().call()
console.log('Total images:', count)
```

##### `members(uint index) returns (string)`
Gets member host at array index.

**Example:**
```javascript
const host = await contract.methods.members(0).call()
console.log('First node:', host)
```

##### `images(uint index) returns (string)`
Gets image name at array index.

**Example:**
```javascript
const image = await contract.methods.images(0).call()
console.log('First image:', image)
```

##### `getPortsForImage(string name) returns (uint[2][])`
Gets port mappings for an image.

**Parameters:**
- `name`: Image name

**Returns:**
- Array of [hostPort, containerPort] pairs

**Example:**
```javascript
const ports = await contract.methods.getPortsForImage('nginx:latest').call()
ports.forEach(([host, container]) => {
  console.log(`${host} -> ${container}`)
})
```

### Events

##### `MemberJoin(string host)`
Emitted when a node joins the cluster.

**Parameters:**
- `host`: IP:Port of new node

##### `MemberLeave(string host)`
Emitted when a node leaves the cluster.

**Parameters:**
- `host`: IP:Port of departing node

##### `MemberImageUpdate(string host, string image)`
Emitted when a node's assigned image changes.

**Parameters:**
- `host`: IP:Port of node
- `image`: New Docker image assigned

### REST API Endpoints

#### `GET /cluster`
Returns list of cluster members.

**Response:**
```json
{
  "members": [
    "127.0.0.1:5000",
    "192.168.1.100:5000"
  ]
}
```

**Example:**
```bash
curl http://localhost:3000/cluster
```

### Command Line Interface

#### Start Node
```bash
npm run start
# Or with custom port:
npm run start -- port=5001
```

#### Deploy Contract
```bash
npx truffle migrate --network development
# Or force redeployment:
npx truffle migrate --network development --reset
```

#### Compile Contracts
```bash
npx truffle compile
```

#### Run Tests
```bash
npx truffle test
```

#### Open Truffle Console
```bash
npx truffle console --network development
```

---

## Example Workflows

### Workflow 1: Deploy a Simple Web Server

**Goal:** Run 2 replicas of nginx across your cluster

```bash
# Step 1: Start Ganache
ganache --port 7545

# Step 2: Deploy contract
npx truffle migrate --network development --reset
# Note the contract address!

# Step 3: Start Canteen node
npm run start

# Step 4: Add nginx image (in Truffle console)
npx truffle console --network development
```

```javascript
const Canteen = await artifacts.require('Canteen')
const instance = await Canteen.deployed()
const accounts = await web3.eth.getAccounts()

// Add nginx with 2 replicas
await instance.addImage('nginx:latest', 2, { from: accounts[0] })

// Configure port mapping
await instance.addPortForImage('nginx:latest', 8080, 80, { from: accounts[0] })

// Check status
const details = await instance.getImageDetails('nginx:latest')
console.log('Nginx replicas running:', details[1].toString())
```

```bash
# Step 5: Verify container is running
docker ps | grep nginx

# Step 6: Access nginx
curl http://localhost:8080
```

### Workflow 2: Multi-Container Application

**Goal:** Deploy a complete app (web + database + cache)

```javascript
// In Truffle console:
const accounts = await web3.eth.getAccounts()
const owner = accounts[0]
const instance = await Canteen.deployed()

// Add frontend (2 replicas for redundancy)
await instance.addImage('myapp/frontend:v1', 2, { from: owner })
await instance.addPortForImage('myapp/frontend:v1', 3000, 80, { from: owner })

// Add backend API (3 replicas for load balancing)
await instance.addImage('myapp/backend:v1', 3, { from: owner })
await instance.addPortForImage('myapp/backend:v1', 8000, 8000, { from: owner })

// Add database (1 replica - stateful)
await instance.addImage('postgres:14', 1, { from: owner })
await instance.addPortForImage('postgres:14', 5432, 5432, { from: owner })

// Add cache (2 replicas)
await instance.addImage('redis:latest', 2, { from: owner })
await instance.addPortForImage('redis:latest', 6379, 6379, { from: owner })

// Monitor deployment
const checkDeployment = async () => {
  const images = ['myapp/frontend:v1', 'myapp/backend:v1', 'postgres:14', 'redis:latest']
  for(const img of images) {
    const details = await instance.getImageDetails(img)
    console.log(`${img}: ${details[1]}/${details[0]} replicas`)
  }
}

await checkDeployment()
```

### Workflow 3: Scaling Up

**Goal:** Increase replicas of a running service

```javascript
// Currently: 2 nginx replicas
// Goal: Scale to 5 replicas

// Unfortunately, there's no "updateImage" function!
// You need to:
// 1. Remove the old configuration
// 2. Add it again with new replica count

// Remove nginx
await instance.removeImage('nginx:latest', { from: owner })

// Wait a few seconds for containers to stop
await new Promise(resolve => setTimeout(resolve, 5000))

// Add nginx with 5 replicas
await instance.addImage('nginx:latest', 5, { from: owner })
await instance.addPortForImage('nginx:latest', 8080, 80, { from: owner })

// Verify
const details = await instance.getImageDetails('nginx:latest')
console.log('Nginx replicas:', details[1].toString(), '/', details[0].toString())
```

**Note:** In a production system, you'd add an `updateImage()` function to the smart contract!

---

## Learning Resources

### Web3 & Blockchain

1. **CryptoZombies** (https://cryptozombies.io/)
   - Interactive Solidity tutorial
   - Free, gamified learning
   - Great for beginners

2. **Ethereum.org** (https://ethereum.org/en/developers/docs/)
   - Official Ethereum documentation
   - Comprehensive guides
   - Best practices

3. **Web3.js Documentation** (https://web3js.readthedocs.io/)
   - Complete API reference
   - Examples and tutorials

### Docker & Containers

1. **Docker Getting Started** (https://docs.docker.com/get-started/)
   - Official Docker tutorial
   - Hands-on exercises

2. **Play with Docker** (https://labs.play-with-docker.com/)
   - Free online Docker environment
   - No installation needed

### Solidity Programming

1. **Solidity by Example** (https://solidity-by-example.org/)
   - Code snippets and patterns
   - Common use cases

2. **OpenZeppelin** (https://docs.openzeppelin.com/)
   - Secure smart contract library
   - Best practices and patterns

### Distributed Systems

1. **Designing Data-Intensive Applications** (Book)
   - By Martin Kleppmann
   - Chapter on consensus and coordination

2. **Raft Consensus** (https://raft.github.io/)
   - Visual explanation of distributed consensus
   - Similar concepts to blockchain

---

## What's Next?

### Experiment Ideas

1. **Add Monitoring**
   - Integrate Prometheus for metrics
   - Track container CPU/memory usage
   - Alert on failures

2. **Implement Health Checks**
   - Ping containers periodically
   - Remove unhealthy nodes automatically
   - Reschedule containers

3. **Add Storage Management**
   - Handle persistent volumes
   - Database backups
   - Distributed file systems (IPFS)

4. **Build a Better Dashboard**
   - Real-time cluster visualization (D3.js)
   - Container logs viewer
   - Deployment history

5. **Improve Scheduling Algorithm**
   - Consider resource constraints (CPU, RAM)
   - Implement affinity rules (don't put all replicas on same node)
   - Priority-based scheduling

6. **Add Authentication**
   - MetaMask integration for dashboard
   - Signature-based API authentication
   - Role-based access control in smart contract

### Contributing

Want to improve Canteen? Here's how:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes**
4. **Test thoroughly**
5. **Submit a pull request**

**Ideas for contributions:**
- Add tests for smart contract
- Improve error handling
- Add configuration file support
- Implement proper logging
- Write more documentation
- Create video tutorials

---

## Conclusion

Congratulations! 🎉 You now understand:
- ✅ How Canteen orchestrates containers using blockchain
- ✅ Key Web3 concepts (accounts, transactions, gas, smart contracts)
- ✅ How to deploy and interact with Ethereum smart contracts
- ✅ How to manage a decentralized application
- ✅ Docker fundamentals and container management

### Key Takeaways

1. **Blockchain isn't just for cryptocurrency** - It's great for coordination without central authority
2. **Smart contracts are programs** - They run on the blockchain and enforce rules
3. **Gas is the cost of computation** - Every operation costs something
4. **Events are powerful** - Use them for notifications and audit logs
5. **Web3 is the future** - Decentralized applications are here to stay

### Final Tips

- 🔐 **Never share private keys** in production
- 🧪 **Test thoroughly** on testnets before mainnet
- 💰 **Start small** - Gas costs add up on mainnet
- 📚 **Keep learning** - Web3 evolves rapidly
- 🤝 **Join communities** - Reddit, Discord, Twitter are helpful

### Get Help

- **Issues**: Open a GitHub issue
- **Questions**: Tag on Stack Overflow with [web3] [ethereum]
- **Chat**: Join Ethereum Discord servers
- **Updates**: Follow @ethereum on Twitter

---

**Happy Coding! May your containers be always up and your gas fees always low!** 🚀

---

*Created with ❤️ for Web3 learners*
*Last updated: October 14, 2025*
