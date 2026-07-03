# Migration Walkthrough: py-multiaddr >= 0.2.0 and AnyIO v4

The `py-libp2p-daemon-bindings` project has been successfully migrated to use the latest `py-multiaddr` and fully upgraded to `anyio` v4 compatibility. All integration tests are now passing with the updated `go-libp2p-daemon` binary.

## What Was Changed

### 1. Daemon Binary Upgrade
- Updated `scripts/install_p2pd.sh` to install `go-libp2p-daemon` version `v0.9.2` since older versions are incompatible with modern Go toolchains.

### 2. Multiaddr Dependency Update
- Migrated the setup configurations to depend on `py-multiaddr>=0.2.0`.
- Adjusted the test variables to account for stricter CID validation in the new `py-multiaddr`. 

### 3. AnyIO v4 Upgrades
Migrated deprecated or removed APIs to the latest `anyio` standards:
- **Events**: Replaced asynchronous `anyio.create_event()` with synchronous `anyio.Event()`. Removed `await event.set()` which caused a `TypeError` inside stream handler task groups since `Event.set()` is no longer an async method.
- **Streams**: Updated all stream termination calls from `stream.close()` to `stream.aclose()`. Replaced deprecated `receive_some` with `receive`.
- **Listeners**: Updated `p2pclient/control.py` to correctly map `anyio.create_tcp_listener` and `create_unix_listener` bindings directly to `anyio.abc.SocketListener`.

### 4. DHT Daemon Configurations
- Since the updated `go-libp2p-daemon` behaves strictly as a DHT client out of the box when operating on localhost networks, we configured `p2pclient/daemon.py` to use the `-dhtServer=true` flag. This ensures DHT tests (`dht_search_value`, `dht_provide`, `dht_find_peer`) properly add peers to their routing tables and perform queries successfully on the local integration test mesh.

## Validation Results

- The complete `pytest` suite has successfully completed.
- Zero deadlocks or stalls due to correct internal error boundary handling for listeners and `anyio.fail_after()` timeout synchronization.
- Resolved issue [#1356](https://github.com/libp2p/py-libp2p/issues/1356).

> [!TIP]
> The deprecated DHT feature `FindPeersConnectedToPeer` is no longer supported by modern `go-libp2p-daemon` and was appropriately marked as skipped in the test suite to prevent unsupported exceptions.
