### Week 1 · Lesson 4: Ethereum Architecture

So far, we've learned three foundations:

* Lesson 1: What a blockchain is and how blocks store data.

* Lesson 2: Cryptography, keys, signatures and Ethereum addresses.

* Lesson 3: Consensus, Proof of Work, Proof of Stake and finality.

Now let's put those concepts together and understand how Ethereum actually works as a running system.

One important thing to understand from the beginning:

Ethereum is not one program running on one computer. It's a network of independently operated nodes, each running software that participates in maintaining the Ethereum network.

By the end of this lesson, you'll understand:

* Ethereum nodes and clients.

* Execution layer vs consensus layer.

* The Ethereum Virtual Machine (EVM).

* Accounts, transactions and state.

* Mempools, blocks and transaction execution.

* How a transaction travels through Ethereum.

* Where libp2p and networking fit into the picture.

### 1\. The big picture: what is an Ethereum node?

Imagine you want to run your own Ethereum node.

You install Ethereum client software, configure it, connect it to other peers, and let it synchronize with the network.

Your node can then independently verify blockchain data rather than blindly trusting a website or third-party API.

![Node architecture | ethereum.org](https://images.openai.com/static-rsc-4/f8lz0V7KRrcKM5U3wTbKzsRD_q0b6afy1syt7ofO47mHis35GFFWqJGViyl1_z6CBS_abx1NXw1STzTUYWSDEZqET92uivCRx_L5UNKn3g7eJ9oogZKR6E0yJbbk0DKtuHCNh6yRlOSdU2dp_cGBRECiUKZL1cnb5Czsx233GNCFrmlNRli5HyPQirtSsA-i?purpose=fullsize)

An Ethereum node generally runs two major software components:

* An Execution Client (EL).

* A Consensus Client (CL).

They work together but have different responsibilities.

### 2\. Execution Layer vs Consensus Layer

This is probably the most important architectural distinction in today's lesson.

Execution Layer (EL)

* Executes transactions.

* Runs smart contracts.

* Maintains account balances and contract storage.

* Validates execution results.

    Think: What does this transaction actually do?

Consensus Layer (CL)

* Coordinates validators.

* Handles attestations.

* Selects the canonical chain.

* Manages justification and finality.

    Think: Which blocks should the network accept?

Let's make this concrete.

Suppose Alice sends 1 ETH to Bob.

The execution layer:

* Checks Alice's transaction signature and nonce.

* Checks that Alice can afford the transaction.

* Executes the transfer.

* Calculates the resulting account balances and gas usage.

* Produces the execution result.

The consensus layer:

* Coordinates the validator network.

* Determines which proposed block is selected by fork choice.

* Collects validator attestations.

* Helps establish finality.

Neither layer can replace the other.

### Why did Ethereum separate them?

Ethereum's transition to Proof of Stake in 2022, called The Merge, separated execution responsibilities from consensus responsibilities.

The execution layer still handles transactions and smart contracts. The consensus layer handles Proof of Stake coordination.

This modular architecture allows different clients to implement the same protocols independently.

### 3\. Ethereum clients: multiple implementations

A client is software implementing the Ethereum protocol.

There isn't just one official Ethereum program.

Here are some well-known implementations:

![Geth - Infrastructure tools - Alchemy | Alchemy](https://images.openai.com/static-rsc-4/HTgWTtPWs7u5SFDYZjdOVcmq-XF8kQybvsDGiYgbQZT22Yle9RxEfcOu_gNj7zrmDabPSbiDNI5HEn-nohWsAcQdJoa0IuAdU-2ujJVfO5GqAWn91t6kEGwp81b8rSkBJswIMhNg90GPNOPp-r2sSwpYs-0blCWjV1ecdj29LFBTQownUONfjggH5giY21C3?purpose=fullsize)

Geth

Execution client written in Go. One of the most widely used Ethereum execution clients.

Language: Go

[GitHub repository](https://github.com/ethereum/go-ethereum?utm_source=chatgpt.com)

![EIP-7702 Attack Surfaces: What Developers Should Know | Nethermind](https://images.openai.com/static-rsc-4/7QiJAZOc7S1Y8DA9-j2uzpTx1KU_f8A1a2ockmDjbRWaoXp-wy5KPJTNCNOaIrW-UubxQyZbwdZqtcdmxTs2fvz5G8g1a5cJ2NI9IPUI6MEtUpGPKjv_KeUhlslVHfyglW0N1Poe31aqbKJk1koTTG1DDra1p-bLEbywEhS-oBC_MFMO7SyooWyfJIxu3G40?purpose=fullsize)

Nethermind

Execution client written primarily in C#.

Language: C#

[GitHub repository](https://github.com/NethermindEth/nethermind?utm_source=chatgpt.com)

![GitHub - paradigmxyz/reth: Modular, contributor-friendly and blazing-fast implementation of the Ethereum protocol, in Rust](https://images.openai.com/static-rsc-4/UnTEZoLtHhY83Pdrk4jiZITwDrmywIw6dRQhwhUksYYIz9Fwjd5kD7BQk3OPrrw5n7qSrDrzJFqufx2nzmpfrb3jSmXhqZaq3tocfj-BmRfZ_DfCw7eQQKV4aoUCQjWD6pnxA2IBBGmWXJ1ZeWfFG3JzJ3hGcyXre_VxDyY19HSx2GtKJhzUfsfji4k9VN5c?purpose=fullsize)

Reth

Ethereum execution client written in Rust.

Language: Rust

[GitHub repository](https://github.com/paradigmxyz/reth?utm_source=chatgpt.com)

![Lighthouse - Infrastructure tools - Alchemy](https://images.openai.com/static-rsc-4/FW4nTSt98Fe-HRvvn70Iy9bx6i8L2vzXyZD8gdTNwNGcDavPyuih0cwYhKP_1SWbfxLHnyAtXiYTQvAUSxTI4u1wFlqujeE7eZWPu3ORZV9TMIWnQe_PKHN9MQ5mdMOYV_1ilwUol0gkyBA8WuOZFzJSBgbPjBKarIcjMyXwhX3RVYp0GmTE-Ovv9My8dmns?purpose=fullsize)

Lighthouse

Consensus client written in Rust.

Language: Rust

[GitHub repository](https://github.com/sigp/lighthouse?utm_source=chatgpt.com)

![Prysm Ethereum Client (@prylabs) on X](https://images.openai.com/static-rsc-4/ZclGPUO1-2ZsxxU8em81V_3q4cn0Z1qohtOAStgZwnZL2KmaGuvDzcm6bI9040gBZHWxBI0nzjWSAFWjD6GF6Gf5qTlzxTreGUpDctmY2vfnh0nJcw_JEuzstvhl-RgRw0xKJXo0hgD2lizFpT_ZvePiDYuQeXvek_LA11mMDSZrm5PrrWC26a5wO_mtZWkn?purpose=fullsize)

Prysm

Consensus client written in Go.

Language: Go

[GitHub repository](https://github.com/OffchainLabs/prysm?utm_source=chatgpt.com)

Other important implementations include Besu and Erigon for execution, and Teku, Nimbus and Lodestar for consensus.

The important principle is client diversity.

If every node used exactly the same implementation and a critical bug existed in it, the entire network could be affected.

Multiple independent implementations reduce that risk, although they do not eliminate shared protocol bugs.

### 4\. The Engine API: how the two clients communicate

We know the execution client and consensus client are separate programs. But how do they coordinate?

They communicate through something called the Engine API.

Consensus Client

Chooses and coordinates the chain

Engine API

Local authenticated RPC connection

Execution Client

Executes transactions and validates state changes

For example, when a consensus client receives a proposed block, it asks the execution client to execute the transactions inside it.

Some important Engine API methods:

| Method                   | Purpose                                                       |
| ------------------------ | ------------------------------------------------------------- |
| engine_newPayload        | Submit an execution payload for validation                    |
| engine_forkchoiceUpdated | Tell the execution client about the current fork-choice state |
| engine_getPayload        | Retrieve a prepared execution payload                         |

The execution client independently executes the transactions and checks whether the resulting state matches the proposed block's commitments.

If valid, it reports that result to the consensus client.

This is a critical architectural property: the consensus client doesn't simply trust the execution client's claims about transaction execution.

The clients communicate over a local RPC interface, typically authenticated using a shared JWT secret. ethereum.org +2

### 5\. The Ethereum Virtual Machine (EVM)

Let's now understand the execution engine itself.

The Ethereum Virtual Machine (EVM) is a virtual computer that executes smart contract code according to Ethereum's protocol rules.

Think about a normal computer:

* CPU executes instructions.

* Memory stores temporary values.

* Storage keeps persistent data.

* Programs perform operations.

The EVM has similar concepts, but its behaviour is specified so that independent Ethereum nodes execute the same transaction and arrive at the same result.

![Introduction to the Ethereum Virtual Machine (EVM) | by Andrey Obruchkov | Medium](https://images.openai.com/static-rsc-4/HNLuPJRsA-6a275scldBwra5qXHixyD7LaXEauoAyfaNPHSoYoRvGWi1sjgAVAZPwsrutj1RtOkMb0EDsBa5dK1peu7OlQknTCpbU-15Ze6qj9UWmOTyJ-lFByhGy0SPDGwbYPHVD2aAAKvlGBwF2sYPw2YFa7hwEIR_Hbd4UxnwgagF6po41_EDHMS75pCy?purpose=fullsize)

### 5.1 The EVM is a stack machine

The EVM primarily uses a stack-based execution model.

Imagine a simple calculation:

```text
5 + 3
```

Conceptually, the EVM might perform:

```text
PUSH 5
PUSH 3
ADD
```

The stack now contains:

```text
[8]
```

The EVM has instructions called opcodes, such as:

| Opcode | Meaning                           |
| ------ | --------------------------------- |
| PUSH   | Put a value on the stack          |
| ADD    | Add two values                    |
| MUL    | Multiply values                   |
| SLOAD  | Read persistent contract storage  |
| SSTORE | Write persistent contract storage |
| CALL   | Call another account or contract  |
| RETURN | Return execution data             |
| REVERT | Revert execution                  |

EVM stack values are 256-bit words, and the stack has a maximum depth of 1024 items. ethereum.org

### 5.2 What is smart contract bytecode?

You generally write smart contracts in Solidity or another high-level language.

For example:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Counter {
    uint256 public count;

    function increment() public {
        count += 1;
    }
}
```

The compiler converts this program into EVM bytecode.

The EVM executes the bytecode, not the Solidity source code.

Solidity source code

Human-readable contract

Solidity compiler

EVM bytecode

Machine instructions for the EVM

EVM execution

State changes and execution results

### 5.3 Why does every node execute the same code?

Suppose 10,000 nodes execute the same valid transaction.

They must all arrive at the same state transition.

If execution depended on the current time of each computer, random local values, or external HTTP requests, different nodes could produce different results.

Therefore, smart contracts cannot simply make arbitrary internet requests during ordinary EVM execution. External information generally enters through transactions, often supplied by oracle systems.

This deterministic execution property is essential to blockchain consensus.

### 6\. Ethereum accounts: EOA vs Contract Account

Ethereum has two fundamental account types.

![What are multi-signature contracts? | Alchemy Docs](https://images.openai.com/static-rsc-4/U76KNkMtHiIVpiAtX34Comzvud5Sget0siGY--miccLDOQiFTBtDzP4w-SgZhpu9vhmFnaph2my550j2PFgaFUUKSbP28JBJ-7W-jeSef1FB5F2UuEzseSx_c8aQd85mm49j8poWuo-g0E3aEiEKJafu6JpE71wYXGd-NZJD23INqdMNTWPEngHFw43Y1ytz?purpose=fullsize)

Externally Owned Account (EOA)

Controlled by a private key. Can initiate signed transactions.

![What Are Smart Contracts and How Do They Work?](https://images.openai.com/static-rsc-4/24unIE3JWcZC2Zvl2a-HZAZoFX6nfa5V00t2fGTMX0y91TeJdUpJCBUp-_NxCaCBg28mRmfMQ7DC5TqfpbljIMnAczlX9-1ApuO1h5j8SRGS6H_P3B34Xv7Wr9f5U22gdPj8L5ULFpC16SOvBz9AoMC4-zHt57l3hMEpuH8bYL5F8NSOqpegHkXDL_BnX0tV?purpose=fullsize)

Contract Account

Controlled by deployed code. Executes when called through a transaction or another contract.

### EOA

An EOA is the type of account associated with a wallet such as MetaMask.

It has:

* Address.

* ETH balance.

* Transaction nonce.

An EOA is controlled by a private key.

### Contract account

A contract account has:

* Address.

* ETH balance.

* Contract code.

* Persistent storage.

It does not have a private key of its own.

For example, our `Counter` contract stores a number:

```text
count = 0
```

After someone calls `increment()`:

```text
count = 1
```

The change becomes part of Ethereum's persistent state once the transaction is included and accepted.

### A key difference

An EOA can originate a transaction. A contract account cannot independently wake up and originate a transaction; it executes in response to a call or other transaction-triggered execution.

### 7\. Ethereum state: what exactly is stored?

This is an important distinction.

A blockchain is not merely a list of transactions. Ethereum maintains a global state.

Imagine the state as a very large database:

Simplified Ethereum state

| Address | Type     | Balance | Nonce |
| ------- | -------- | ------- | ----- |
| Alice   | EOA      | 5 ETH   | 7     |
| Bob     | EOA      | 2 ETH   | 3     |
| Counter | Contract | 0 ETH   | —     |

Illustrative data, not live account balances.

The real Ethereum state also includes contract code and storage.

Ethereum uses a data structure called the Merkle Patricia Trie to organise state and provide cryptographic commitments to it.

Each block header includes a `stateRoot`, which commits to the resulting global state after the block's transactions have been executed.

That gives us a powerful verification mechanism:

If two honest nodes execute the same valid block from the same previous state, they should produce the same state root.

![Ethereum’s Hidden Backbone: A Deep Dive Into Merkle Patricia Tries | HackerNoon](https://images.openai.com/static-rsc-4/l5DnKnbIVVqTI_6wMUwJVJCpgPqC6sfhHM7-4QeJawHAKwMD3rel8yIHkHT4iRgrrxf8Ab_Iwec4FF_i-REOObDYgyYRXZrTB6m1kuCJ4ImJTNy06Lk8qql_eujhMHHrkX3A4IQCUVof3vI6Yp-QiCfpWXy9429_gjQUFaM93Wl0_s3VuVg92RwEzxJoX96g?purpose=fullsize)

There are different roots associated with execution data:

* `stateRoot`: commitment to the resulting world state.

* `transactionsRoot`: commitment to the block's transactions.

* `receiptsRoot`: commitment to transaction receipts.

These commitments allow clients to verify data without treating the entire database as an unstructured collection of records.

### 8\. Transactions and Gas

Let's understand what happens when Alice sends ETH to Bob.

A transaction is a signed instruction requesting a state transition.

A typical EOA transaction contains fields such as:

| Field                | Purpose                                           |
| -------------------- | ------------------------------------------------- |
| nonce                | Sender's transaction sequence number              |
| to                   | Recipient address, or empty for contract creation |
| value                | ETH being transferred                             |
| data                 | Optional input data                               |
| gasLimit             | Maximum gas units the sender allows               |
| maxFeePerGas         | Maximum total fee per gas unit                    |
| maxPriorityFeePerGas | Maximum tip per gas unit                          |
| chainId              | Identifies the intended network                   |
| signature            | Authorizes the transaction                        |

Ethereum transactions use a sender's signature to authorize the request.

### What is gas?

Gas measures the computational and resource cost of executing an operation.

For example:

* Simple ETH transfer: typically 21,000 gas.

* Contract execution: varies according to operations.

* Persistent storage writes: can be relatively expensive.

The transaction fee is based on:

\\text{Fee} = \\text{Gas Used} \\times \\text{Effective Gas Price}

On Ethereum after EIP-1559, the effective gas price is generally composed of:

\\text{Base Fee} + \\text{Priority Fee}

The base fee is burned, while the priority fee goes to the block proposer.

Example:

Suppose:

* Gas used = 21,000.

* Effective gas price = 20 gwei.

Then:

21,000 \\times 20 = 420,000\\text{ gwei}

Since 1 ETH = gwei:

\\text{Fee} = 0.00042\\text{ ETH}

Gas prevents someone from consuming unlimited computation for free.

It also means smart contract developers must care about execution efficiency.

### 9\. Mempool: where transactions wait

Suppose Alice creates and signs a transaction.

Does it immediately become part of the blockchain?

No.

First, it usually enters a node's local transaction pool, commonly called the mempool.

![Guide du débutant sur les réseaux décentralisés : Comprendre les RPC, les validateurs et les Chain ID](https://images.openai.com/static-rsc-4/3DpcC0OiVuOV7zKdcELfOpsPX762e-6DQan9OZH3PILK1m9qJwCdUP0W3L9-M1npen7GhkWyGUjpO98QZgAGGcvBhEJa20mNFUWN1MkFTCN0yNEysOqkou37-swHgiAHzkrQLRhv4zkn6-fCXLAagf_o4xhWC5lH-kuVk7EQ1BCPJeyVj4lnj2_aqiGB7NJz?purpose=fullsize)

A simplified lifecycle:

* Alice signs a transaction.

* Her wallet submits it to an Ethereum node using JSON-RPC.

* The execution client checks basic validity and admission conditions.

* The node adds it to its local transaction pool.

* It announces the transaction to execution-layer peers.

* Other nodes receive and independently check it.

* A block proposer selects transactions.

* The execution client executes the selected transactions.

* The consensus client proposes the block.

* Other nodes verify the block and its execution.

* The chain progresses and the block eventually reaches finality.

A crucial detail: there is no single global mempool.

Each execution client maintains its own local transaction pool. Nodes may see different pending transactions depending on connectivity, timing, policies and capacity.

Also, transactions are not guaranteed to be included merely because they entered one node's mempool.

ethereum.org +1

### 10\. Where does libp2p fit into Ethereum?

This is probably the most interesting connection for our learning journey.

Ethereum actually has two different peer-to-peer networking stacks.

Ethereum networking architecture

Consensus Layer P2P

libp2p

* Block propagation.

* Validator attestations.

* GossipSub-based message propagation.

* Peer discovery using Discovery v5.

Execution Layer P2P

DevP2P

* Transaction propagation.

* Block and execution data exchange.

* Peer discovery.

* RLPx-based secure communication.

The two networks serve different purposes and have separate peer identities and networking protocols.

This is an important discovery:

Ethereum's consensus layer uses libp2p, while its execution layer uses DevP2P.

The consensus layer uses libp2p protocols for peer communication and gossip. The execution layer uses Ethereum's DevP2P stack, including RLPx and Ethereum wire protocols. ethereum.org +2

Think about the implications:

Your knowledge of:

* Peer discovery.

* Secure transport.

* GossipSub.

* Message propagation.

* Peer identity.

* Network reliability.

...is directly relevant to understanding Ethereum's consensus networking.

But there is an important distinction: libp2p handles the communication mechanisms. Ethereum's consensus implementation defines how those messages are interpreted and how validators reach agreement.

### 11\. Follow one transaction through the complete architecture

Let's put everything together.

Alice sends 1 ETH to Bob.

* Wallet

    Alice signs a transaction using her private key.

* Execution Client

    Receives the transaction through JSON-RPC, validates it and adds it to the local transaction pool.

* Execution P2P

    The transaction is propagated to other execution clients using DevP2P.

* Block proposer

    A validator is selected to propose a block. Its execution client prepares an execution payload.

* Consensus Client

    The validator's consensus client includes the execution payload in a beacon block and signs the proposal.

* Consensus P2P

    The block is propagated to consensus peers using libp2p.

* Other nodes

    Their consensus clients check the block and ask their execution clients to execute its payload.

* Finality

    Validators attest, fork choice selects the preferred chain, and checkpoints can become finalized.

Notice how many independent systems participate in what looks like a simple wallet transfer!

This is the real beauty of Ethereum architecture: cryptography, networking, virtual machines, databases and consensus all work together.

### 12\. Hands-on: inspect an Ethereum node using JSON-RPC

Let's make the architecture tangible.

You don't need to run a full Ethereum node for this exercise. You can use an Ethereum RPC endpoint supplied by a provider, or a local development node.

Ethereum's execution clients expose JSON-RPC methods.

For example, the following request asks a node for its current block number:

```bash

curl -X POST YOUR_ETHEREUM_RPC_URL \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "eth_blockNumber",
    "params": [],
    "id": 1
  }'
```

You should receive something similar to:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": "0x123456"
}
```

The result is hexadecimal.

Now try these methods:

| JSON-RPC method           | What it does                    |
| ------------------------- | ------------------------------- |
| eth_chainId               | Returns the network chain ID    |
| eth_blockNumber           | Returns the latest block number |
| eth_getBalance            | Reads an account's ETH balance  |
| eth_getBlockByNumber      | Retrieves a block               |
| eth_getTransactionByHash  | Retrieves transaction details   |
| eth_getTransactionReceipt | Retrieves a transaction receipt |

For example, to retrieve the latest block:

```bash

curl -X POST YOUR_ETHEREUM_RPC_URL \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "eth_getBlockByNumber",
    "params": ["latest", false],
    "id": 1
  }'
```

This is the same general interface that libraries such as `web3.py`, `ethers.js` and `viem` use to communicate with Ethereum execution clients.

For consensus-specific information, clients expose a separate Beacon API.

### 13\. What I want you to understand from this lesson

Let's summarise the complete architecture:

| Component        | Responsibility                                      |
| ---------------- | --------------------------------------------------- |
| EOA              | User-controlled account                             |
| Contract account | Stores code and contract state                      |
| EVM              | Executes smart contract bytecode                    |
| Execution client | Executes transactions and maintains execution state |
| Consensus client | Coordinates PoS and fork choice                     |
| Validator client | Proposes blocks and attests                         |
| Engine API       | Connects execution and consensus clients            |
| DevP2P           | Execution-layer networking                          |
| libp2p           | Consensus-layer networking                          |
| JSON-RPC         | Application interface to execution clients          |
| Beacon API       | Application interface to consensus clients          |

A particularly useful mental model:

* Networking moves messages.

* Cryptography authenticates and protects data.

* Execution determines what transactions do.

* Consensus determines which history is accepted.

* State represents the resulting system.

### 14\. Test your understanding

Lesson 4 quiz

0/5 answered

1. Which component executes smart contracts?

Consensus client

Execution client and its EVM

Validator client

2. What connects the execution client and consensus client?

Engine API

GossipSub

JSON-RPC only

3. Which networking stack does Ethereum's consensus layer use?

DevP2P

libp2p

HTTP only

4. What is Ethereum's mempool?

The permanent blockchain database

A local pool of pending transactions

The validator private-key store

5. What does the stateRoot represent?

The hash of the validator's private key

A cryptographic commitment to the resulting Ethereum state

The number of transactions in a block

Check answers

### 15\. Your assignments

I'd like you to do three things:

* Architecture exercise: Draw a diagram of an Ethereum node with its execution client, consensus client, Engine API, execution peers and consensus peers.

* Networking exercise: Explain in your own words why Ethereum uses libp2p for its consensus network but DevP2P for its execution network.

* RPC exercise: Query `eth_chainId`, `eth_blockNumber` and `eth_getBlockByNumber` using an RPC endpoint.

Don't worry about memorising all the API methods. Understanding which component is responsible for what is much more important.

### Next lesson: Lesson 5 — Smart Contracts and Solidity

We'll write our first smart contract and understand:

* Solidity fundamentals.

* Contract deployment.

* Functions, state variables and events.

* ABI and bytecode.

* Storage vs memory vs calldata.

* Contract calls vs transactions.

* How the EVM executes a contract.

We'll move from understanding Ethereum infrastructure to actually building something on Ethereum.
