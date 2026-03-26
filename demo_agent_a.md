# goose-libp2p Demo — Agent A
# Run with: goose run mcp/demo_agent_a.md
# This demonstrates Goose using the goose-libp2p MCP extension to operate
# a real libp2p peer node.

Please complete the following steps using the goose-libp2p tools:

1. Call `start_peer` with port=9000 and nick="AgentA" to start a libp2p peer node.

2. Call `get_peer_info` and show me the full multiaddr — I will use it to connect from AgentB.

3. Call `subscribe_topic` with topic="/goose/tasks" to subscribe to the task channel.

4. Call `subscribe_topic` with topic="/goose/results" to subscribe to the results channel.

5. Call `publish_message` with topic="/goose/tasks" and message="Hello from AgentA! I need help writing a Python function that reverses a linked list."

6. Wait 5 seconds, then call `get_messages` with topic="/goose/tasks" to see if the message was received.

7. Call `get_node_status` to show the full health snapshot of the node.

8. Call `list_peers` to show all connected peers.

After completing these steps, display a summary showing:
- The peer ID and multiaddr for AgentA
- The full multiaddr command another agent should use to connect
- The message that was published to /goose/tasks
