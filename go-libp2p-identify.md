# Deep Dive: libp2p Identify & Identify Push Protocols

## Table of Contents
1. [Overview](#overview)
2. [Core Concepts](#core-concepts)
3. [Identify Protocol](#identify-protocol)
4. [Identify Push Protocol](#identify-push-protocol)
5. [Implementation Details](#implementation-details)
6. [Workflow & Message Flow](#workflow--message-flow)
7. [Code Examples](#code-examples)
8. [Best Practices](#best-practices)

---

## Overview

The **identify** protocol in libp2p is fundamental to peer discovery and capability negotiation. It allows peers to exchange metadata about themselves, including:

- **Peer ID**: The unique identifier of the peer
- **Protocol Support**: Which protocols the peer implements
- **Listen Addresses**: How to reach the peer
- **User Agent**: Software version and implementation details
- **Observed Address**: What address the remote peer sees you on

### Why Two Protocols?

- **`/ipfs/id/1.0.0`** (Identify): Request-response model for initial handshake
- **`/ipfs/id/push/1.0.0`** (Identify Push): Notification model for updates

---

## Core Concepts

### 1. Peer Identity Exchange

When two libp2p nodes connect, they need to know:
- Who they're talking to (verification)
- How to communicate (supported protocols)
- Where to find them later (addresses)

```go
// The Identify message structure (protobuf)
type Identify struct {
    ProtocolVersion   string   // e.g., "ipfs/0.1.0"
    AgentVersion      string   // e.g., "go-libp2p/0.27.0"
    PublicKey         []byte   // Peer's public key
    ListenAddrs       [][]byte // Multiaddrs the peer listens on
    ObservedAddr      []byte   // The address as seen by remote peer
    Protocols         []string // Supported protocols like "/kad/1.0.0"
    SignedPeerRecord  []byte   // Certified address information
}
```

### 2. Connection Lifecycle

```
Peer A                                  Peer B
   |                                       |
   |-------- Open Connection ------------>|
   |                                       |
   |<------- Identify Request ------------|
   |                                       |
   |-------- Identify Response ---------->|
   |  (PublicKey, Protocols, Addresses)   |
   |                                       |
   |   [Both peers now have metadata]     |
   |                                       |
   |<------ Identify Push (updates) ------|
   |  (When B's state changes)            |
```

### 3. Service Discovery

After identify exchange, peers know:
- Which protocols to use for communication
- Whether the peer supports required features
- How to establish future connections

---

## Identify Protocol

### Purpose
The identify protocol runs automatically when a new connection is established. It's the **initial handshake** that establishes mutual understanding.

### Protocol Flow

```go
// Simplified flow
func (ids *idService) HandleIdentifyRequest(conn network.Conn) {
    // 1. Open identify stream
    stream, err := conn.NewStream(identify.ID)
    
    // 2. Send our identify message
    ids.sendIdentifyResponse(stream, conn)
    
    // 3. Close stream (request-response done)
    stream.Close()
}
```

### Key Components

#### 1. **IDService** Structure

```go
type IDService struct {
    Host          host.Host
    UserAgent     string
    ProtocolVersion string
    
    // Cache of observed addresses
    observedAddrs *ObservedAddrManager
    
    // Peer metadata storage
    peerstore     peerstore.Peerstore
    
    // Identify push handling
    pushSemaphore chan struct{}
}
```

#### 2. **Triggering Identify**

Identify is triggered in several scenarios:

```go
// Scenario 1: Incoming connection
func (ids *IDService) IdentifyConn(conn network.Conn) {
    // Automatically triggered by libp2p
    go ids.handleIncomingIdentify(conn)
}

// Scenario 2: Outgoing connection
func (ids *IDService) IdentifyWait(conn network.Conn) <-chan struct{} {
    // Wait for identify to complete before using connection
    return ids.waitForIdentify(conn)
}

// Scenario 3: Manual trigger
func (ids *IDService) Push() {
    // Manually push updates to all peers
    ids.pushToAllPeers()
}
```

#### 3. **Information Gathering**

```go
func (ids *IDService) createIdentifyMessage(conn network.Conn) *pb.Identify {
    // Gather local information
    msg := &pb.Identify{
        ProtocolVersion: ids.ProtocolVersion,
        AgentVersion:    ids.UserAgent,
        PublicKey:       ids.marshalPublicKey(),
        Protocols:       ids.Host.Mux().Protocols(),
        
        // Get all listen addresses
        ListenAddrs: ids.getAllListenAddrs(),
        
        // Tell remote peer what address we see them on
        ObservedAddr: conn.RemoteMultiaddr().Bytes(),
        
        // Include signed peer record if available
        SignedPeerRecord: ids.getSignedPeerRecord(),
    }
    return msg
}
```

#### 4. **Address Discovery**

One critical feature is **observed address detection**:

```go
// When we receive identify from remote peer
func (ids *IDService) consumeIdentifyMessage(msg *pb.Identify, conn network.Conn) {
    // They tell us what address THEY see us on
    observedAddr := msg.GetObservedAddr()
    
    // Add to our observed addresses
    ids.observedAddrs.Record(
        conn,
        ma.NewMultiaddrBytes(observedAddr),
    )
    
    // If multiple peers report same address, we might be reachable there
    if ids.observedAddrs.IsReachable(observedAddr) {
        ids.Host.AddAddress(observedAddr)
    }
}
```

---

## Identify Push Protocol

### Purpose
Identify Push allows peers to **proactively notify** connected peers about changes without waiting for a new connection or request.

### When to Push?

Push updates are sent when:

1. **New protocols added/removed**
   ```go
   host.SetStreamHandler("/myprotocol/1.0.0", handler)
   // Automatically triggers identify push
   ```

2. **Listen addresses change**
   ```go
   // Network interface changes, new listeners
   host.Network().Listen(newAddr)
   // Push triggered
   ```

3. **Signed peer record updates**
   ```go
   // When certified address record changes
   host.Peerstore().AddSignedPeerRecord(record)
   ```

### Push Implementation

```go
type pushHandler struct {
    idService *IDService
    
    // Limit concurrent pushes
    semaphore chan struct{}
    
    // Track which peers need updates
    dirtyPeers map[peer.ID]struct{}
}

func (ids *IDService) Push() {
    // Get all connected peers
    peers := ids.Host.Network().Peers()
    
    for _, p := range peers {
        // Send push to each peer concurrently
        go ids.pushToPeer(p)
    }
}

func (ids *IDService) pushToPeer(p peer.ID) {
    // Rate limiting: don't overwhelm peers
    ids.pushSemaphore <- struct{}{}
    defer func() { <-ids.pushSemaphore }()
    
    // Open push stream
    stream, err := ids.Host.NewStream(
        context.Background(),
        p,
        identify.IDPush,
    )
    if err != nil {
        return
    }
    defer stream.Close()
    
    // Send updated identify message
    msg := ids.createIdentifyMessage(stream.Conn())
    writer := pbio.NewDelimitedWriter(stream)
    writer.WriteMsg(msg)
}
```

### Receiving Push Updates

```go
func (ids *IDService) handlePushStream(stream network.Stream) {
    defer stream.Close()
    
    // Read the pushed identify message
    msg := &pb.Identify{}
    reader := pbio.NewDelimitedReader(stream, maxMessageSize)
    
    if err := reader.ReadMsg(msg); err != nil {
        return
    }
    
    // Update our knowledge of the remote peer
    ids.consumeIdentifyMessage(msg, stream.Conn())
    
    // Store updated protocols
    peerID := stream.Conn().RemotePeer()
    ids.Peerstore().SetProtocols(peerID, msg.Protocols...)
    
    // Store updated addresses
    ids.Peerstore().AddAddrs(
        peerID,
        convertAddrs(msg.ListenAddrs),
        peerstore.TempAddrTTL,
    )
}
```

---

## Implementation Details

### 1. Stream Management

```go
// Protocol IDs
const (
    ID     = "/ipfs/id/1.0.0"       // Identify protocol
    IDPush = "/ipfs/id/push/1.0.0"  // Identify push protocol
)

// Setting up handlers
func (ids *IDService) Start() {
    // Handle incoming identify requests
    ids.Host.SetStreamHandler(ID, func(s network.Stream) {
        ids.handleIdentifyRequest(s)
    })
    
    // Handle incoming push updates
    ids.Host.SetStreamHandler(IDPush, func(s network.Stream) {
        ids.handlePushStream(s)
    })
}
```

### 2. Protobuf Serialization

```go
import (
    pbio "github.com/libp2p/go-libp2p/p2p/protocol/identify/pb"
    ggio "github.com/gogo/protobuf/io"
)

func writeIdentifyMessage(stream network.Stream, msg *pb.Identify) error {
    // Use length-prefixed protobuf encoding
    writer := ggio.NewDelimitedWriter(stream)
    return writer.WriteMsg(msg)
}

func readIdentifyMessage(stream network.Stream) (*pb.Identify, error) {
    reader := ggio.NewDelimitedReader(stream, maxMessageSize)
    msg := &pb.Identify{}
    err := reader.ReadMsg(msg)
    return msg, err
}
```

### 3. Concurrent Safety

```go
type IDService struct {
    mu sync.RWMutex
    
    // Track identify status per connection
    conns map[network.Conn]*identifyState
}

type identifyState struct {
    completed chan struct{} // Signals identify done
    err       error         // Any error that occurred
}

func (ids *IDService) IdentifyWait(conn network.Conn) <-chan struct{} {
    ids.mu.Lock()
    state, exists := ids.conns[conn]
    if !exists {
        state = &identifyState{
            completed: make(chan struct{}),
        }
        ids.conns[conn] = state
        go ids.doIdentify(conn, state)
    }
    ids.mu.Unlock()
    
    return state.completed
}
```

### 4. Signed Peer Records

```go
// Signed peer records provide authenticated address information
type SignedPeerRecord struct {
    PeerID    peer.ID
    Seq       uint64      // Sequence number for updates
    Addresses []multiaddr.Multiaddr
    Signature []byte      // Signed by peer's private key
}

func (ids *IDService) getSignedPeerRecord() []byte {
    // Get envelope from peerstore
    envelope := ids.Peerstore().SignedPeerRecord(ids.Host.ID())
    if envelope == nil {
        return nil
    }
    
    // Marshal to bytes
    data, _ := envelope.Marshal()
    return data
}

func (ids *IDService) consumeSignedPeerRecord(data []byte, peerID peer.ID) {
    // Unmarshal and verify signature
    envelope, err := record.ConsumeEnvelope(data, peer.PeerRecordEnvelopeDomain)
    if err != nil {
        return
    }
    
    // Extract and verify peer record
    rec, ok := envelope.Record.(*peer.PeerRecord)
    if !ok || rec.PeerID != peerID {
        return
    }
    
    // Store in peerstore with higher confidence
    ids.Peerstore().AddAddrs(
        peerID,
        rec.Addrs,
        peerstore.SignedAddrTTL, // Longer TTL for signed addrs
    )
}
```

---

## Workflow & Message Flow

### Complete Connection Workflow

```
Time  Peer A (Client)                    Peer B (Server)
  |                                           |
  1   Connect to Peer B
  |   -------------------------------->       |
  |                                           |
  2                                    Accept connection
  |                                    Start identify service
  |                                           |
  3                                    Open identify stream
  |   <--------------------------------       |
  |                                           |
  4                                    Send Identify message:
  |   <--------------------------------       - PublicKey
  |                                           - Protocols: [/kad/1.0.0, /gossipsub/1.0.0]
  |                                           - ListenAddrs: [/ip4/192.168.1.5/tcp/4001]
  |                                           - ObservedAddr: /ip4/203.0.113.5/tcp/54321
  |                                           |
  5   Parse & store metadata                  |
  |   - Verify PublicKey matches PeerID       |
  |   - Store protocols in peerstore          |
  |   - Store addresses                       |
  |   - Record observed address               |
  |                                           |
  6   Open identify stream (our turn)         |
  |   -------------------------------->       |
  |                                           |
  7   Send our Identify message               |
  |   -------------------------------->       |
  |                                           |
  8                                    Parse & store our metadata
  |                                           |
  9   [Both peers have complete metadata]    |
  |                                           |
  10  Later: Peer A adds new protocol         |
  |   SetStreamHandler("/myproto/1.0.0")      |
  |                                           |
  11  Open identify push stream               |
  |   -------------------------------->       |
  |                                           |
  12  Send updated Identify (push)            |
  |   -------------------------------->       - New protocols list
  |                                           |
  13                                   Update stored protocols
  |                                    Now knows about /myproto/1.0.0
  |                                           |
```

### State Transitions

```go
type IdentifyState int

const (
    IdentifyStateInit IdentifyState = iota
    IdentifyStateWaiting    // Waiting for response
    IdentifyStateCompleted  // Successfully identified
    IdentifyStateFailed     // Identify failed
)

// Example state machine
func (ids *IDService) handleConnection(conn network.Conn) {
    state := IdentifyStateInit
    
    // Transition: Init -> Waiting
    state = IdentifyStateWaiting
    err := ids.sendIdentify(conn)
    
    if err != nil {
        // Transition: Waiting -> Failed
        state = IdentifyStateFailed
        return
    }
    
    // Transition: Waiting -> Completed
    state = IdentifyStateCompleted
    ids.notifyConnected(conn)
}
```

---

## Code Examples

### Example 1: Basic Setup

```go
package main

import (
    "context"
    "fmt"
    
    "github.com/libp2p/go-libp2p"
    "github.com/libp2p/go-libp2p/core/host"
    "github.com/libp2p/go-libp2p/core/peer"
    "github.com/libp2p/go-libp2p/p2p/protocol/identify"
)

func main() {
    // Create a libp2p host (identify is enabled by default)
    host, err := libp2p.New(
        libp2p.UserAgent("my-app/1.0.0"),
        libp2p.ProtocolVersion("my-protocol/1.0.0"),
    )
    if err != nil {
        panic(err)
    }
    defer host.Close()
    
    fmt.Printf("Host ID: %s\n", host.ID())
    fmt.Printf("Listening on: %v\n", host.Addrs())
}
```

### Example 2: Monitoring Identify Events

```go
func monitorIdentifyEvents(h host.Host) {
    // Subscribe to identify events
    sub, err := h.EventBus().Subscribe(new(event.EvtPeerIdentificationCompleted))
    if err != nil {
        panic(err)
    }
    defer sub.Close()
    
    for {
        select {
        case evt := <-sub.Out():
            identifyEvt := evt.(event.EvtPeerIdentificationCompleted)
            
            fmt.Printf("Identified peer: %s\n", identifyEvt.Peer)
            
            // Get peer's protocols
            protocols, _ := h.Peerstore().GetProtocols(identifyEvt.Peer)
            fmt.Printf("  Protocols: %v\n", protocols)
            
            // Get peer's addresses
            addrs := h.Peerstore().Addrs(identifyEvt.Peer)
            fmt.Printf("  Addresses: %v\n", addrs)
            
            // Get agent version
            if agent, err := h.Peerstore().Get(identifyEvt.Peer, "AgentVersion"); err == nil {
                fmt.Printf("  Agent: %s\n", agent)
            }
        }
    }
}
```

### Example 3: Custom Identify Handling

```go
func waitForProtocol(h host.Host, peerID peer.ID, protocol string) error {
    ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
    defer cancel()
    
    // Wait for identify to complete
    ids := h.Peerstore().Get(peerID, "IdentifyCompleted")
    if ids == nil {
        // Not identified yet, wait for event
        sub, _ := h.EventBus().Subscribe(new(event.EvtPeerIdentificationCompleted))
        defer sub.Close()
        
        for {
            select {
            case evt := <-sub.Out():
                if evt.(event.EvtPeerIdentificationCompleted).Peer == peerID {
                    goto CHECK_PROTOCOL
                }
            case <-ctx.Done():
                return fmt.Errorf("identify timeout")
            }
        }
    }
    
CHECK_PROTOCOL:
    // Check if peer supports protocol
    protocols, err := h.Peerstore().GetProtocols(peerID)
    if err != nil {
        return err
    }
    
    for _, p := range protocols {
        if p == protocol {
            return nil
        }
    }
    
    return fmt.Errorf("peer does not support protocol: %s", protocol)
}
```

### Example 4: Triggering Manual Push

```go
func addNewProtocolAndPush(h host.Host) {
    // Add a new protocol handler
    h.SetStreamHandler("/myapp/newfeature/1.0.0", func(s network.Stream) {
        defer s.Close()
        fmt.Println("New feature handler called!")
    })
    
    // Identify service automatically pushes, but you can also trigger manually
    // Get the identify service (if you have a reference)
    // ids.Push() // Pushes to all connected peers
    
    fmt.Println("New protocol registered and pushed to peers")
}
```

### Example 5: Accessing Observed Addresses

```go
func getObservedAddresses(h host.Host) []multiaddr.Multiaddr {
    // Get our observed addresses (what others see us as)
    observedAddrs := h.Peerstore().Get(h.ID(), "observed-addrs")
    
    if observedAddrs == nil {
        return nil
    }
    
    // Type assert to address slice
    addrs, ok := observedAddrs.([]multiaddr.Multiaddr)
    if !ok {
        return nil
    }
    
    return addrs
}

func printConnectivityStatus(h host.Host) {
    observed := getObservedAddresses(h)
    
    fmt.Println("Listen Addresses:", h.Addrs())
    fmt.Println("Observed Addresses:", observed)
    
    // If we have observed addresses, we might be publicly reachable
    if len(observed) > 0 {
        fmt.Println("Likely publicly reachable!")
    } else {
        fmt.Println("Might be behind NAT")
    }
}
```

---

## Best Practices

### 1. Always Wait for Identify

```go
// DON'T: Use connection immediately
conn, _ := host.Connect(ctx, peerInfo)
stream, _ := host.NewStream(ctx, peerID, "/myprotocol/1.0.0")

// DO: Wait for identify to complete
conn, _ := host.Connect(ctx, peerInfo)
<-identify.WaitForIdentify(conn) // Wait for identification
stream, _ := host.NewStream(ctx, peerID, "/myprotocol/1.0.0")
```

### 2. Handle Identify Failures Gracefully

```go
func connectWithRetry(h host.Host, peerInfo peer.AddrInfo) error {
    ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
    defer cancel()
    
    if err := h.Connect(ctx, peerInfo); err != nil {
        return fmt.Errorf("connection failed: %w", err)
    }
    
    // Wait for identify with timeout
    select {
    case <-identify.WaitForIdentify(h.Network().ConnsToPeer(peerInfo.ID)[0]):
        return nil
    case <-ctx.Done():
        return fmt.Errorf("identify timeout")
    }
}
```

### 3. Keep Protocol Versions Consistent

```go
// Use semantic versioning
const (
    MyProtocolV1 = "/myapp/protocol/1.0.0"
    MyProtocolV2 = "/myapp/protocol/2.0.0"
)

// Support multiple versions for backward compatibility
h.SetStreamHandler(MyProtocolV1, handleV1)
h.SetStreamHandler(MyProtocolV2, handleV2)
```

### 4. Monitor for Protocol Updates

```go
func watchForNewProtocols(h host.Host, peerID peer.ID) {
    ticker := time.NewTicker(30 * time.Second)
    defer ticker.Stop()
    
    lastProtocols, _ := h.Peerstore().GetProtocols(peerID)
    
    for range ticker.C {
        currentProtocols, _ := h.Peerstore().GetProtocols(peerID)
        
        // Compare for changes
        if !protocolsEqual(lastProtocols, currentProtocols) {
            fmt.Printf("Peer %s updated protocols: %v\n", peerID, currentProtocols)
            lastProtocols = currentProtocols
            
            // React to new protocols
            handleNewProtocols(currentProtocols)
        }
    }
}
```

### 5. Use Signed Peer Records

```go
// Generate and store signed peer record
func setupSignedPeerRecord(h host.Host) error {
    // Create peer record with our addresses
    rec := &peer.PeerRecord{
        PeerID: h.ID(),
        Addrs:  h.Addrs(),
        Seq:    uint64(time.Now().Unix()),
    }
    
    // Sign the record
    envelope, err := record.Seal(rec, h.Peerstore().PrivKey(h.ID()))
    if err != nil {
        return err
    }
    
    // Store in peerstore (will be included in identify)
    h.Peerstore().Put(h.ID(), "SignedPeerRecord", envelope)
    
    return nil
}
```

---

## Summary

The identify and identify push protocols are foundational to libp2p:

- **Identify**: Initial handshake, mutual authentication and capability discovery
- **Identify Push**: Efficient update mechanism for protocol/address changes
- **Automatic**: Both run automatically when using libp2p
- **Extensible**: Can be extended with custom metadata via signed peer records

Key takeaways:
1. Always wait for identify before using protocols
2. Monitor identify events for peer discovery
3. Use signed peer records for authenticated addresses
4. Understand push updates to react to peer changes
5. Handle failures and timeouts gracefully

These protocols enable libp2p's decentralized, heterogeneous network where peers can discover capabilities and adapt to changes dynamically. 