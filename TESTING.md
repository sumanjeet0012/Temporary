# Testing the goose-mcp-libp2p MCP Server

This guide walks you through **every layer of testing** — from raw imports to
a full Goose AI session — so you can confirm the MCP server is working
correctly at each stage.

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python (via pyenv) | 3.12 (`uctest1` venv) |
| Goose CLI | ≥ 1.28.0 |
| Working directory | repo root (`goose-universal-connectivity/`) |

---

## 1. Activate the Environment

```bash
# From anywhere
cd /Users/sumanjeet/code/goose-universal-connectivity

# Activate the uctest1 venv
pyenv shell uctest1

# Confirm the right Python is active
python --version          # should print Python 3.12.x
which python              # should contain uctest1
```

---

## 2. Verify Dependencies Are Installed

```bash
# Check the key packages are present
python -c "import mcp; print('mcp ✅', mcp.__version__)"
python -c "import libp2p; print('libp2p ✅')"
python -c "import trio; print('trio ✅')"
python -c "import trio_asyncio; print('trio_asyncio ✅')"
python -c "import janus; print('janus ✅')"
```

If any package is missing, install from the mcp directory:

```bash
pip install -e mcp/
```

---

## 3. Run the Automated Smoke Test

This is the **fastest way** to confirm all 9 MCP tools work end-to-end:

```bash
# From repo root with uctest1 active
python mcp/test_mcp.py
```

### Expected output

```
============================================================
goose-mcp-libp2p  —  smoke test
============================================================

[1/9] Importing MCP module…
  ✅ Import OK

[2/9] start_peer(port=9100, nick='TestGoose')…
  → { "status": "started", "peer_id": "12D3Koo...", "multiaddr": "/ip4/..." }
  ✅ Peer started

[3/9] get_peer_info()…
  ✅ Peer info OK

[4/9] get_node_status()…
  ✅ Node status OK

[5/9] subscribe_topic('/goose/tasks')…
  ✅ Subscription requested

[6/9] publish_message('/goose/tasks', 'Hello from Goose!')…
  ✅ Message published

[7/9] get_messages('/goose/tasks')…
  ✅ get_messages() responded OK

[8/9] list_peers()…
  ✅ Connected to N peer(s)

[9/9] stop_peer()…
  ✅ Stop signal sent

============================================================
All tests passed! ✅
```

> **Note:** `get_messages` may return an empty list — GossipSub does not
> echo your own published messages back to you by design.

---

## 4. Test the MCP JSON-RPC Protocol Directly

This verifies that the server speaks the MCP protocol correctly, independent
of Goose.

### 4a. Initialize handshake

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}' \
  | python mcp/goose_libp2p_mcp.py
```

**Expected:** A JSON response containing `"result": { "protocolVersion": "2024-11-05", ... }`.

### 4b. List all registered tools

```bash
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}\n{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}\n' \
  | python mcp/goose_libp2p_mcp.py
```

**Expected:** A JSON response listing all 9 tools:

```
start_peer, stop_peer, get_peer_info, connect_peer,
publish_message, get_messages, list_peers, subscribe_topic, get_node_status
```

### 4c. Using the Goose MCP CLI helper

```bash
goose mcp goose-libp2p --stdio
```

Then paste these lines one at a time (press Enter after each):

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
```

Press `Ctrl+C` to exit.

---

## 5. Verify Goose Configuration

### 5a. Check the extension is registered

```bash
goose configure list
# or
cat ~/.config/goose/config.yaml | grep -A 10 "goose-libp2p"
```

You should see:

```yaml
extensions:
  goose-libp2p:
    name: goose-libp2p
    type: stdio
    enabled: true
    cmd: /Users/sumanjeet/.pyenv/versions/uctest1/bin/python
    args:
      - /Users/sumanjeet/code/goose-universal-connectivity/mcp/goose_libp2p_mcp.py
```

### 5b. Validate the profile YAML

```bash
python -c "import yaml; yaml.safe_load(open('mcp/goose_profile.yaml')); print('YAML valid ✅')"
```

---

## 6. Run a Goose AI Session

This is the **full end-to-end test**: Goose uses the MCP tools to operate a
real libp2p node.

### 6a. Interactive session

```bash
goose session --profile libp2p
```

Once the session starts, type natural language commands:

```
> Start a libp2p peer on port 9200 with the nickname GooseTest
> Show me the peer info
> What is the node status?
> Subscribe to the topic /goose/tasks
> Publish the message "Hello p2p world!" to /goose/tasks
> List all connected peers
> Stop the peer
```

### 6b. One-shot session from a file

```bash
goose run --profile libp2p --instructions mcp/demo_agent_a.md
```

This runs the pre-written demo script in `demo_agent_a.md` and exits when
complete.

### 6c. What to look for

| Step | Success indicator |
|---|---|
| Session starts | `[goose-libp2p] connected` in the Goose header |
| `start_peer` | Goose prints a peer ID like `12D3Koo...` |
| `get_node_status` | `"running": true` in the response |
| `publish_message` | `"status": "published"` |
| `list_peers` | At least 1 bootstrap peer listed |
| `stop_peer` | `"status": "stopped"` or `"stop_requested"` |

---

## 7. Two-Peer Connectivity Test

To test actual peer-to-peer messaging between two nodes:

```bash
# Terminal 1 — start peer A
python mcp/test_mcp.py   # note the multiaddr printed for peer A

# Terminal 2 — start peer B and connect to A
python - <<'EOF'
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath("mcp/goose_libp2p_mcp.py"))))
import importlib.util as ilu
spec = ilu.spec_from_file_location("m", "mcp/goose_libp2p_mcp.py")
m = ilu.module_from_spec(spec); spec.loader.exec_module(m)

print(m.start_peer(port=9101, nick="PeerB"))
time.sleep(2)

# Replace with the multiaddr printed by Terminal 1
PEER_A_ADDR = "/ip4/127.0.0.1/tcp/9100/p2p/12D3Koo..."
print(m.connect_peer(PEER_A_ADDR))
time.sleep(2)
print(m.subscribe_topic("/goose/tasks"))
time.sleep(1)
print(m.get_messages("/goose/tasks"))
EOF
```

---

## 8. Troubleshooting

### MCP server doesn't start

```bash
# Run directly to see raw errors
python mcp/goose_libp2p_mcp.py
```

### `ModuleNotFoundError: No module named 'headless'`

```bash
# Must be run from the repo root
cd /Users/sumanjeet/code/goose-universal-connectivity
python mcp/test_mcp.py
```

### `ModuleNotFoundError: No module named 'mcp'`

```bash
pyenv shell uctest1
pip install -e mcp/
```

### Port already in use

```bash
# Find and kill the process using port 9100
lsof -ti tcp:9100 | xargs kill -9
```

### Goose can't find the extension

```bash
# Verify the path in config matches the actual file
ls -la mcp/goose_libp2p_mcp.py
cat ~/.config/goose/config.yaml
```

### Goose session shows 0 tools

```bash
# Check the extension is enabled
grep -A 5 "goose-libp2p" ~/.config/goose/config.yaml
# enabled: true  <-- must be true
```

---

## 9. Quick Reference Checklist

```
[ ] pyenv shell uctest1
[ ] python -c "import mcp, libp2p, trio"   # deps OK
[ ] python mcp/test_mcp.py                 # all 9 tests pass
[ ] echo '{"jsonrpc":...}' | python mcp/goose_libp2p_mcp.py   # protocol OK
[ ] cat ~/.config/goose/config.yaml        # extension registered
[ ] goose session --profile libp2p         # AI session works
```

All six boxes checked = MCP server is fully operational. 🦆
