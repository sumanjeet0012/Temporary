# Canteen - Complete Project Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [What Problem Does It Solve?](#what-problem-does-it-solve)
3. [How Canteen Works](#how-canteen-works)
4. [Architecture & Technology Stack](#architecture--technology-stack)
5. [Prerequisites](#prerequisites)
6. [Installation & Setup Guide](#installation--setup-guide)
7. [Project Structure Explained](#project-structure-explained)
8. [Core Components Deep Dive](#core-components-deep-dive)
9. [Smart Contract Explained](#smart-contract-explained)
10. [How to Use Canteen](#how-to-use-canteen)
11. [Testing](#testing)
12. [Learning Path](#learning-path)
13. [Limitations & Future Improvements](#limitations--future-improvements)
14. [Troubleshooting](#troubleshooting)

---

## Project Overview

**Canteen** is a **decentralized container orchestration system** built on Ethereum blockchain technology. Think of it as a blockchain-based alternative to Kubernetes that provides fault-tolerant, decentralized management of Docker containers across a cluster of servers.

### Key Features
- 🔗 **Decentralized**: Uses Ethereum smart contracts for orchestration logic
- 🐳 **Docker Integration**: Manages Docker containers across multiple nodes
- 🔄 **Auto-healing**: Automatically reschedules containers when nodes fail
- 📊 **Load Balancing**: Distributes containers based on resource availability
- 🌐 **SWIM Protocol**: Uses gossip-based protocol for cluster membership
- 📈 **Web Dashboard**: React-based visualization of cluster status

---

## What Problem Does It Solve?

### The Challenge
Modern companies rely on complex distributed systems with multiple components:
- Databases (PostgreSQL, MongoDB, etc.)
- Backend services
- Stream processing platforms
- Cache systems
- Microservices

If any of these components fail, entire businesses can go down, costing **hundreds of thousands of dollars per hour** (e.g., a stock exchange database outage).

### Traditional Solution: Kubernetes/DC/OS
Container orchestrators like Kubernetes solve this by:
- Distributing containers across servers
- Monitoring component health
- Auto-restarting failed containers
- Load balancing

### Problems with Traditional Orchestrators
1. **Single Point of Failure**: If Kubernetes itself goes down, everything fails
2. **Complexity**: Requires extensive configuration and maintenance
3. **Resource Heavy**: Needs significant computational resources
4. **Dependencies**: Requires additional components (e.g., etcd database)

### Canteen's Solution
Canteen eliminates these issues by:
- Using blockchain as the **immutable, decentralized source of truth**
- No single point of failure (blockchain consensus)
- Simpler setup and configuration
- Lightweight architecture

---

## How Canteen Works

### High-Level Flow

```
┌─────────────────────────────────────────────────────┐
│          Ethereum Smart Contract (Canteen)          │
│  - Stores cluster state                             │
│  - Manages members (nodes/servers)                  │
│  - Manages images (Docker containers)               │
│  - Scheduling logic                                 │
└───────────────┬─────────────────────────────────────┘
                │
        ┌───────┴────────┐
        │                │
┌───────▼──────┐  ┌──────▼───────┐  ┌────────────┐
│   Node 1     │  │   Node 2     │  │   Node N   │
│              │  │              │  │            │
│ - Scheduler  │  │ - Scheduler  │  │ - Scheduler│
│ - Docker     │  │ - Docker     │  │ - Docker   │
│ - SWIM       │  │ - SWIM       │  │ - SWIM     │
└──────────────┘  └──────────────┘  └────────────┘
       │                │                  │
       └────────────────┴──────────────────┘
                    │
            SWIM Protocol (Gossip)
            - Cluster membership
            - Health checks
```

### Step-by-Step Process

1. **Node Registration**
   - Each server runs a Canteen node
   - Node registers itself with the smart contract
   - Gets assigned to the cluster

2. **Image Registration**
   - Admin registers Docker images (e.g., `rethinkdb:latest`)
   - Specifies number of replicas needed

3. **Scheduling**
   - Smart contract assigns images to nodes using round-robin algorithm
   - Considers replica requirements and node availability

4. **Deployment**
   - Each node watches the smart contract
   - When assigned an image, pulls from Docker Hub
   - Starts the container locally

5. **Health Monitoring**
   - SWIM protocol monitors node health via gossip
   - Nodes periodically check smart contract for changes

6. **Auto-healing**
   - When a node fails, SWIM detects it
   - Remaining nodes rebalance containers
   - Failed containers automatically rescheduled to healthy nodes

---

## Architecture & Technology Stack

### Blockchain Layer
- **Ethereum Smart Contract (Solidity)**: Core orchestration logic
- **Web3.js**: JavaScript library for blockchain interaction
- **Truffle**: Smart contract development framework

### Node/Backend Layer
- **Node.js**: Runtime environment
- **Babel**: ES6+ transpilation
- **Dockerode**: Docker API client for Node.js
- **SWIM Protocol**: Gossip-based cluster membership

### Frontend/Dashboard
- **React**: UI framework
- **D3.js**: Data visualization for cluster topology
- **Styled Components**: CSS-in-JS styling
- **Express**: Web server for API endpoints

### Infrastructure
- **Docker**: Container runtime
- **Ethereum Node**: Local (Ganache) or network (Ropsten, Rinkeby)

---

## Prerequisites

### Knowledge Prerequisites

#### Essential (Must Have)
1. **JavaScript (ES6+)**
   - Async/await, promises
   - Classes and modules
   - Arrow functions
   
2. **Node.js & npm**
   - Package management
   - Running scripts
   - Environment basics

3. **Docker Basics**
   - What containers are
   - Docker images vs containers
   - Basic commands (pull, run, stop)

4. **Blockchain Basics**
   - What blockchain is
   - Smart contracts concept
   - Transactions and gas

#### Recommended (Should Have)
5. **Solidity (Ethereum Smart Contracts)**
   - Data types (struct, mapping, array)
   - Functions and modifiers
   - Events

6. **React.js**
   - Components and state
   - Lifecycle methods
   - Hooks (optional)

7. **Distributed Systems Concepts**
   - Cluster computing
   - Fault tolerance
   - Load balancing

#### Nice to Have
8. **Kubernetes/Container Orchestration**
   - Understanding of orchestration problems
   - Scheduling concepts
   
9. **Web3 Development**
   - MetaMask
   - Ethereum networks
   - Gas optimization

### Software Prerequisites

#### Required
- **Node.js** (v8.x or higher)
- **npm** (v5.x or higher)
- **Docker** (v17.x or higher)
- **Git**

#### For Smart Contract Development
- **Truffle** (`npm install -g truffle`)
- **Ganache** (local Ethereum blockchain)
  - Download from: https://www.trufflesuite.com/ganache
  - Or use CLI: `npm install -g ganache-cli`

#### Operating System
- **Linux** (recommended) or **macOS**
- Windows with WSL2 (Windows Subsystem for Linux)

---

## Installation & Setup Guide

### Step 1: Clone and Install Dependencies

```bash
# Clone the repository
cd /Users/sumanjeet/code/py-libp2p-experiment

# Install main project dependencies
npm install

# Install dashboard dependencies
cd dashboard
npm install
cd ..
```

### Step 2: Start Local Ethereum Network

**Option A: Using Ganache GUI**
1. Download and install Ganache from https://www.trufflesuite.com/ganache
2. Open Ganache
3. Click "Quickstart" to create a workspace
4. Note the RPC Server address (usually `http://127.0.0.1:8545`)

**Option B: Using Ganache CLI**
```bash
npm install -g ganache-cli
ganache-cli -p 8545
```

### Step 3: Compile Smart Contracts

```bash
# Compile Solidity contracts
truffle compile
```

This creates compiled contracts in `build/contracts/` directory.

### Step 4: Deploy Smart Contract

```bash
# Deploy to local network
truffle migrate

# Or use the deploy script
npm run deploy
```

**Important**: Note the deployed contract address from the output!

### Step 5: Update Configuration

Edit `index.js` with your contract details:

```javascript
scheduler.start(
  new Web3.providers.HttpProvider('http://localhost:8545'),
  '0xYOUR_CONTRACT_ADDRESS_HERE',  // Replace with deployed address
  '0xYOUR_PRIVATE_KEY_HERE'         // Use a test account private key
)
```

### Step 6: Start Canteen Nodes

**Terminal 1 - Node 1:**
```bash
npm start -- port=5000
```

**Terminal 2 - Node 2 (connects to Node 1):**
```bash
npm start -- port=5001 nodes=127.0.0.1:5000
```

**Terminal 3 - Node 3 (connects to Node 1):**
```bash
npm start -- port=5002 nodes=127.0.0.1:5000
```

### Step 7: Start Dashboard (Optional)

```bash
cd dashboard
npm start
```

Dashboard opens at `http://localhost:3000`

### Step 8: Register Docker Images

Use Truffle console to interact with the contract:

```bash
truffle console
```

In the console:
```javascript
// Get contract instance
let canteen = await Canteen.deployed()

// Add a Docker image with 2 replicas
await canteen.addImage("nginx:latest", 2)

// Add another image
await canteen.addImage("redis:latest", 1)

// Check image details
await canteen.getImageDetails("nginx:latest")
```

---

## Project Structure Explained

```
py-libp2p-experiment/
│
├── contracts/              # Solidity smart contracts
│   ├── Canteen.sol        # Main orchestration contract
│   └── Migrations.sol     # Truffle deployment tracking
│
├── migrations/            # Deployment scripts
│   ├── 1_initial_migration.js
│   └── 2_deploy_contracts.js
│
├── test/                  # Smart contract tests
│   └── canteen_test.js    # Automated test suite
│
├── dashboard/             # React frontend
│   ├── src/
│   │   ├── App.js        # Main dashboard component
│   │   ├── Canteen.json  # Contract ABI
│   │   └── index.js      # Entry point
│   ├── public/           # Static assets
│   └── package.json
│
├── build/                 # Compiled contracts (auto-generated)
│
├── index.js              # Main entry point
├── cluster.js            # SWIM protocol implementation
├── scheduler.js          # Container scheduling logic
├── web-server.js         # API server for cluster info
├── deploy.js             # Contract deployment script
├── truffle.js            # Truffle configuration
└── package.json          # Dependencies
```

---

## Core Components Deep Dive

### 1. Smart Contract (`contracts/Canteen.sol`)

#### Key Data Structures

```solidity
struct Member {
    string imageName;  // Assigned Docker image
    bool active;       // Is node active?
}

struct Image {
    uint replicas;     // Desired number of replicas
    uint deployed;     // Currently deployed count
    bool active;       // Is image active?
}
```

#### Key Functions

**Member Management:**
- `addMember(host)`: Register a new node
- `removeMember(host)`: Deregister a node
- `getMemberDetails(host)`: Get node's assigned image

**Image Management:**
- `addImage(name, replicas)`: Register Docker image
- `removeImage(name)`: Unregister image
- `getImageDetails(name)`: Get image stats

**Scheduling:**
- `rebalanceWithUnfortunateImage()`: Redistribute containers
- `getNextImageToUse()`: Select least-used image

### 2. Scheduler (`scheduler.js`)

**Purpose**: Watches smart contract and manages local Docker containers

#### Key Methods

```javascript
async start(provider, contractAddress, privateKey)
// Initialize scheduler, register node

async loop()
// Continuously check for assigned image changes

async registerNode()
// Register this node with smart contract

async updateScheduler(scheduledImage)
// Pull and start assigned Docker image

async cleanup()
// Stop and remove containers on shutdown
```

#### Workflow
1. Connects to Ethereum node
2. Registers server as cluster member
3. Polls smart contract every second
4. On image assignment:
   - Pulls image from Docker Hub
   - Creates/starts container
   - Exposes ports
5. On reassignment:
   - Stops old container
   - Starts new container

### 3. Cluster Manager (`cluster.js`)

**Purpose**: Manages cluster membership using SWIM protocol

#### SWIM Protocol
- **S**calable **W**eakly-consistent **I**nfection-style **M**embership
- Gossip-based protocol
- Detects node failures quickly
- Low network overhead

#### Methods

```javascript
start(port, nodes)
// Start SWIM node on specified port
// Bootstrap by connecting to existing nodes

getHost()
// Get this node's host:port identifier

getProtocol()
// Get SWIM instance for monitoring
```

### 4. Web Server (`web-server.js`)

**Purpose**: Provides REST API for cluster status

#### Endpoints

**GET `/cluster`**
- Returns list of all cluster members
- Used by dashboard for visualization

```json
{
  "members": [
    "127.0.0.1:5000",
    "127.0.0.1:5001",
    "127.0.0.1:5002"
  ]
}
```

### 5. Dashboard (`dashboard/src/App.js`)

**Purpose**: Visualizes cluster topology using D3.js

#### Features
- Real-time cluster member visualization
- Force-directed graph layout
- Add/remove images via UI
- Contract interaction
- Cluster health monitoring

#### Key State

```javascript
this.state = {
  status: 'connecting...',
  contract: '0x...',        // Contract address
  images: [],               // Registered images
  members: [],              // Cluster nodes
  schedulings: []           // Image assignments
}
```

---

## Smart Contract Explained

### Scheduling Algorithm

Canteen uses a **priority-based round-robin** algorithm:

#### Step 1: Fill Empty Nodes
```
If Node has no image AND Image needs more replicas:
    Assign Image to Node
```

#### Step 2: Rebalance
```
For each node with an image:
    Calculate current ratio = deployed / replicas
    If a different image has lower ratio:
        Reassign node to that image
```

#### Example

**Initial State:**
- Nodes: [A, B, C, D]
- Images: nginx (replicas: 2), redis (replicas: 2)

**Scheduling:**
1. Assign nginx to A → [nginx, -, -, -]
2. Assign nginx to B → [nginx, nginx, -, -]
3. Assign redis to C → [nginx, nginx, redis, -]
4. Assign redis to D → [nginx, nginx, redis, redis]

**Result:** Balanced distribution (2 nginx, 2 redis)

### Events

The contract emits events for off-chain monitoring:

```solidity
event MemberJoin(string host)
event MemberLeave(string host)
event MemberImageUpdate(string host, string image)
```

Dashboard listens to these events for real-time updates.

---

## How to Use Canteen

### Use Case 1: Deploy a Simple Web Server

```bash
# 1. Start 3 Canteen nodes (in separate terminals)
npm start -- port=5000
npm start -- port=5001 nodes=127.0.0.1:5000
npm start -- port=5002 nodes=127.0.0.1:5000

# 2. Register image via Truffle console
truffle console
> let canteen = await Canteen.deployed()
> await canteen.addImage("nginx:latest", 3)

# 3. Verify deployment
> await canteen.getImageDetails("nginx:latest")
# Should show: replicas=3, deployed=3

# 4. Check containers
docker ps
# Should see 3 nginx containers running
```

### Use Case 2: Database Replication

```javascript
// Deploy RethinkDB with 2 replicas
await canteen.addImage("rethinkdb:latest", 2)

// Each node running RethinkDB can join a cluster
// Provides fault tolerance
```

### Use Case 3: Microservices

```javascript
// API server - 3 replicas
await canteen.addImage("mycompany/api-server:v1", 3)

// Worker service - 2 replicas
await canteen.addImage("mycompany/worker:v1", 2)

// Cache - 1 replica
await canteen.addImage("redis:alpine", 1)
```

### Use Case 4: Handle Node Failure

```
Initial: [nginx, nginx, redis] on [Node1, Node2, Node3]

Node2 fails → SWIM detects → Node2 marked inactive

Smart contract rebalances:
[nginx, -, redis] → [nginx, redis, redis]

Remaining nodes automatically pull missing images
```

---

## Testing

### Run Smart Contract Tests

```bash
# Run all tests
npm test

# Or using Truffle directly
truffle test
```

### Test Suite Coverage

The `test/canteen_test.js` file tests:

1. **Initial State**: Empty members and images
2. **Member Management**:
   - Adding members
   - Removing members
   - Rebalancing after removal
3. **Image Management**:
   - Adding images
   - Removing images
   - Port configuration
4. **Scheduling Logic**:
   - Round-robin distribution
   - Replica requirements
   - Rebalancing scenarios

### Example Test

```javascript
it('distributes images correctly', async function () {
  await canteen.addMember("host1")
  await canteen.addImage("img1", 2)
  
  let details = await canteen.getMemberDetails("host1")
  details[0].should.be.equal("img1")  // Assigned img1
  
  await canteen.addMember("host2")
  details = await canteen.getMemberDetails("host2")
  details[0].should.be.equal("img1")  // Also assigned img1
})
```

---

## Learning Path

To fully understand this project, follow this learning path:

### Phase 1: Foundations (1-2 weeks)

#### Week 1: Blockchain & Smart Contracts
1. **Learn Blockchain Basics**
   - Resources:
     - [Blockchain Demo](https://andersbrownworth.com/blockchain/)
     - [Ethereum Whitepaper (Simplified)](https://ethereum.org/en/whitepaper/)
   - Topics:
     - What is blockchain?
     - Consensus mechanisms
     - Smart contracts

2. **Learn Solidity**
   - Resources:
     - [CryptoZombies](https://cryptozombies.io/) (Interactive tutorial)
     - [Solidity by Example](https://solidity-by-example.org/)
   - Practice:
     - Write simple contracts
     - Understand mappings, structs, arrays
     - Learn about gas and optimization

#### Week 2: Docker & Containers
3. **Learn Docker**
   - Resources:
     - [Docker for Beginners](https://docker-curriculum.com/)
     - [Play with Docker](https://labs.play-with-docker.com/)
   - Topics:
     - Images vs containers
     - Dockerfile
     - Docker Hub
     - Basic commands

4. **Understand Container Orchestration**
   - Resources:
     - [Kubernetes Basics](https://kubernetes.io/docs/tutorials/kubernetes-basics/)
   - Concepts:
     - Why orchestration is needed
     - Scheduling
     - Health checks
     - Load balancing

### Phase 2: Core Technologies (1-2 weeks)

#### Week 3: Web3 Development
5. **Learn Web3.js**
   - Resources:
     - [Web3.js Documentation](https://web3js.readthedocs.io/)
     - [Ethereum Development with Web3](https://www.dappuniversity.com/)
   - Practice:
     - Connect to Ethereum
     - Deploy contracts
     - Call contract functions
     - Listen to events

6. **Learn Truffle Framework**
   - Resources:
     - [Truffle Documentation](https://www.trufflesuite.com/docs/truffle/overview)
   - Topics:
     - Compiling contracts
     - Migrations
     - Testing
     - Console interaction

#### Week 4: Distributed Systems
7. **Understand SWIM Protocol**
   - Resources:
     - [SWIM Paper](https://www.cs.cornell.edu/projects/Quicksilver/public_pdfs/SWIM.pdf) (Academic)
     - [Gossip Protocols Explained](https://highscalability.com/gossip-protocol-explained/)
   - Concepts:
     - Membership protocols
     - Failure detection
     - Gossip communication

8. **Learn Node.js & Async Programming**
   - Resources:
     - [Node.js Guide](https://nodejs.dev/learn)
   - Topics:
     - Event loop
     - Promises and async/await
     - Docker API (Dockerode)

### Phase 3: Project Deep Dive (1 week)

#### Week 5: Canteen Implementation
9. **Read the Code**
   - Start with:
     1. `contracts/Canteen.sol` - Understand the state
     2. `scheduler.js` - See how nodes work
     3. `cluster.js` - Understand SWIM usage
     4. `index.js` - See how it all connects

10. **Experiment**
    - Deploy locally
    - Add custom images
    - Simulate node failures
    - Modify scheduling algorithm

11. **Extend**
    - Add resource limits (CPU, memory)
    - Implement health checks
    - Add rolling updates
    - Create monitoring dashboards

### Recommended Resources

#### Books
- **"Mastering Ethereum"** by Andreas M. Antonopoulos
- **"Docker Deep Dive"** by Nigel Poulton
- **"Designing Data-Intensive Applications"** by Martin Kleppmann

#### Online Courses
- [Ethereum and Solidity: The Complete Developer's Guide](https://www.udemy.com/course/ethereum-and-solidity-the-complete-developers-guide/)
- [Docker Mastery](https://www.udemy.com/course/docker-mastery/)
- [Blockchain Specialization (Coursera)](https://www.coursera.org/specializations/blockchain)

#### Practice Projects
1. Build a simple voting dApp
2. Create a multi-node Docker Swarm cluster
3. Write a gossip protocol implementation
4. Build a Web3 application with React

---

## Limitations & Future Improvements

### Current Limitations

1. **Scheduling Algorithm**
   - Only priority-based round-robin
   - No resource awareness (CPU, RAM, disk)
   - No affinity/anti-affinity rules

2. **Gas Costs**
   - Every scheduling change costs gas
   - Not suitable for frequent changes
   - Can be expensive on mainnet

3. **Scalability**
   - On-chain scheduling doesn't scale well
   - Limited by blockchain throughput
   - State storage costs increase

4. **Security**
   - No authentication between nodes
   - Docker socket exposed
   - Private key management

5. **Features**
   - No rolling updates
   - No health checks
   - No volume management
   - No secrets management

### Planned Improvements (from README)

1. **Advanced Scheduling**
   - Resource-based scheduling
   - Custom scheduling policies
   - Priority queues

2. **State Channels**
   - Move intensive operations off-chain
   - Reduce gas costs
   - Improve performance

3. **Decentralized Cloud**
   - Peer-to-peer hosting marketplace
   - Pay for computational resources
   - No cloud vendor lock-in

### How You Can Contribute

1. **Implement Resource-Aware Scheduling**
   - Add CPU/memory limits to smart contract
   - Monitor node resources
   - Schedule based on availability

2. **Add Health Checks**
   - Container health monitoring
   - Automatic restart on failure
   - Custom health check endpoints

3. **Improve Security**
   - TLS for inter-node communication
   - Private key encryption
   - Access control for Docker API

4. **Build Monitoring**
   - Prometheus metrics
   - Grafana dashboards
   - Alert system

---

## Troubleshooting

### Common Issues

#### Issue 1: "Cannot connect to Docker daemon"

**Error:**
```
Error: connect EACCES /var/run/docker.sock
```

**Solution:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Restart shell or run
newgrp docker

# On macOS, ensure Docker Desktop is running
```

#### Issue 2: "Transaction has been reverted"

**Possible Causes:**
- Node already registered
- Image already exists
- Insufficient gas

**Solution:**
```javascript
// Check if member exists first
let details = await canteen.getMemberDetails("127.0.0.1:5000")
console.log(details)

// Ensure sufficient gas
await canteen.addMember("host", {gas: 500000})
```

#### Issue 3: "Cannot find module 'web3'"

**Solution:**
```bash
# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install
```

#### Issue 4: Nodes not joining cluster

**Check:**
```bash
# Verify SWIM is working
# In node logs, look for:
"Joining N specified bootstrap node(s)"
"Cluster members: [...]"
```

**Solution:**
- Ensure bootstrap node is running first
- Check firewall settings
- Use correct host:port format

#### Issue 5: Contract address not found

**Error:**
```
Error: Returned values aren't valid, did it run Out of Gas?
```

**Solution:**
1. Redeploy contract: `truffle migrate --reset`
2. Update address in `index.js`
3. Copy ABI to dashboard: `cp build/contracts/Canteen.json dashboard/src/`

---

## Key Concepts Summary

### Blockchain Layer
- **Smart contract = single source of truth**
- Stores cluster state immutably
- Scheduling logic runs on-chain
- Events notify off-chain components

### Node Layer
- **Each node = autonomous agent**
- Watches smart contract
- Executes container operations
- Reports health via SWIM

### Orchestration Flow
```
User registers image → Smart contract schedules → 
Nodes detect change → Pull image → Start container
```

### Fault Tolerance
```
Node fails → SWIM detects → 
Other nodes check contract → 
Rebalance if needed → Start missing containers
```

---

## Glossary

**Blockchain**: Distributed ledger maintained by network consensus

**Smart Contract**: Self-executing code on blockchain

**Gas**: Computational cost unit on Ethereum

**Docker Image**: Packaged application with dependencies

**Container**: Running instance of Docker image

**Node**: Server running Canteen software

**Replica**: Copy of a container for redundancy

**Scheduling**: Assigning containers to nodes

**SWIM**: Membership protocol for cluster monitoring

**Gossip Protocol**: Communication pattern where nodes randomly share information

**Web3**: Library for blockchain interaction

**ABI**: Application Binary Interface (contract interface definition)

**Truffle**: Development framework for Ethereum

**Ganache**: Local Ethereum blockchain for testing

---

## Quick Reference Commands

### Blockchain
```bash
# Start local blockchain
ganache-cli -p 8545

# Compile contracts
truffle compile

# Deploy contracts
truffle migrate

# Run tests
truffle test

# Open console
truffle console
```

### Canteen
```bash
# Start first node
npm start -- port=5000

# Start additional nodes
npm start -- port=5001 nodes=127.0.0.1:5000

# Deploy contract
npm run deploy
```

### Docker
```bash
# List running containers
docker ps

# View container logs
docker logs <container_id>

# Stop all containers
docker stop $(docker ps -q)

# Remove all containers
docker rm $(docker ps -aq)
```

### Smart Contract Interaction
```javascript
// In truffle console
let canteen = await Canteen.deployed()

// Add member
await canteen.addMember("127.0.0.1:5000")

// Add image
await canteen.addImage("nginx:latest", 2)

// Check image details
await canteen.getImageDetails("nginx:latest")

// Check member details
await canteen.getMemberDetails("127.0.0.1:5000")

// Get counts
await canteen.getMembersCount()
await canteen.getImagesCount()
```

---

## Conclusion

Canteen demonstrates how blockchain technology can solve real-world infrastructure problems. By decentralizing container orchestration, it eliminates single points of failure while maintaining simplicity.

**Key Takeaways:**
1. Blockchain as infrastructure, not just for finance
2. Smart contracts can manage complex distributed systems
3. Combining on-chain logic with off-chain execution
4. Practical application of consensus mechanisms

**Next Steps:**
1. Set up local environment
2. Deploy and test Canteen
3. Understand each component
4. Experiment with modifications
5. Contribute improvements

**Remember:** This is a hackathon MVP. It's not production-ready but serves as an excellent learning project for blockchain, distributed systems, and container orchestration.

---

## Additional Resources

### Documentation
- [Project README](./README.md)
- [Solidity Documentation](https://docs.soliditylang.org/)
- [Web3.js Documentation](https://web3js.readthedocs.io/)
- [Dockerode Documentation](https://github.com/apocas/dockerode)

### Community
- Ethereum Stack Exchange
- Docker Community Forums
- GitHub Issues

### Related Projects
- Kubernetes
- Docker Swarm
- Apache Mesos
- Nomad

---

**Created:** October 2025  
**Author:** Project Documentation  
**Version:** 1.0  
**Status:** Educational/Experimental

