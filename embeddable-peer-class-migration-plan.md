# Embeddable `Peer` Class Migration Plan for `py-ipfs-lite`

## 1. Goal

The goal of this migration is to turn `py-ipfs-lite` from a primarily CLI-driven project into a reusable Python library that can be embedded inside other applications.

Currently, the project appears to place most orchestration logic inside `main.py`, with functions such as daemon startup, add, and get being directly tied to command-line execution. This works for a standalone tool, but it makes the project difficult to reuse from other applications such as GooseSwarm.

The proposed design introduces a first-class `Peer` object:

```python
peer = Peer(config)
await peer.bootstrap()
cid = await peer.add_file("example.txt")
data = await peer.get(cid)
await peer.close()
```

The CLI should become a thin wrapper around this object.

---

## 2. Current Problem

### 2.1 CLI Owns the Core Logic

In the current approach, the CLI likely performs several responsibilities at once:

- Parses command-line arguments.
- Loads configuration.
- Creates the libp2p host.
- Creates the routing/DHT layer.
- Creates the blockstore/datastore.
- Creates Bitswap or exchange logic.
- Creates DAG services.
- Performs `add`, `get`, and daemon behavior.
- Handles shutdown.

This makes `main.py` too important. Instead of being only an entrypoint, it becomes the place where the actual library behavior lives.

That is not ideal because application developers should not need to import from `main.py` or execute a subprocess to use `py-ipfs-lite`.

---

### 2.2 The Project Behaves Like a Binary, Not a Library

A CLI-first architecture typically supports this usage well:

```bash
py-ipfs-lite daemon
py-ipfs-lite add file.txt
py-ipfs-lite get <cid>
```

But embedded applications need this instead:

```python
peer = Peer(config)
await peer.bootstrap()
cid = await peer.add_file("file.txt")
await peer.close()
```

Without an embeddable `Peer` class, projects like GooseSwarm must use one of these weaker approaches:

1. Start `py-ipfs-lite` as a separate daemon process.
2. Shell out to the CLI.
3. Import unstable internal functions from `main.py`.
4. Duplicate setup logic for host, DHT, Bitswap, and DAG services.

All of these options create maintenance and reliability problems.

---

### 2.3 State Ownership Is Unclear

An IPFS-like peer has real runtime state:

- Peer identity.
- libp2p host.
- Listening addresses.
- Active connections.
- Routing table.
- Bootstrap state.
- Blockstore.
- Datastore.
- Bitswap exchange.
- DAG service.
- Lifecycle state.

If this state is created inside standalone functions such as `run_daemon`, `run_add`, or `run_get`, there is no single object that owns the state.

That creates questions such as:

- Who is responsible for closing the host?
- Who owns the DHT lifecycle?
- Is the blockstore reused across operations?
- Can multiple peers exist in one process?
- Can tests inject fake components?
- Can another application control peer startup and shutdown?

A `Peer` class solves this by making ownership explicit.

---

## 3. Target Architecture

The target architecture should separate the reusable core from the CLI.

```text
py-libp2p primitives
        ↓
py-ipfs-lite Peer
        ↓
CLI / GooseSwarm / tests / other applications
```

The CLI should no longer own the implementation. It should simply create a `Peer`, call the appropriate method, print the result, and exit.

---

## 4. Proposed New Project Structure

A recommended structure:

```text
py_ipfs_lite/
├── __init__.py
├── config.py
├── peer.py
├── cli.py
├── main.py
├── host.py
├── routing.py
├── blockstore.py
├── datastore.py
├── exchange.py
├── dag.py
├── files.py
├── errors.py
└── types.py

tests/
├── test_peer_lifecycle.py
├── test_peer_add_get.py
├── test_peer_file_api.py
├── test_cli_add.py
├── test_cli_get.py
└── test_cli_daemon.py
```

This structure can be introduced gradually. The project does not need to be fully reorganized in one large pull request.

---

## 5. File Responsibilities

### 5.1 `py_ipfs_lite/peer.py`

This is the main new file.

It should define the embeddable `Peer` class. The `Peer` class should be responsible for orchestrating existing components, not for implementing low-level networking or storage logic itself.

Responsibilities:

- Own one libp2p host.
- Own one routing system, such as KadDHT.
- Own one datastore or blockstore.
- Own one Bitswap/exchange client.
- Own one DAG service.
- Expose lifecycle methods.
- Expose data methods.
- Support dependency injection for advanced users and tests.

The file should include:

```python
class Peer:
    def __init__(
        self,
        config: Config,
        *,
        host=None,
        routing=None,
        datastore=None,
        blockstore=None,
        exchange=None,
        dag_service=None,
    ):
        ...
```

Suggested public methods:

```python
async def bootstrap(self) -> None:
    ...

async def close(self) -> None:
    ...

async def add(self, data: bytes):
    ...

async def get(self, cid):
    ...

async def remove(self, cid) -> None:
    ...

async def add_file(self, path: str):
    ...

async def get_file(self, cid, output_path: str) -> str:
    ...
```

Suggested internal helper methods:

```python
async def _create_host(self):
    ...

def _create_datastore(self):
    ...

def _create_blockstore(self):
    ...

async def _create_routing(self):
    ...

def _create_exchange(self):
    ...

def _create_dag_service(self):
    ...

async def _connect_bootstrap_peers(self) -> None:
    ...

def _ensure_started(self) -> None:
    ...
```

The `Peer` class should not parse CLI arguments and should not print to stdout.

---

### 5.2 `py_ipfs_lite/cli.py`

This file should contain CLI command handlers.

Responsibilities:

- Parse user intent from CLI arguments.
- Load configuration.
- Create a `Peer`.
- Call the relevant `Peer` method.
- Print results.
- Convert exceptions into user-friendly CLI errors.

Example CLI wrapper shape:

```python
async def run_add(args):
    config = load_config(args.config)
    peer = Peer(config)

    try:
        await peer.bootstrap()
        cid = await peer.add_file(args.path)
        print(cid)
    finally:
        await peer.close()
```

The CLI should not manually create the host, DHT, Bitswap client, or DAG service. That belongs in `Peer`.

---

### 5.3 `py_ipfs_lite/main.py`

This file should become a very small entrypoint.

Responsibilities:

- Invoke the CLI parser.
- Dispatch to command handlers.
- Handle top-level process exit.

Example:

```python
def main():
    from py_ipfs_lite.cli import main as cli_main
    cli_main()

if __name__ == "__main__":
    main()
```

`main.py` should not contain business logic.

---

### 5.4 `py_ipfs_lite/config.py`

This file should continue to define configuration structures.

The `Peer` constructor should accept a `Config` object rather than raw CLI arguments.

Suggested config responsibilities:

- Listen addresses.
- Bootstrap peers.
- Datastore path.
- Blockstore options.
- Identity/private key configuration.
- Routing mode.
- Exchange/Bitswap options.
- File chunking options, if applicable.

Example:

```python
@dataclass
class Config:
    listen_addrs: list[str]
    bootstrap_peers: list[str]
    datastore_path: str
    routing_mode: str = "dht"
    enable_bitswap: bool = True
```

---

### 5.5 `py_ipfs_lite/host.py`

Optional but useful.

Responsibilities:

- Build a libp2p host from config.
- Encapsulate host creation details.

Example:

```python
async def create_host(config: Config):
    ...
```

This keeps `peer.py` clean and avoids putting all construction logic directly in one file.

---

### 5.6 `py_ipfs_lite/routing.py`

Responsibilities:

- Create routing services such as KadDHT.
- Connect routing to the host.
- Provide routing bootstrap helpers.

Example:

```python
async def create_routing(host, config: Config):
    ...
```

---

### 5.7 `py_ipfs_lite/blockstore.py`

Responsibilities:

- Define or wrap the blockstore used by the peer.
- Provide in-memory and persistent implementations if needed.
- Expose simple block operations.

Expected operations:

```python
async def put_block(block):
    ...

async def get_block(cid):
    ...

async def delete_block(cid):
    ...

async def has_block(cid) -> bool:
    ...
```

---

### 5.8 `py_ipfs_lite/exchange.py`

Responsibilities:

- Construct and wrap Bitswap exchange behavior.
- Request blocks from the network.
- Provide blocks to other peers.
- Connect the exchange to the blockstore and host.

Example:

```python
def create_exchange(host, blockstore, routing, config: Config):
    ...
```

---

### 5.9 `py_ipfs_lite/dag.py`

Responsibilities:

- Implement DAG-level operations.
- Convert raw bytes/files into blocks.
- Resolve CIDs into data.
- Use the blockstore and exchange underneath.

Expected operations:

```python
async def add(data: bytes):
    ...

async def get(cid) -> bytes:
    ...

async def remove(cid) -> None:
    ...
```

The `Peer` should delegate to this service for actual DAG operations.

---

### 5.10 `py_ipfs_lite/files.py`

Optional helper file.

Responsibilities:

- File reading/writing helpers.
- Directory import/export behavior.
- Chunking helpers, if the project supports UnixFS-like behavior later.

Initially, `Peer.add_file()` and `Peer.get_file()` may directly read/write files. Later, this can move into `files.py`.

---

### 5.11 `py_ipfs_lite/errors.py`

Define project-specific exceptions.

Suggested exceptions:

```python
class PyIPFSLiteError(Exception):
    pass

class PeerNotStartedError(PyIPFSLiteError):
    pass

class PeerAlreadyStartedError(PyIPFSLiteError):
    pass

class BlockNotFoundError(PyIPFSLiteError):
    pass

class InvalidCIDError(PyIPFSLiteError):
    pass

class BootstrapError(PyIPFSLiteError):
    pass
```

This makes both library and CLI error handling cleaner.

---

## 6. Proposed `Peer` API

### 6.1 Constructor

```python
peer = Peer(config)
```

The constructor should store configuration and optional injected dependencies. It should avoid heavy network startup if possible.

Recommended behavior:

- Do lightweight validation.
- Store injected dependencies.
- Do not connect to the network yet.
- Do not start background services yet.

Actual startup should happen in `bootstrap()`.

---

### 6.2 `bootstrap()`

Starts the peer.

Responsibilities:

1. Create host if not provided.
2. Create datastore/blockstore if not provided.
3. Create routing if not provided.
4. Create exchange/Bitswap if not provided.
5. Create DAG service if not provided.
6. Start required services.
7. Connect to bootstrap peers.
8. Mark the peer as started.

Example usage:

```python
peer = Peer(config)
await peer.bootstrap()
```

---

### 6.3 `close()`

Stops the peer and releases resources.

Responsibilities:

- Stop Bitswap/exchange.
- Stop routing/DHT.
- Close datastore/blockstore if needed.
- Close libp2p host.
- Cancel background tasks.
- Mark the peer as stopped.

Example usage:

```python
await peer.close()
```

This method should be safe to call more than once if possible.

---

### 6.4 `add(data: bytes)`

Adds raw bytes to the local DAG/blockstore and returns a CID.

Example:

```python
cid = await peer.add(b"hello world")
```

Expected behavior:

- Ensure the peer has started.
- Create one or more blocks.
- Store blocks in the blockstore.
- Return the root CID.

---

### 6.5 `get(cid)`

Gets bytes for a CID.

Example:

```python
data = await peer.get(cid)
```

Expected behavior:

- Ensure the peer has started.
- Check the local blockstore first.
- If unavailable locally, request blocks through exchange/Bitswap.
- Reconstruct and return bytes.

---

### 6.6 `remove(cid)`

Removes local data for a CID.

Example:

```python
await peer.remove(cid)
```

Expected behavior:

- Ensure the peer has started.
- Remove local block data where possible.
- This should not imply deleting data from the network.

---

### 6.7 `add_file(path)`

Adds a file from disk and returns a CID.

Example:

```python
cid = await peer.add_file("./artifact.tar.gz")
```

Expected behavior:

- Read file bytes.
- Delegate to `add()`.
- Return root CID.

Later, this method can support streaming/chunking for large files.

---

### 6.8 `get_file(cid, output_path)`

Fetches data by CID and writes it to disk.

Example:

```python
await peer.get_file(cid, "./artifact.tar.gz")
```

Expected behavior:

- Delegate to `get()`.
- Write bytes to `output_path`.
- Return the output path.

---

## 7. Dependency Injection Design

The constructor should allow advanced users to provide pre-built components.

Example:

```python
peer = Peer(
    config,
    host=existing_host,
    routing=existing_routing,
    datastore=custom_datastore,
    blockstore=custom_blockstore,
)
```

This is important for:

- GooseSwarm integration.
- Unit tests.
- Integration tests with multiple peers.
- Custom storage backends.
- Applications that already own a libp2p host.

The rule should be:

> If the user provides a component, `Peer` uses it. If not, `Peer` creates a default component from `Config`.

---

## 8. Lifecycle Rules

The `Peer` class should have clear lifecycle rules.

### 8.1 Initial State

After construction:

```python
peer = Peer(config)
```

The peer exists but is not connected or ready.

### 8.2 Started State

After:

```python
await peer.bootstrap()
```

The peer is ready to add, get, and serve data.

### 8.3 Closed State

After:

```python
await peer.close()
```

The peer should release all owned resources.

### 8.4 Method Safety

Methods such as `add`, `get`, `remove`, `add_file`, and `get_file` should check that the peer is started.

If the peer is not started, raise:

```python
PeerNotStartedError
```

---

## 9. CLI Migration Plan

### 9.1 Before Migration

The CLI likely looks conceptually like this:

```python
async def run_add(args):
    config = load_config(args)
    host = await new_host(...)
    routing = KadDHT(host, ...)
    blockstore = create_blockstore(...)
    exchange = BitswapClient(...)
    dag = DAGService(...)
    cid = await dag.add_file(args.path)
    print(cid)
```

### 9.2 After Migration

The CLI should look like this:

```python
async def run_add(args):
    config = load_config(args.config)
    peer = Peer(config)

    try:
        await peer.bootstrap()
        cid = await peer.add_file(args.path)
        print(cid)
    finally:
        await peer.close()
```

For `get`:

```python
async def run_get(args):
    config = load_config(args.config)
    peer = Peer(config)

    try:
        await peer.bootstrap()
        await peer.get_file(args.cid, args.output)
    finally:
        await peer.close()
```

For `daemon`:

```python
async def run_daemon(args):
    config = load_config(args.config)
    peer = Peer(config)
    await peer.bootstrap()

    try:
        await wait_forever()
    finally:
        await peer.close()
```

---

## 10. Migration Steps

### Step 1: Create `peer.py`

Create `py_ipfs_lite/peer.py` and define a minimal `Peer` class.

Initial implementation can wrap existing logic without changing behavior.

Goal of this step:

- Introduce the class.
- Keep existing CLI working.
- Avoid large rewrites.

---

### Step 2: Move Host Creation into `Peer`

Find the code in `main.py` that creates the libp2p host.

Move it into:

```python
async def _create_host(self):
    ...
```

Then update CLI code to use:

```python
peer = Peer(config)
await peer.bootstrap()
```

---

### Step 3: Move Datastore and Blockstore Creation

Move datastore/blockstore setup from `main.py` into `Peer` or helper modules.

Suggested target:

```python
def _create_datastore(self):
    ...

def _create_blockstore(self):
    ...
```

---

### Step 4: Move Routing/DHT Creation

Move KadDHT or routing table setup into:

```python
async def _create_routing(self):
    ...
```

`Peer.bootstrap()` should call this automatically if routing was not injected.

---

### Step 5: Move Bitswap/Exchange Creation

Move Bitswap setup into:

```python
def _create_exchange(self):
    ...
```

This should connect the host, routing layer, and blockstore.

---

### Step 6: Move DAG Service Creation

Move DAG setup into:

```python
def _create_dag_service(self):
    ...
```

The DAG service should become the layer used by `Peer.add()` and `Peer.get()`.

---

### Step 7: Implement Public Data Methods

Add these methods:

```python
async def add(self, data: bytes):
    self._ensure_started()
    return await self.dag.add(data)

async def get(self, cid):
    self._ensure_started()
    return await self.dag.get(cid)

async def remove(self, cid):
    self._ensure_started()
    return await self.dag.remove(cid)
```

Then implement file methods:

```python
async def add_file(self, path: str):
    with open(path, "rb") as f:
        return await self.add(f.read())

async def get_file(self, cid, output_path: str):
    data = await self.get(cid)
    with open(output_path, "wb") as f:
        f.write(data)
    return output_path
```

---

### Step 8: Rewrite CLI Commands as Thin Wrappers

Update `run_add`, `run_get`, and `run_daemon` to use `Peer`.

The CLI should not directly construct host/routing/blockstore/exchange/DAG components anymore.

---

### Step 9: Add Tests

Add tests for:

- Peer construction.
- Peer bootstrap.
- Peer close.
- Add/get with in-memory components.
- File add/get.
- CLI commands calling `Peer` correctly.
- Multiple peers in the same process.

Suggested test names:

```text
test_peer_can_be_constructed_from_config
test_peer_bootstrap_initializes_missing_components
test_peer_close_is_idempotent
test_peer_add_get_roundtrip
test_peer_add_file_get_file_roundtrip
test_cli_add_uses_peer
test_cli_get_uses_peer
test_multiple_peers_can_run_in_same_process
```

---

### Step 10: Export `Peer` from Package

Update `py_ipfs_lite/__init__.py`:

```python
from py_ipfs_lite.peer import Peer
from py_ipfs_lite.config import Config

__all__ = ["Peer", "Config"]
```

This allows users to write:

```python
from py_ipfs_lite import Peer, Config
```

---

## 11. Recommended Pull Request Breakdown

To reduce risk, split the migration into small PRs.

### PR 1: Add `Peer` skeleton

- Add `peer.py`.
- Add `Peer.__init__`, `bootstrap`, and `close` skeletons.
- Add lifecycle tests.

### PR 2: Move construction logic

- Move host, blockstore, routing, exchange, and DAG creation into `Peer`.
- Keep CLI behavior unchanged.

### PR 3: Add data methods

- Implement `add`, `get`, `remove`, `add_file`, and `get_file`.
- Add unit tests.

### PR 4: Make CLI use `Peer`

- Rewrite CLI handlers as thin wrappers.
- Remove duplicated setup code from `main.py`.

### PR 5: Public package API

- Export `Peer` and `Config` from `__init__.py`.
- Add README examples.
- Add GooseSwarm integration example.

---

## 12. GooseSwarm Integration Example

After this migration, GooseSwarm should be able to embed `py-ipfs-lite` directly.

Example:

```python
from py_ipfs_lite import Peer, Config

class GooseSwarmNode:
    def __init__(self, config):
        self.ipfs = Peer(config.ipfs)

    async def start(self):
        await self.ipfs.bootstrap()

    async def publish_artifact(self, path: str):
        return await self.ipfs.add_file(path)

    async def fetch_artifact(self, cid, output_path: str):
        return await self.ipfs.get_file(cid, output_path)

    async def stop(self):
        await self.ipfs.close()
```

This is much cleaner than spawning a separate daemon process or shelling out to CLI commands.

---

## 13. Design Principles

### 13.1 CLI Should Be a Consumer

The CLI should consume the library API.

It should not own core behavior.

Correct direction:

```text
CLI → Peer → py-libp2p primitives
```

Avoid:

```text
main.py → everything
```

---

### 13.2 `Peer` Should Orchestrate, Not Reimplement

The `Peer` class should not duplicate low-level behavior already implemented elsewhere.

It should coordinate:

- host
- routing
- blockstore
- exchange
- DAG service

The class should be an orchestration boundary.

---

### 13.3 Constructor Should Be Lightweight

Avoid starting network services in `__init__`.

Prefer:

```python
peer = Peer(config)
await peer.bootstrap()
```

This makes lifecycle explicit and easier to test.

---

### 13.4 Support Dependency Injection

Allow callers to inject advanced components.

This makes the project more flexible and testable.

---

### 13.5 Keep Backward Compatibility Where Possible

Existing CLI commands should continue to work.

The user-facing CLI should not break just because internals are being reorganized.

---

## 14. Acceptance Criteria

This migration can be considered successful when:

- `py_ipfs_lite.peer.Peer` exists.
- `Peer` can be imported by external applications.
- `Peer` owns host, routing, blockstore, exchange, and DAG service.
- `Peer.bootstrap()` starts the necessary services.
- `Peer.close()` cleanly shuts them down.
- `Peer.add()` and `Peer.get()` work without using CLI functions.
- `Peer.add_file()` and `Peer.get_file()` work from library code.
- CLI commands internally use `Peer`.
- Core setup logic is no longer duplicated across `run_daemon`, `run_add`, and `run_get`.
- Tests can instantiate `Peer` with fake or in-memory components.
- GooseSwarm or another application can embed `py-ipfs-lite` without spawning a subprocess.

---

## 15. Final Target Usage

Library usage:

```python
from py_ipfs_lite import Peer, Config

config = Config(...)
peer = Peer(config)

try:
    await peer.bootstrap()
    cid = await peer.add_file("artifact.tar.gz")
    print(cid)
finally:
    await peer.close()
```

CLI usage remains simple:

```bash
py-ipfs-lite add artifact.tar.gz
py-ipfs-lite get <cid> --output artifact.tar.gz
py-ipfs-lite daemon
```

The important difference is that both the CLI and external applications now rely on the same reusable `Peer` abstraction.

---

## 16. Summary

The current project structure is CLI-centered. That makes `py-ipfs-lite` useful as a command-line tool, but difficult to embed inside larger applications.

The proposed `Peer` class turns the project into a proper library. It gives one object clear ownership of networking, routing, storage, exchange, and DAG services. It also gives applications a clean lifecycle:

```python
peer = Peer(config)
await peer.bootstrap()
# use peer
await peer.close()
```

This design is more appropriate because it reflects how an IPFS-like node actually behaves: it is a long-lived, stateful peer with explicit startup, data operations, and shutdown.

Once this migration is complete, the CLI becomes simpler, tests become easier, and projects like GooseSwarm can embed `py-ipfs-lite` directly.
