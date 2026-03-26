# 🦆 Goose libp2p MCP — The Complete Developer Guide

This guide breaks down the architecture, folder structure, dependencies, and code so you can understand exactly how everything fits together.

---

## 1. High-Level Concept: What is this?

**Analogy:** 
Imagine **Goose AI** is a manager who wants to send messages to branches in different cities, but Goose does not know how to operate the radio equipment.

The **libp2p Network** is the radio network (a peer-to-peer mesh) where all the other cities are listening and talking. 

Our **MCP Server (`goose_libp2p_mcp.py`)** is the *Radio Operator*. It speaks English to the Manager (via JSON-RPC MCP Protocol) and translates those requests into radio dial turns and button presses (Python libp2p network calls).

The MCP server exposes **Tools** (like `start_peer`, `publish_message`) to Goose. When Goose wants to do something, it calls these tools, and the MCP server executes the heavy lifting on the peer-to-peer network.

---

## 2. Folder Structure

Let us look at the `mcp/` folder and what each piece does:

*   **`pyproject.toml`**: The recipe book. Tells Python what dependencies we need.
*   **`README.md`**: The quick-start guide.
*   **`TESTING.md`**: The detailed QA manual (how to run all the tests).
*   **`goose_profile.yaml`**: The ID badge for Goose. Tells Goose *how* to start the MCP server.
*   **`goose_libp2p_mcp.py`**: The actual "Radio Operator" (The MCP Server code).
*   **`test_mcp.py`**: A pure Python script to test the radio before handing it to the Manager (Goose AI).
*   **`__pycache__/`**: Python compiled byte-code (ignore this).

---

## 3. Dependencies (`pyproject.toml`)

Here is exactly **what** the dependencies are and **why** we need them.

### A. The Brains
*   **`mcp[cli]>=1.6.0`**: The Model Context Protocol framework. **Why?** It translates Python functions into LLM tools automatically. It provides the `FastMCP` class.
*   **`libp2p` (Custom Fork)**: The core peer-to-peer networking stack. **Why?** It is the engine that handles connecting to peers, traversing NATs, and GossipSub routing.

### B. The Async Translators (The Kitchen Analogy)
libp2p is *strictly asynchronous* (an event loop kitchen). But FastMCP tool calls are *synchronous* (a waiter taking orders). 

*   **`trio`**: An async concurrency library. **Why?** Our version of `libp2p` was built specifically for the Trio event loop (not standard `asyncio`). It is the "kitchen".
*   **`trio_asyncio`**: A bridge between standard `asyncio` and `trio`. **Why?** Some internal Python tools expect `asyncio`. This*   **`trio_asyncio`**: A bridge between standard `asyncio` andqueue. **Why?** This is the literal *ticket window* between the Waiter (MCP Thread) and the Kitchen (libp2p Trio Thread). It allows safe communication across different threads without crashing.

### C. The Data Mechanics
*   **`base58`**: **Why?** libp2p Peer IDs are hashed representations of public keys encoded in Base58 (e.g., `12D3KooW...`). We need this to read and write Peer IDs.
*   **`protobuf`**: **Why?** Under the hood, libp2p nodes send messages to each other using Protocol Buffers (a highly compressed binary format).
*   **`multiaddr`**: **Why?** In p2p, IP addresses are not enough. We need to know the IP, Protocol, and Peer ID (e.g., `/ip4/127.0.0.1/tcp/9100/p2p/12D...`). `multiaddr` parses these complex network addresses.

---

## 4. Deep Dive: `goose_libp2p_mcp.py`

This is the most important file. Let us break down its architecture layer by layer.

### A. The Setup and `sys.path` Hack
```python
_MCP_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_MCP_DIR)
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)
```
**Why?** The MCP server lives in `mcp/`, but relies on `headless.py` and folders in the root directory (`goose-universal-connectivity/`). This tricks Python into looking in the parent directory for imports, so `from headless import HeadlessService` works seamlessly!

### B. The FastMCP Server Instance
```python
mcp = FastMCP("goose-libp2p", instructions="...")
```
When Goose connects, FastMCP reads all functions decorated with `@mcp.tool()` and tells Goose that they are available.

### C. The Background### C. The Background### C. The Background### C. The Background### C. The Background### C. The Background### C. The Background### C. The Background### C. The Background### C. Trea##
```python
def _run_service_in_thread(nickndef _run_service_in_thread(nickndef _run_service_in_thread(nickndef _run_service_irvice
    _service = HeadlessService(nickname, port, connect_addrs)
    _service.run() # Blocks forever while the network is alive
```

### D.### D.### D.### D.### D.#icket Window")
When Goose calls a tool on tWhen Goose calls a tool on tWhen Goose calls a tool on tWhen Goose calls a tool on tWhen Goose calls a tool on tWhen Goose calls a tool on tWhen Goose calls a tool on tWhen Goose calls a tool on tWhen Goose calls a tool on tWhen Goose calls a tool on tWhen Got: `action: publish`).
2.  **Main thread** s2.  **Mae ticket to the Kitchen (Trio thread) via `_service.2.quest_queue.sync_q.put(req)`.
3.  **Main thread** waits at the pickup window for the Network to finish processing it.
4.  **Main thread** gets the response and hands it back to Goose as JSON.

This pattern ensures that no matter how rapidly Goose spams tools, it will never cause threading errors or race conditions in the peer-to-peer network stack.

---

## 5. Deep Dive: `test_mcp.py`

When building an MCP, testing by opening Goose every time is too slow. `test_mcp.py` is our simulation of Goose.

**How it works**How it works**How it works**How it works**How it works**HowP JSON-RPC server over stdio, `test_mcp.py` dynamically loads `goose_libp2p_mcp.py` as a raw Python module using `importlib.util`.
2.  **Mocking the AI**: It directly calls the underlying Python functions (`start_peer()`, `publish_message()`) exactly as the FastMCP router would, completely bypassing the JSON-RPC layer.
3.  **The Flow**:
    *   It starts a peer on port 9100.
    *   Verifies the `peer_info` and `node_status`.
    *   Subscribes to `/goose/tasks` and publishes a message (testing the Queue system).
    *   Checks `get_messages` and finally calls `stop_peer()` to ensure threads clean up.

**Analogy:** 
If the MCP server is a car, Goose is the driver using the steering wheel (JSON-RPC). `test_mcp.py` is a mechanic in the garage testing the engine directly by hot-wiring the starteIf the MCP server is a car, GI universal p2p connectivity without any centralized servers!
