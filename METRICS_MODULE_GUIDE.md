# py-libp2p Metrics Module — From Basics to Advanced

A complete guide to the metrics implementation in py-libp2p (`libp2p/metrics/`),
covering the architecture, every metric each module exposes, the data flow end
to end, and how to extend the system.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture — how data flows](#2-architecture--how-data-flows)
3. [Quick start](#3-quick-start)
4. [The core: `Metrics` class](#4-the-core-metrics-class)
5. [The bridge: `MetricsListener`](#5-the-bridge-metricslistener)
6. [Per-module metrics reference](#6-per-module-metrics-reference)
   - [6.1 Ping](#61-ping)
   - [6.2 Gossipsub](#62-gossipsub)
   - [6.3 Kad-DHT](#63-kad-dht)
   - [6.4 Swarm](#64-swarm)
   - [6.5 Bitswap](#65-bitswap)
   - [6.6 Discovery](#66-discovery)
7. [The legacy channel-based consumer](#7-the-legacy-channel-based-consumer)
8. [The observability stack: Prometheus + Grafana](#8-the-observability-stack-prometheus--grafana)
9. [Tests](#9-tests)
10. [Comparison with go-libp2p / rust-libp2p](#10-comparison-with-go-libp2p--rust-libp2p)
11. [Advanced: adding metrics for a new module](#11-advanced-adding-metrics-for-a-new-module)
12. [FAQ and gotchas](#12-faq-and-gotchas)

---

## 1. Overview

The metrics module turns *observable events* emitted by every libp2p module into
[Prometheus](https://prometheus.io/) metrics that can be scraped over HTTP and
visualised in dashboards (Grafana).

**What it is:**

| File | Purpose |
|---|---|
| `libp2p/metrics/metrics.py` | The central `Metrics` aggregate + HTTP server + legacy channel consumer |
| `libp2p/metrics/listener.py` | `MetricsListener` — the event-bus listener that fans out events to collectors |
| `libp2p/metrics/ping.py` | Ping RTT / failure collectors |
| `libp2p/metrics/gossipsub.py` | Gossipsub publish/receive/control/subscription collectors |
| `libp2p/metrics/kad_dht.py` | Kademlia DHT inbound/outbound/operational collectors |
| `libp2p/metrics/swarm.py` | Swarm connection/dial collectors (`SwarmEvent` + `SwarmMetrics`) |
| `libp2p/metrics/bitswap.py` | Bitswap wantlist/block/message/session/provider-query collectors |
| `libp2p/metrics/discovery.py` | Peer discovery (mDNS, bootstrap, random walk) collectors |
| `libp2p/metrics/prometheus.yml` | Sample Prometheus scrape config |
| `examples/metrics/` | Runnable multi-node demo with Prometheus + Grafana docker-compose |

**Which modules emit events (and therefore have metrics):**

- **Ping protocol** — `libp2p/host/ping.py` emits `PingEvent`
- **Pubsub / Gossipsub** — `libp2p/pubsub/pubsub.py` emits `GossipsubEvent`
- **Kademlia DHT** — `libp2p/kad_dht/` (`kad_dht.py`, `peer_routing.py`, `provider_store.py`, `value_store.py`) emits `KadDhtEvent`
- **Swarm (connection layer)** — `libp2p/network/swarm.py` emits `SwarmEvent`
- **Bitswap** — `libp2p/bitswap/` (`client.py`, `session.py`, `message_queue.py`, `provider_query.py`) emits `BitswapEvent`
- **Discovery** — `libp2p/discovery/` (`mdns/listener.py`, `bootstrap/bootstrap.py`, `random_walk/random_walk.py`) emits `DiscoveryEvent`

---

## 2. Architecture — how data flows

```
            ┌─────────────────────────────────────────────────────────┐
            │                    libp2p modules                       │
            │  ping · gossipsub · kad-dht · swarm · bitswap · disc.  │
            └──────────────────────┬──────────────────────────────────┘
                                   │ 1. build event object (e.g. KadDhtEvent)
                                   │ 2. host.get_event_bus().emit(event)
                                   ▼
                         ┌───────────────────┐
                         │     EventBus      │   (libp2p/events/bus.py)
                         └─────────┬─────────┘
                                   │ 3. notify all registered listeners
                                   ▼
                        ┌─────────────────────┐
                        │   MetricsListener   │   (libp2p/metrics/listener.py)
                        │  handle_event()     │
                        └─────────┬───────────┘
                                   │ 4. pattern-match event type
                                   ▼
         ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌─────────┐  ┌────────┐  ┌─────────┐
         │ PingM.  │  │ GossipM. │  │ KadM.   │  │ SwarmM. │  │ BitswM.│  │ DiscovM.│
         └────┬────┘  └────┬─────┘  └────┬────┘  └────┬────┘  └───┬────┘  └────┬────┘
              │            │             │            │           │            │
              └────────────┴─────────────┴────────────┴───────────┴────────────┘
                                  │ 5. record() → prometheus counters/
                                  │    histograms/gauges (default registry)
                                  ▼
                        ┌──────────────────────┐
                        │   /metrics endpoint  │   start_http_server(port)
                        ▼
                   Prometheus scrapes →  Grafana dashboards
```

**The flow step by step:**

1. **Emit**: Every module publishes an event object on the host's shared event
   bus after a relevant operation. E.g. after an iterative DHT lookup,
   `peer_routing.py::_emit_lookup_event` sets `KadDhtEvent().lookup = True`
   plus `duration_ms`, `peers_queried`, `peers_found`, `success` and calls
   `self.host.get_event_bus().emit(event)`.
2. **Fan out**: `EventBus.emit()` (in `libp2p/events/bus.py`) synchronously
   calls `handle_event(event)` on every registered listener.
3. **Match**: `MetricsListener.handle_event()` pattern-matches the concrete
   event type and dispatches to the matching module collector.
4. **Record**: Each collector's `record(event)` translates boolean flags on the
   event into `Counter.inc()`, `Histogram.observe()` or `Gauge.set()` calls
   against the **default prometheus_client registry**.
5. **Scrape**: `Metrics.start_http_server()` serves `/metrics` over HTTP on a
   chosen port; Prometheus scrapes it; Grafana queries Prometheus.

> Events are plain Python objects carrying **boolean flags** (which occurrence
> this is, one event per occurrence) and **payload fields** (durations, counts,
> sizes). This "flag + payload" design keeps each event object small and lets
> the collector `record()` dispatch without parsing domain data.

---

## 3. Quick start

Four lines in your host setup:

```python
from libp2p.metrics.metrics import Metrics

metrics = Metrics()
metrics.attach(host.get_event_bus())   # start recording bus events
port = metrics.start_http_server()     # prometheus endpoint
print(f"Metrics: http://localhost:{port}/metrics")
```

Then point Prometheus at `http://localhost:8000` (or the returned port):

```yaml
scrape_configs:
  - job_name: "libp2p-python"
    static_configs:
      - targets: ["localhost:8000"]
```

(Ready-made file: `libp2p/metrics/prometheus.yml`; full demo with two nodes,
Prometheus and Grafana: `examples/metrics/` — run `metrics-demo` in two
terminals, `docker compose up`, then `ping`, `join`/`publish`, `put`/`get`.)

---

## 4. The core: `Metrics` class

`libp2p/metrics/metrics.py`

### 4.1 Attributes

`Metrics` is an aggregate of every module collector, exposed as attributes:

| Attribute | Type | Class (file) |
|---|---|---|
| `metrics.ping` | `PingMetrics` | `libp2p/metrics/ping.py` |
| `metrics.gossipsub` | `GossipsubMetrics` | `libp2p/metrics/gossipsub.py` |
| `metrics.kad_dht` | `KadDhtMetrics` | `libp2p/metrics/kad_dht.py` |
| `metrics.swarm` | `SwarmMetrics` | `libp2p/metrics/swarm.py` |
| `metrics.bitswap` | `BitswapMetrics` | `libp2p/metrics/bitswap.py` |
| `metrics.discovery` | `DiscoveryMetrics` | `libp2p/metrics/discovery.py` |

Constructing `Metrics()` instantiates all six collectors, which register their
Prometheus metrics immediately (on module import / first `Metrics()` use) into
the **default registry** of `prometheus_client`.

### 4.2 `attach(event_bus) -> Metrics`

Registers a `MetricsListener` on the event bus. From this point on every
emitted event (DHT lookups, Bitswap block transfers, discovery events, pubsub
messages, ping RTTs, swarm dials) is recorded. Returns `self` for chaining:

```python
metrics = Metrics()
metrics.attach(host.get_event_bus())
metrics.start_http_server()
```

### 4.3 `start_http_server(port=None) -> int`

- Finds a free port starting at 8000 via `find_available_port()`.
- `start_http_server(port)` from `prometheus_client` serves the default
  registry on `GET /metrics`.
- Returns the actual port used.
- Uses the *listener* path (event consumption is done by `attach`).

### 4.4 `find_available_port(start_port=8000, host="127.0.0.1") -> int`

Pure utility: binds a socket to `(host, port)`, returns the first port that
binds successfully, incremented on `OSError` (port in use).

### 4.5 Legacy: `start_prometheus_server(metric_recv_channel)` (async)

The older, channel-based consumer (still present for back-compat):

```python
metrics = Metrics()
port = metrics.start_http_server()
# ... run node ...
# elsewhere in the node: a trio channel delivers events to this coroutine
await metrics.start_prometheus_server(recv_channel)
```

It picks three ports (metrics on 8000, prometheus UI on 9000, grafana on 7000),
starts the HTTP server, prints instructions for `docker compose up`, and then
loops `await recv_channel.receive()` forever, dispatching **only four** event
types via `match`:

```python
case PingEvent():      self.ping.record(event)
case GossipsubEvent(): self.gossipsub.record(event)
case KadDhtEvent():    self.kad_dht.record(event)
case SwarmEvent():     self.swarm.record(event)
```

> Note the difference: the legacy path covers only ping/gossipsub/kad/swarm
> (bitswap & discovery were added later), while the listener path
> (`MetricsListener`) covers all six. Prefer `attach() + start_http_server()`.

Any `record()` exception is swallowed (`logger.debug(..., exc_info=True)`) so a
misbehaving event can never kill the node.

---

## 5. The bridge: `MetricsListener`

`libp2p/metrics/listener.py`

Implements `IEventListener` from `libp2p/events` (the `INotifee`-style event
bus). It is deliberately **fast and non-blocking** (pure counter/histogram
increments, no I/O) so it is safe on any host's event bus.

```python
class MetricsListener(IEventListener):
    def __init__(self, metrics: Metrics | None = None):
        self.metrics = metrics if metrics is not None else Metrics()

    def handle_event(self, event: Any) -> None:
        match event:
            case PingEvent():  self.metrics.ping.record(event)
            case GossipsubEvent(): self.metrics.gossipsub.record(event)
            case KadDhtEvent(): self.metrics.kad_dht.record(event)
            case SwarmEvent():  self.metrics.swarm.record(event)
            case BitswapEvent(): self.metrics.bitswap.record(event)
            case DiscoveryEvent(): self.metrics.discovery.record(event)
```

You can build it standalone and register it manually:

```python
host.get_event_bus().register_listener(MetricsListener(metrics))
```

or equivalently via `Metrics.attach()`. Matching is by class — unknown event
types are ignored.

---

## 6. Per-module metrics reference

Common conventions used below:

- **Type**: Counter (monotonic total), Histogram (distribution of observed
  values), Gauge (instantaneous value).
- **Labels**: Prometheus label dimensions, e.g. `peer_id` breaks a counter per
  peer. Cardinality warning: high-cardinality labels (full peer IDs) can bloat
  the metric — see [FAQ](#12-faq-and-gotchas).
- **Buckets**: histogram bucket boundaries in the listed unit.
- **Where events come from**: the emit sites in the module code.
- **What to alert on / dashboard ideas** per module.

### 6.1 Ping

File: `libp2p/metrics/ping.py` — event: `PingEvent` (`libp2p/host/ping.py:37`)
Emit site: `host/ping.py` around line 237–249 (after each ping round-trips).
`PingEvent` carries `peer_id`, `rtts: list[int] | None`, `failure_error`.

| Metric name | Type | Labels | Buckets (ms) | Description |
|---|---|---|---|---|
| `ping` | Histogram | — | 1, 5, 10, 25, 50, 100, 200, 500, 1000 | RTT per ping/pong, ms (mirrors go-libp2p buckets) |
| `ping_failure` | Counter | `reason` (exception class name) | — | Ping send/receive failures |

`record()` logic:

- `rtts` present + no failure → observe **every** RTT in the list
  (`PingEvent` can batch multiple RTTs from one ping round).
- `rtts=None` + `failure_error` → increment failure counter labelled with
  `type(err).__name__` (e.g. `TooSlowError`, `StreamReset`).
- Anything else → `ValueError` (invalid state; caught by the listener-level
  try/except in the legacy consumer).

**Reads as**: latency health of the network. Use the histogram's 95th/99th
percentile for p99 alerting, and `ping_failure` for liveness.

---

### 6.2 Gossipsub

File: `libp2p/metrics/gossipsub.py`
Event: `GossipsubEvent` (`libp2p/pubsub/pubsub.py:311`)
Emit sites: `pubsub.py` lines ~577, 1285, 1323, 1482
(`_on_message` inbound publish, outbound publish, subscription change, control
message handling). Fields: `peer_id`, `publish`, `subopts`, `control`,
`message_size`, `publish_out`, `subscription_change`, `topic`, `action`,
`peers_sent`.

| Metric name | Type | Labels | Buckets | Description |
|---|---|---|---|---|
| `gossipsub_received_total` | Counter | `peer_id` | — | Messages successfully received (inbound) |
| `gossipsub_publish_total` | Counter | `peer_id` | — | Received messages that are publishes |
| `gossipsub_subopts_total` | Counter | `peer_id` | — | Received messages notifying peer subscription changes |
| `gossipsub_control_total` | Counter | `peer_id` | — | Received control messages |
| `gossipsub_message_bytes` | Histogram | — | 64, 128, 256, 512, 1024, 2048, 4096 | Inbound message size in bytes |
| `gossipsub_publish_out_total` | Counter | `peer_id` | — | Messages published **by this node** |
| `gossipsub_publish_out_bytes` | Histogram | — | 64, 128, 256, 512, 1024, 2048, 4096 | Size of locally published messages |
| `gossipsub_subscription_changes_total` | Counter | `action` | — | Local subscription changes (subscribe/unsubscribe) |

`record()` fan-out logic:

1. `publish_out` → increment `publish_out_total` (labelled peer) and observe
   `publish_out_bytes` if `message_size` set; return early.
2. `subscription_change` → increment `subscription_changes_total` with
   `action` label; return early.
3. Otherwise (inbound): always increment `received_total`; then independently
   increment `publish_total` / `subopts_total` / `control_total` per flag; and
   observe `message_bytes` if a size is present.

A single inbound gossip message counts **once** in `received_total` and **once
per matching sub-type** — so `received_total` ≈ sum of the three sub-counters.

**Reads as**: pubsub traffic per peer, message size distribution (payload
efficiency), local fan-out health (publish_out), mesh topology churn via
subscription changes.

---

### 6.3 Kad-DHT

File: `libp2p/metrics/kad_dht.py`
Event: `KadDhtEvent` (`libp2p/kad_dht/events.py:9`)
Emit sites across `libp2p/kad_dht/`:

| Site | Event flag | What happened |
|---|---|---|
| `kad_dht.py:648` (stream handler) | `inbound` + one of `find_node`/`get_value`/`put_value`/`get_providers`/`add_provider` | Server handled an inbound RPC (per message type, lines 699/787/886/970/1093) |
| `kad_dht.py:409` (maintenance loop) | `routing_table` + `count` | Periodic routing-table size snapshot (gauge) |
| `kad_dht.py:779` | `rate_limited` | Inbound request rejected by rate limiter |
| `kad_dht.py:1230` | `stream_reset` | Stream reset for protocol violation |
| `kad_dht.py:1286` | `refresh` | Routing table refresh cycle |
| `kad_dht.py:1378` | `put_value_out` | Value stored at peers (peers_stored, success) |
| `kad_dht.py:1652/1663` | `get_value_out` | Value retrieve result (value_found, success) |
| `peer_routing.py:85` (find_peer) | `find_peer` | Peer lookup (success) |
| `peer_routing.py:385` (lookup) | `lookup` | Iterative lookup finished: duration_ms, peers_queried, peers_found, success |
| `provider_store.py:216` | `provide` | Content advertised to peers (peers_announced, success) |
| `provider_store.py:291` | `republish` (type=provider) | Provider record republished (count) |
| `provider_store.py:400/489` | `find_providers` | Provider lookup (providers_found, success) |
| `value_store.py:272` | `republish` (type=value) | Value record republished (count) |

**Inbound (server-side) counters** — labels `peer_id`:

| Metric name | Description |
|---|---|
| `kad_inbound_total` | All inbound DHT requests |
| `kad_inbound_find_node` | Inbound FIND_NODE requests |
| `kad_inbound_get_value` | Inbound GET_VALUE requests |
| `kad_inbound_put_value` | Inbound PUT_VALUE requests |
| `kad_inbound_get_providers` | Inbound GET_PROVIDERS requests |
| `kad_inbound_add_provider` | Inbound ADD_PROVIDER requests |

**Outbound / operational** — `result` label is `success`/`failure`:

| Metric name | Type | Labels | Buckets | Description |
|---|---|---|---|---|
| `kad_lookup_total` | Counter | `result` | — | Iterative peer lookups performed |
| `kad_lookup_duration_ms` | Histogram | — | 10, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000 | Lookup duration ms |
| `kad_lookup_peers_queried` | Histogram | — | 1, 2, 5, 10, 20, 50, 100 | Peers queried per lookup |
| `kad_lookup_peers_found` | Histogram | — | 1, 2, 5, 10, 20, 50, 100 | Peers found per lookup |
| `kad_provide_total` | Counter | `result` | — | Content provide announcements |
| `kad_provide_peers_announced` | Histogram | — | 1, 2, 5, 10, 20, 50 | Peers announced to per provide |
| `kad_find_providers_total` | Counter | `result` | — | Provider lookups |
| `kad_find_providers_found` | Histogram | — | 1, 2, 5, 10, 20, 50 | Providers found per lookup |
| `kad_put_value_total` | Counter | `result` | — | Outbound value store ops |
| `kad_get_value_total` | Counter | `result` | — | Outbound value retrieve ops |
| `kad_find_peer_total` | Counter | `result` | — | Peer lookup ops |
| `kad_refresh_total` | Counter | `result` | — | Routing table refresh cycles |
| `kad_republish_total` | Counter | `type` (provider/value), `result` | — | Record republish ops |

**Defensive / health:**

| Metric name | Type | Description |
|---|---|---|
| `kad_rate_limited_total` | Counter | Inbound requests rejected by rate limiting |
| `kad_stream_reset_total` | Counter | DHT streams reset (protocol violations) |
| `kad_routing_table_peers` | Gauge | Peers currently in the routing table (set from maintenance loop) |

**Reads as**: DHT service traffic per operation type, lookup latency &
efficiency (queried vs found), content availability (provide/find_providers),
churn (`routing_table_peers` downward trend = connectivity problems),
misbehaving peers (`rate_limited`, `stream_reset`).

---

### 6.4 Swarm

File: `libp2p/metrics/swarm.py`
Event: `SwarmEvent` (defined in the same file, flags `conn_incoming`,
`conn_incoming_error`, `dial_attempt`, `dial_attempt_error`; `peer_id`).
Emit sites: `libp2p/network/swarm.py` lines 691/694 (dial attempt + failure),
887/890 (incoming conn error), 1721–1819 (incoming connection notifications and
failure paths).

| Metric name | Type | Labels | Description |
|---|---|---|---|
| `swarm_incoming_conn` | Counter | `peer_id` | Incoming connection received by libp2p-swarm |
| `swarm_incoming_conn_error` | Counter | `peer_id` | Incoming connection failure |
| `swarm_dial_attempt` | Counter | `peer_id` | Dial attempts made |
| `swarm_dial_attempt_error` | Counter | `peer_id` | Outgoing connection failure |

`record()` increments each counter whose flag is set on the event **and**
always labels it with `peer_id` (may be `None`).

**Reads as**: connection health — dial failure rate (`dial_attempt_error /
dial_attempt`), whether the node is reachable behind NAT (`incoming_conn` vs
`incoming_conn_error`). Mirrors the Rust `libp2p_swarm` metrics.

---

### 6.5 Bitswap

File: `libp2p/metrics/bitswap.py`
Event: `BitswapEvent` (`libp2p/bitswap/events.py:9`)
Emit sites: `bitswap/client.py` (want adds/cancels, block send/receive,
provider query), `bitswap/session.py:46` (new session), `bitswap/message_queue.py:299`
(message sent — labels `kind`), `bitswap/provider_query.py:326`.

Fields: `want_add`, `want_cancel`, `block_received`, `block_sent`,
`message_sent`, `message_received`, `session_new`, `provider_query`, plus
`cid`, `size_bytes`, `kind`, `entries`, `msg_bytes`, `success`, `peers_found`,
`duration_ms`.

| Metric name | Type | Labels | Buckets (bytes) | Description |
|---|---|---|---|---|
| `bitswap_wantlist_adds_total` | Counter | — | — | Wantlist entries added |
| `bitswap_wantlist_cancels_total` | Counter | — | — | Wantlist entries cancelled |
| `bitswap_blocks_received_total` | Counter | — | — | Blocks received |
| `bitswap_blocks_sent_total` | Counter | — | — | Blocks sent |
| `bitswap_block_received_bytes` | Histogram | — | 64, 256, 1024, 4096, 16k, 64k, 256k, 1M | Received block sizes |
| `bitswap_block_sent_bytes` | Histogram | — | same | Sent block sizes |
| `bitswap_message_sent_total` | Counter | `kind` | — | Bitswap messages sent (e.g. wantlist/block/cancel kinds) |
| `bitswap_message_received_total` | Counter | `kind` | — | Bitswap messages received |
| `bitswap_message_received_bytes` | Histogram | — | same | Received message sizes |
| `bitswap_sessions_total` | Counter | — | — | Bitswap sessions created |
| `bitswap_provider_queries_total` | Counter | `result` | — | DHT provider queries from Bitswap |
| `bitswap_provider_queries_found` | Histogram | — | 1, 2, 5, 10, 20, 50 | Providers per query |

`record()` uses an **if/elif chain** — one event drives exactly one metric
(i.e. it is a discriminated union on the flags).

**Reads as**: DAG transfer activity (blocks in/out), whether clients cancel
wants early (`wantlist_cancels`), message efficiency (size distributions),
protocol page concurrency (`sessions`).

---

### 6.6 Discovery

File: `libp2p/metrics/discovery.py`
Event: `DiscoveryEvent` (`libp2p/discovery/events/events.py:13`)
Emit sites: `discovery/mdns/listener.py:83/102` (peer found/lost),
`discovery/bootstrap/bootstrap.py:279/382` (bootstrap connect result and peer
found), `discovery/random_walk/random_walk.py:126`.

Fields: `peer_discovered`, `peer_lost`, `bootstrap_connect`, `random_walk`,
plus `source` (mdns | bootstrap | random_walk | rendezvous), `success`,
`duration_ms`, `peers_found`.

| Metric name | Type | Labels | Buckets | Description |
|---|---|---|---|---|
| `discovery_peer_discovered_total` | Counter | `source` | — | Peers discovered by source |
| `discovery_peer_lost_total` | Counter | `source` | — | Peers lost/expired by source |
| `discovery_bootstrap_connect_total` | Counter | `result` | — | Bootstrap connect attempts |
| `discovery_bootstrap_connect_duration_ms` | Histogram | — | 10, 50, 100, 250, 500, 1000, 2500, 5000, 10000 | Bootstrap connect duration ms |
| `discovery_random_walk_total` | Counter | `result` | — | Random walk operations |
| `discovery_random_walk_peers_found` | Histogram | — | 1, 2, 5, 10, 20, 50 | Peers per random walk |

Also if/elif discriminated-union dispatch.

**Reads as**: discovery health by source — mDNS peers churning (`peer_lost`),
bootstrap reachability (`bootstrap_connect` failures), random-walk yield
(peers found per walk).

---

## 7. The legacy channel-based consumer

Pre-`attach`, the flow was: modules send events over a trio memory channel;
`Metrics.start_prometheus_server(recv_channel)` consumes them. It remains as
`Metrics.start_prometheus_server()` and differs from the modern path:

| | `attach()` + listener | legacy channel consumer |
|---|---|---|
| transport | event bus (registered listener) | trio `MemoryReceiveChannel` |
| module coverage | all six modules | ping, gossipsub, kad, swarm (4) |
| visibility | instant, synchronous | async loop on the channel |
| failure handling | per-event try/except (debug log) | per-event try/except |

Use `attach()` for new code; the old function is kept for back-compat and the
older examples.

---

## 8. The observability stack: Prometheus + Grafana

`libp2p/metrics/prometheus.yml`:

```yaml
global:
  scrape_interval: 5s
scrape_configs:
  - job_name: "libp2p-python"
    static_configs:
      - targets: ["host.docker.internal:8000"]
```

`examples/metrics/docker-compose.yml` runs:

- **Prometheus** (`prom/prometheus:latest`) on `$PROMETHEUS_PORT` → 9090,
  scraping the node's `/metrics` port (8000) via `host.docker.internal`.
- **Grafana** (`grafana/grafana:latest`) on `$GRAFANA_PORT` → 3000, data
  source = Prometheus.

Run the demo:

```bash
pip install -e .            # installs the `metrics-demo` entrypoint
metrics-demo                # terminal 1 — node A
metrics-demo                # terminal 2 — node B, then `connect <a-multiaddr>`
PROMETHEUS_PORT=9001 GRAFANA_PORT=7001 docker compose up
```

Then in node A's shell:

```bash
ping <peerB> 15             # fires ping RTT histograms
join pubsub-chat            # both nodes
publish pubsub-chat hello!  # gossipsub counters
put /exp/fa kad-dht-value   # node A
get /exp/fa                 # node B → kad counters
advertize content-id ; get_provider content-id
```

---

## 9. Tests

`tests/core/observability/`:

| File | Covers |
|---|---|
| `test_prometheus_metrics.py` | Each collector's `record()` on synthetic events; checks counters/histogram values; `find_available_port` |
| `test_metrics_listener.py` | `MetricsListener` dispatch for all six event types |
| `test_event_bus_integration.py` | Full round trip: module emits → bus → listener → metrics; HTTP server bootstrapping is mocked |

Conventions used by tests: build an event, set the boolean flag + payload
fields, call `metrics.<module>.record(event)`, then assert
`prometheus_client` registry values (e.g. via `get_sample_value(...)`).

---

## 10. Comparison with go-libp2p / rust-libp2p

**py-libp2p is single-package; go/rust are multi-module.**

- In **go-libp2p**, each repo (go-libp2p-pubsub, go-libp2p-kad-dht,
  go-libp2p-swarm, go-libp2p-record, …) is an independent Go module and every
  one carries its own `metrics.go` next to the protocol code. Metrics are
  *registered into a registry that the node supplies* (e.g.
  `prometheus.Register(metrics.New(...))` or a custom `Registerer`), and there
  is no central "metrics package" — `go-libp2p` itself only has `metrics`
  helpers for its own transport/swarm bits.
- **rust-libp2p** is one workspace, and each crate (`libp2p-swarm`,
  `libp2p-gossipsub`, `libp2p-kad`, `libp2p-bitswap`… but note bitswap lives in
  rust-ipfs) exposes a `metrics::Metrics` builder that the app connects to a
  registry. The py-libp2p swarm metrics docstring explicitly says "Mirrors the
  Rust libp2p metrics implementation".
- **py-libp2p** uses the Rust *conceptual* model (per-module metrics classes,
  single registry) but with Go *naming* style: `ping` histogram buckets match
  go-libp2p's (`1,5,10,25,50,100,200,500,1000` ms), counters are named
  `_total/_bytes` etc.

**Name mapping (informal, go → py):**

| go-libp2p | py-libp2p |
|---|---|
| `ping` histogram (same buckets) | `ping` |
| `libp2p_gossipsub_publish_count` etc. | `gossipsub_publish_out_total` |
| `libp2p_kad_*` | `kad_*` |
| swarm `incoming_connection_*` / `outgoing_connection_*` | `swarm_incoming_conn*` / `swarm_dial_attempt*` |

Where they differ materially: py-libp2p centralises registration in the default
prometheus registry (no per-module opt-in registerer) and drives everything off
the event bus rather than direct call sites.

---

## 11. Advanced: adding metrics for a new module

To instrument a new module (say `ipfs_bitswap`-style blockstore stats or a new
`relay` protocol):

1. **Define the event** — in the module (careful of circular imports), or in a
   sibling `events.py` (kad-dht precedent):

   ```python
   class RelayEvent:
       peer_id: str | None = None
       hop_opened: bool = False
       hop_close: bool = False
       duration_ms: float | None = None
   ```

2. **Emit it** — after the operation:

   ```python
   event = RelayEvent()
   event.hop_opened = True
   event.duration_ms = ms
   self.host.get_event_bus().emit(event)
   ```

3. **Write the collector** — `libp2p/metrics/relay.py`:

   ```python
   from prometheus_client import Counter, Histogram
   from libp2p.relay.events import RelayEvent

   class RelayMetrics:
       def __init__(self) -> None:
           self.hop_opened = Counter(
               "relay_hop_opened_total",
               "Relay hop circuits opened",
               labelnames=["peer_id"],
           )
           self.hop_duration_ms = Histogram(
               "relay_hop_duration_ms",
               "Relay hop duration ms",
               buckets=[10, 50, 100, 250, 500, 1000, 5000, 10000],
           )

       def record(self, event: RelayEvent) -> None:
           if event.hop_opened:
               self.hop_opened.labels(peer_id=event.peer_id or "").inc()
               if event.duration_ms is not None:
                   self.hop_duration_ms.observe(event.duration_ms)
   ```

4. **Wire it in** — add `relay = RelayMetrics()` to `Metrics.__init__`, its
   import to `libp2p/metrics/metrics.py`, and a `case RelayEvent():` branch in
   `MetricsListener.handle_event()`.

5. **Test** — add a case to `tests/core/observability/` modeled on
   `test_prometheus_metrics.py`.

That's the whole contract: *flag-bearing event → collector → registry*.

---

## 12. FAQ and gotchas

**Q: Why is there both a `MetricsListener` and `start_prometheus_server`?**
A: The listener is the modern path (bus-based, all six modules). The channel
consumer is legacy, kept for compatibility, four modules only.

**Q: Why do swarm counters use raw peer IDs as labels?**
A: They mirror the Rust/Go swarm metrics; high cardinality is acceptable for
swarm-level counters in small deployments but watch your Prometheus label
cardinality with many peers (see `gossipsub_*`/`kad_inbound_*` — same pattern).

**Q: Why do bitswap and discovery avoid peer_id labels?**
A: Docstrings say "bounded labels only" — these are stable, low-cardinality
metrics safe at scale (kinds, sources, results).

**Q: What happens if `record()` throws?**
A: The legacy consumer catches everything and debug-logs. The listener path
does not wrap `record()` per event, so a collector bug surfaces immediately —
keep `record()` side-effect free.

**Q: Do collectors count an inbound gossipsub message more than once?**
A: Yes, deliberately: once in `received_total`, plus once per subtype metric
(`publish`/`subopts`/`control`).

**Q: Can I reuse one `Metrics()` for multiple hosts?**
A: `attach()` takes a bus; collectors live in the default registry, so all
hosts sharing the bus would be aggregated across nodes unless you label
additionally. Run one `Metrics` per process for clean data.

**Q: Port already in use?**
A: `find_available_port()` walks up from 8000 (news of `8000`, `8001`, …) until
a bind succeeds.

**Q: Where do event payload fields come from?**
A: From the emit site, e.g. lookup duration is computed in
`peer_routing._emit_lookup_event` as `(trio.current_time() - start_time) * 1000`
and routed table size from `self.routing_table.size()` in the maintenance
loop.

---

*Generated from the py-libp2p codebase (`libp2p/metrics/`, module event
definitions, and `examples/metrics/`).*