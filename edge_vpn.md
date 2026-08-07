# Building an Edge VPN using py-libp2p
*A comprehensive guide from first principles to architecture and implementation*

---

# Table of Contents

1. Introduction
2. What is a VPN?
3. What is an Edge VPN?
4. Traditional VPN vs Edge VPN
5. Understanding Networking Fundamentals
6. How Edge VPNs Actually Work
7. The Role of libp2p
8. What py-libp2p Already Provides
9. What an Application Must Build
10. Complete Architecture
11. Packet Journey
12. Components Explained
13. Security Model
14. NAT Traversal
15. Routing
16. Address Allocation
17. Control Plane vs Data Plane
18. Proposed py-libp2p Edge VPN Architecture
19. Development Roadmap
20. Future Enhancements

---

# 1. Introduction

An Edge VPN is **not simply another VPN protocol.**

Instead, it is a **distributed secure networking architecture** where every participating device acts as an intelligent network edge.

Instead of saying:

> "Connect everything through one VPN server"

an Edge VPN says

> "Connect devices directly whenever possible."

This makes it extremely scalable.

Modern examples include

- Tailscale
- NetBird
- ZeroTier
- Netmaker

The idea is much closer to distributed systems than traditional networking.

---

# 2. What is a VPN?

VPN means

**Virtual Private Network**

It creates a private encrypted network over the public Internet.

Instead of

```
Laptop ---- Internet ---- Server
```

you get

```
Laptop ==Encrypted Tunnel== Server
```

Everything inside this tunnel is encrypted.

The applications don't even know the Internet exists.

To them,

it looks like both devices are on the same LAN.

---

# 3. Traditional VPN

Example:

```
                 VPN Server

             +---------------+
             |               |
             |  WireGuard    |
             |  OpenVPN      |
             +---------------+

              /     |      \
             /      |       \

Laptop     Phone   EC2     Office PC
```

Every packet goes through

the VPN server.

Even if Laptop wants to talk to EC2,

traffic still becomes

```
Laptop

↓

VPN Server

↓

EC2
```

Problems

- single bottleneck
- higher latency
- server bandwidth cost
- single point of failure

---

# 4. Edge VPN

Instead

```
Laptop ------------ EC2

     \             /

      \           /

      Raspberry Pi

             |

          Home NAS
```

Every node can communicate directly.

No centralized traffic forwarding.

Only a control server may exist.

This is a massive architectural difference.

---

# 5. Important Networking Concepts

Before understanding Edge VPN,

understand these concepts.

---

## Physical Network

Actual Ethernet cables

WiFi

Fiber

etc.

---

## IP Address

Every machine has

```
192.168.x.x
10.x.x.x
172.x.x.x
```

or public IP.

---

## Routing

Routing decides

Where should this packet go?

---

## Interface

Linux

```
eth0

wlan0

lo
```

VPN creates another interface

```
tun0
```

Applications use tun0

without realizing

their packets are actually traveling through the Internet.

---

## TUN Device

This is probably the most important concept.

A TUN device is

a virtual network card.

Linux kernel believes

it is a real network adapter.

But instead of sending packets to hardware,

it gives packets to your application.

Example

```
Chrome

↓

Kernel

↓

tun0

↓

Your VPN application

↓

Internet
```

---

# 6. Packet Journey

Suppose

Laptop pings

10.100.0.2

Kernel routing table says

```
Send to tun0
```

Kernel writes packet

to tun0.

Your VPN application reads

```
IP Packet
```

Application encrypts packet

Application sends through libp2p

Remote peer receives

Application decrypts

Writes packet into tun0

Remote kernel receives packet.

To applications

it feels like

a normal LAN.

---

# 7. Why libp2p?

libp2p already solves

many difficult networking problems.

Instead of implementing

secure networking,

peer discovery,

NAT traversal,

identity,

transport,

yourself,

you simply use libp2p.

Think of libp2p as

TCP/IP for decentralized applications.

---

# 8. What py-libp2p Already Provides

This is extremely important.

py-libp2p already provides almost everything below.

---

## Peer Identity

Every peer has

```
Private Key

↓

Public Key

↓

Peer ID
```

Like

```
12D3KooW...
```

This uniquely identifies every node.

No passwords.

No usernames.

---

## Secure Channels

Supports

Noise

TLS

Every byte is encrypted.

You do NOT need to implement encryption.

---

## Stream Multiplexing

One TCP connection

can contain many logical streams.

Instead of

```
TCP x 100
```

you get

```
One TCP

↓

100 Streams
```

Huge efficiency improvement.

---

## Multiple Transports

TCP

QUIC

WebSockets

etc.

Application doesn't care.

---

## DHT

Distributed Hash Table

Allows

finding peers

without central database.

---

## mDNS

Automatic LAN discovery.

Computers find each other automatically.

---

## Relay

If direct connection fails,

relay through another peer.

---

## Connection Management

Reconnect

Keep alive

Stream lifecycle

Connection reuse

Already implemented.

---

## Multiaddr

Flexible addressing

Instead of

```
IP + Port
```

libp2p uses

```
/ip4/1.2.3.4/tcp/4001/p2p/Qm...
```

Much more expressive.

---

# 9. What py-libp2p DOES NOT Provide

This is your responsibility.

---

## Virtual Network Interface

Need

```
tun0
```

using

```
pytun

python-pytun

pyroute2
```

---

## IP Packet Processing

Need code to

Read packet

Parse packet

Forward packet

---

## Routing Logic

Need to decide

```
Packet destined for

10.0.0.8

↓

Send to Peer A
```

---

## Address Allocation

Need virtual IPs

```
10.100.0.1

10.100.0.2

10.100.0.3
```

Need DHCP-like mechanism.

---

## DNS

Need

```
laptop.edge

server.edge
```

mapping.

---

## ACL

Need

Who can talk to whom?

---

## Firewall

Need filtering

before forwarding.

---

## MTU Handling

Packets larger than transport

must be fragmented.

---

## Network Configuration

Need CLI

```
edgevpn join

edgevpn leave

edgevpn peers
```

---

# 10. Complete Architecture

```
                Applications

        Chrome SSH Docker Ping

                    │

                    ▼

             Linux Networking

                    │

              Routing Table

                    │

                tun0 Device

                    │

        --------------------------

        Edge VPN Application

        --------------------------

        Packet Parser

        Routing Engine

        Firewall

        Compression

        Fragmentation

        Virtual IP Manager

        DNS Resolver

        ACL Engine

        Session Manager

        --------------------------

                    │

              py-libp2p

      Secure Streams

      Peer Discovery

      DHT

      Relay

      Noise

      Multiplexing

                    │

              Internet

                    │

          Remote py-libp2p

                    │

         Remote VPN Application

                    │

               Remote tun0
```

---

# 11. Control Plane vs Data Plane

This distinction is critical.

## Control Plane

Responsible for

- peer discovery
- authentication
- IP assignment
- routing updates
- configuration

Very little traffic.

---

## Data Plane

Responsible for

actual packets.

Millions of packets.

Example

Netflix video

SSH

HTTP

Ping

Everything flows here.

---

# 12. Address Allocation

Every node needs

virtual IP.

Example

```
Laptop

10.100.0.1

EC2

10.100.0.2

NAS

10.100.0.3
```

Applications never see

real Internet IP.

Only virtual network.

---

# 13. Routing Table

Need something like

| Destination | Peer ID |
|-------------|----------|
|10.100.0.2|PeerA|
|10.100.0.3|PeerB|
|10.100.0.4|PeerC|

Whenever packet arrives

lookup destination.

Forward.

---

# 14. Packet Format

You probably won't send raw IP packet directly.

Example

```
+---------------------+

Packet Header

Version

Source Peer

Destination Peer

Sequence Number

Timestamp

Flags

Compression

Encryption Metadata

+---------------------+

Raw IP Packet

+---------------------+
```

---

# 15. Security

Need

Authentication

Authorization

Encryption

Replay protection

Peer verification

Certificate rotation

Session expiry

ACL

Most encryption already comes from libp2p.

---

# 16. NAT Traversal

Problem

Both devices behind routers.

Neither knows public address.

Solutions

STUN

Hole Punching

Relay

libp2p already helps enormously here.

---

# 17. Reliability

Need

Heartbeat

Reconnect

Peer timeout

Packet loss detection

Keep Alive

Sequence numbers

---

# 18. Proposed Project Structure

```
edgevpn/

├── cli.py

├── config.py

├── peer_manager.py

├── packet.py

├── packet_parser.py

├── tunnel.py

├── routing.py

├── firewall.py

├── dns.py

├── ip_allocator.py

├── control_plane.py

├── data_plane.py

├── stream_handler.py

├── libp2p_node.py

├── crypto.py

├── metrics.py

├── logging.py

└── utils.py
```

---

# 19. Suggested Development Roadmap

### Phase 1

Basic py-libp2p communication

```
Peer A

↓

Peer B

↓

Send bytes
```

---

### Phase 2

Create TUN interface

Read packets

Print packets

---

### Phase 3

Write packets

back into TUN

---

### Phase 4

Tunnel packets through libp2p

---

### Phase 5

Assign virtual IPs

---

### Phase 6

Routing

---

### Phase 7

Peer discovery

using DHT

---

### Phase 8

Automatic reconnect

---

### Phase 9

DNS

---

### Phase 10

CLI

---

# 20. Long-Term Vision

A mature py-libp2p Edge VPN could support:

- Secure mesh networking
- Multi-cloud networking
- Kubernetes cluster connectivity
- Home lab networking
- Remote development
- IoT device networking
- Site-to-site networking
- Zero Trust access
- Multi-hop routing
- Dynamic peer discovery
- Self-healing mesh
- Identity-based networking

At that point, your project would resemble the architecture of systems like Tailscale or NetBird, but built on py-libp2p instead of WireGuard.

---

# Key Takeaways

## py-libp2p gives you:
- ✔ Peer identity
- ✔ Secure encrypted channels
- ✔ Peer discovery (mDNS/DHT)
- ✔ NAT traversal support
- ✔ Relays
- ✔ Stream multiplexing
- ✔ Connection management
- ✔ Multi-addressing

## Your Edge VPN application must add:
- ✔ TUN interface integration
- ✔ Virtual IP management
- ✔ Packet encapsulation/decapsulation
- ✔ Routing engine
- ✔ DNS
- ✔ Firewall/ACL
- ✔ Configuration management
- ✔ Control plane
- ✔ Data plane
- ✔ CLI
- ✔ Monitoring and metrics

---

# Final Perspective

Think of an Edge VPN as **building a distributed virtual Ethernet switch on top of the Internet**.

- The **operating system** generates IP packets.
- The **TUN interface** hands those packets to your application.
- Your **application** decides where they should go, applies VPN-specific logic (routing, ACLs, virtual IPs), and forwards them.
- **py-libp2p** provides the secure, authenticated, peer-to-peer transport between nodes.
- The remote application unwraps the packets and injects them back into its own TUN interface, making remote machines appear as if they are on the same local network.

The key architectural principle is separation of responsibilities:

- **libp2p = Secure peer-to-peer transport layer**
- **Your application = Virtual network (VPN) layer**

This separation lets you focus on networking logic while relying on libp2p for identity, encryption, connectivity, and peer communication.