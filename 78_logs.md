# FAILING TESTS ANALYSIS

## Overview
All 6 of the interop tests involving `nim-v1.15` failed during the test run. An analysis of the logs indicates a systemic issue where both the dialer and listener nodes are unable to establish a connection to the relay node.

## Failing Tests & Configurations
1. **rust-v0.56 x nim-v1.15** (tcp, noise, yamux)
2. **rust-v0.56 x nim-v1.15** (tcp, noise, mplex)
3. **nim-v1.15 x rust-v0.56** (tcp, noise, yamux)
4. **nim-v1.15 x rust-v0.56** (tcp, noise, mplex)
5. **nim-v1.15 x nim-v1.15** (tcp, noise, yamux)
6. **nim-v1.15 x nim-v1.15** (tcp, noise, mplex)

**Error Status**: 
- Nim nodes: `Connection to relay timed out: Timeout exceeded!` (after 30 seconds)
- Rust nodes: `Error: Failed to connect: Transport([... Other(Custom { kind: Other, error: Timeout })])` (after 30 seconds)

## The Problem
Both the dialer and the listener containers are failing to establish a multiplexed secure connection to the relay container (`rust-v0.56`). The timeout occurs exactly during the dial phase when the nodes attempt to connect to the relay's published multiaddress (e.g., `/ip4/10.228.222.68/tcp/37687/p2p/12D3KooWF...`). Because the relay connection is never established, the listener cannot create a `p2p-circuit` reservation, and the dialer cannot reach the listener, resulting in a complete failure of the hole-punching workflow.

## Why it happens (Root Cause Analysis)
By cross-referencing the logs, we can isolate the variable causing the failure. Notably, the timeout occurs not just for the `nim-v1.15` nodes, but **also for the `rust-v0.56` nodes** when they act as the dialer or listener. Since the `rust-v0.56` dialer fails to connect to the `rust-v0.56` relay, this eliminates `nim-libp2p` as the sole root cause.

The issue stems from a **Docker network routing/NAT configuration problem** or a **libp2p handshake stall** at the relay level:
1. **NAT Routing Blackhole**: The `dialer_router` and `listener_router` perform `MASQUERADE` on the `wan0` interfaces. However, the relay container is artificially injected with static routes back to the internal subnets (`Setting route to dialer subnet 10.228.222.96/27 via 10.228.222.66`). When the relay responds to the incoming TCP SYN (which has the masqueraded WAN IP of the router), it sends the SYN-ACK directly to the router. If `conntrack` on the router drops the reverse-masquerade routing (due to asymmetric routing perceptions or MTU blackholes), the TCP handshake never completes.
2. **Relay Multistream/Protocol Stall**: Alternatively, the TCP connection succeeds, but the `multistream-select` handshake stalls. If the relay is waiting for the dialer to send the protocol preamble, but the dialer is waiting for the relay, the connection will hit the hardcoded `30.seconds` timeout (as seen in Nim's `sw.connect(relayMA).wait(30.seconds)`).

## Where to fix
To resolve this issue, developers should investigate the following areas:
1. **Network Infrastructure (`run.sh` / iptables)**: 
   - Remove the artificial static routes injected into the relay container (`ip route add ... via ...`). The relay should not need explicit routes to the private subnets since the routers are performing NAT masquerading. The NAT router's `conntrack` is sufficient to return packets.
   - Verify that IP forwarding (`sysctl net.ipv4.ip_forward=1`) is persistently enabled on the `dialer_router` and `listener_router` containers.
2. **Relay Configuration**:
   - Check if the `rust-v0.56` relay requires specific flags to properly respond to `multistream-select` immediately.
3. **Nim Connection Timeout (`interop/hole-punching/hole_punching.nim:90`)**:
   - While the root cause is environmental or relay-specific, the Nim implementation handles the timeout correctly by raising an `AsyncTimeoutError`. Developers can add more granular debug logging in `nim-libp2p`'s multistream-select module to determine exactly which protocol handshake is hanging (e.g., `/noise` or `/yamux/1.0.0`) before the 30-second timeout hits.

## Resolution (Fixed)
After an iterative debugging session, the root cause was verified to be **Docker Virtual Ethernet Checksum Offloading**. 
When the relay container replied with SYN-ACK packets, Docker's veth interface did not compute the TCP checksums correctly because of hardware offloading. When these packets arrived at the NAT routers (`dialer-router` and `listener-router`), `conntrack` saw the invalid checksums and marked the packets as `INVALID`. Consequently, `conntrack` failed to reverse-translate the destination IP addresses from the router's WAN IP back to the peer's LAN IP. The `INPUT` chain drop rules then silently dropped the packets, causing a TCP handshake timeout.

**The fixes applied were:**
1. Modified `images/linux/Dockerfile` to install `ethtool`.
2. Updated `images/linux/run.sh` to include `iptables` `CHECKSUM` fill targets for outgoing packets (`iptables -t mangle -A POSTROUTING -p tcp -j CHECKSUM --checksum-fill`).
3. Re-enabled the `INPUT DROP` rule in `images/linux/run.sh` to properly simulate the NAT and drop un-tracked packets (to avoid TCP RSTs).
4. Modified the Docker Compose generation in `lib/run-single-test.sh` to inject the `net.netfilter.nf_conntrack_checksum=0` sysctl into the routers. This forces `conntrack` to ignore checksum verification on incoming packets and allows it to successfully track and translate the Relay's SYN-ACK packets.

All 6 failing tests now successfully pass.
