# Decentralized Multi-Agent Goose Demo over GossipSub

## Demo Title
**One Goose agent breaks down a real engineering task, delegates half to another Goose agent over a decentralized GossipSub topic, and both agents validate the merged solution before proceeding.**

---

## Demo Summary
This demo showcases a **distributed multi-agent workflow** built on top of:
- **Goose** as the AI agent/orchestrator
- **Your MCP server** as the bridge between Goose and the Python peer
- **Universal Connectivity / libp2p GossipSub** as the decentralized communication layer

Instead of only showing that Agent A can send a message to Agent B, this demo shows something more meaningful:
1. A **big engineering task** is given to Agent A
2. Agent A **splits the task** and delegates a real subtask to Agent B
3. Agent B performs its part of the work and publishes the result
4. Both agents use the **same shared task topic** to discuss whether the combined solution is correct
5. Agent A finalizes only after both agents agree the solution is good enough

This makes the demo feel like a **real decentralized multi-agent task execution and validation workflow**, not just a chat message exchange.

---

## Core Demo Idea
### You tell Agent A:
> Solve this issue, split the work with Agent B, collaborate over a shared GossipSub topic, and only proceed after both of you validate the final solution.

### Agent roles
- **Agent A** = Solver / Main orchestrator
- **Agent B** = Reviewer / Validator / QA partner

### High-level behavior
- Agent A receives the full task
- Agent A keeps one part of the work for itself
- Agent A sends a structured work assignment to Agent B
- Agent B joins the shared task topic and works on the delegated half
- Both agents post partial results to the same topic
- Both agents discuss whether the merged solution is sufficient
- Agent A returns the final answer only after validation

---

## Recommended Topic Structure
Use two topic types:

### 1. Agent B inbox topic
```text
agents/inbox/agent-b
```
This is the fixed topic that Agent B listens to before the demo starts.

### 2. Shared task topic
```text
agents/task/<task_id>
```
This is the task-specific topic where the real collaboration happens.

### Why this structure works
- Agent B always knows where to listen first
- Agent A can dynamically create a task-specific collaboration space
- The audience can clearly see the difference between **task handoff** and **task collaboration**

---

## Exact Workflow

### Step 1 — Start Agent B in listener mode
Before the demo starts, Agent B should be told to:
1. Subscribe to `agents/inbox/agent-b`
2. Wait for one incoming task assignment
3. Read the task assignment payload
4. Subscribe to the shared task topic from the payload
5. Complete its assigned subtask
6. Publish results to the shared task topic
7. Participate in the validation discussion
8. Stop when the task is approved or completed

---

### Step 2 — Give a big task to Agent A
Example prompt:

> Investigate why topic messages are not reliably appearing after peer connection. Propose a fix, delegate the validation and edge-case review to Agent B, collaborate over a shared task topic, and only finalize once both of you agree the solution is sufficient.

This is a good task because it naturally splits into:
- **Agent A work:** root cause analysis + proposed fix
- **Agent B work:** validation plan + reviewer critique + edge cases

---

### Step 3 — Agent A sends a task assignment to Agent B inbox
Published to:
```text
agents/inbox/agent-b
```

Example payload:

```json
{
  "type": "task_assign",
  "task_id": "task-123",
  "from_agent": "agent-a",
  "shared_topic": "agents/task/task-123",
  "task_summary": "Investigate why topic messages are not reliably appearing after peer connection.",
  "your_subtask": "Review the proposed fix, identify missing edge cases, and create a minimal validation plan.",
  "my_subtask": "I will analyze root cause and propose the implementation fix."
}
```

This message tells Agent B:
- what the overall task is
- what part B should do
- which shared topic to join

---

### Step 4 — Both agents collaborate on the same task topic
Shared topic:
```text
agents/task/task-123
```

#### Example partial result from Agent A
```json
{
  "type": "partial_result",
  "task_id": "task-123",
  "from_agent": "agent-a",
  "content": "I believe the issue is that subscription/join state is not established before publish or expectation logic."
}
```

#### Example partial result from Agent B
```json
{
  "type": "partial_result",
  "task_id": "task-123",
  "from_agent": "agent-b",
  "content": "Missing validation cases: late join, reconnect after disconnect, and topic isolation."
}
```

---

### Step 5 — Validation discussion on the same topic
After both partial results are posted, Agent A and Agent B discuss whether the combined solution is sufficient.

#### Validation request from Agent A
```json
{
  "type": "validation_request",
  "task_id": "task-123",
  "from_agent": "agent-a",
  "question": "If we subscribe earlier and confirm join success before publish, do you think the solution is complete?"
}
```

#### Validation reply from Agent B
```json
{
  "type": "validation_reply",
  "task_id": "task-123",
  "from_agent": "agent-b",
  "answer": "Yes, provided you also test reconnect and confirm topic isolation. Otherwise the fix is incomplete."
}
```

This creates the most interesting part of the demo:
**the agents do not just exchange outputs—they validate the merged solution together before proceeding.**

---

### Step 6 — Final consensus message
Once both agents agree, Agent A posts a completion message:

```json
{
  "type": "task_complete",
  "task_id": "task-123",
  "from_agent": "agent-a",
  "final_summary": "Root cause identified, fix proposed, reviewer-approved after adding validation for late join, reconnect, and topic isolation.",
  "status": "approved"
}
```

Then Agent A presents the final answer to the user.

---

## Why This Demo Is Strong

### 1. It shows real work, not just transport
The agents are not only sending messages—they are:
- decomposing a real task
- doing separate pieces of work
- merging results
- validating correctness

### 2. It shows decentralized collaboration
The communication is happening over **GossipSub topics**, not through a central server.

### 3. It is easy to explain live
You can explain the system like this:
- **Inbox topic** = the address where Agent B receives assignments
- **Shared task topic** = the collaboration room where both agents work together

### 4. It demonstrates a believable multi-agent workflow
This looks like a real engineering collaboration pattern:
- solver + reviewer
- implementation + validation
- proposal + critique + approval

---

## Best Real-World Task Type for This Demo
The best task format is:

### **Solve + Validate**
Where:
- **Agent A = Solver**
- **Agent B = Validator / Reviewer**

Examples:
- Agent A finds bug cause, Agent B designs validation checks
- Agent A proposes architecture, Agent B critiques risks
- Agent A drafts fix, Agent B verifies if it is complete
- Agent A handles implementation logic, Agent B handles edge cases and testing

This split is realistic, easy to follow, and very demo-friendly.

---

## Recommended Demo Prompt for Agent A
```text
Solve this issue. Split the work with Agent B.
Send Agent B a task assignment via agents/inbox/agent-b.
Use a shared task topic for collaboration.
Once both partial results are ready, discuss whether the solution is sufficient before finalizing.
```

---

## Recommended Demo Prompt for Agent B
```text
You are agent-b, the reviewer/validator.
1. Subscribe to agents/inbox/agent-b
2. Wait for one task assignment
3. When you receive it, subscribe to the shared_topic from the message
4. Complete your assigned subtask
5. Publish your findings to the shared_topic
6. Participate in validation discussion on that same topic
7. Stop when the task is approved or when asked to stop
```

---

## Minimal MCP Tools Needed
To support this workflow well, your MCP server should ideally expose:

- `subscribe_topic(topic)`
- `publish_message(topic, message)`
- `wait_for_message(topic, timeout)`
- `get_messages(topic)`

Optional but useful later:
- `publish_structured_message(topic, payload)`
- `get_task_state(task_id)`
- `list_topics()`
- `shutdown_peer()`

---

## Final One-Line Pitch
> **One Goose agent breaks down a real engineering task, delegates half to another Goose agent over a decentralized GossipSub topic, and both agents validate the merged solution before proceeding.**

---

## Final Recommendation
For the laptop demo, this is the best architecture:

- **Agent A receives the big task**
- **Agent A delegates a real subtask to Agent B**
- **Agent B joins the shared task topic**
- **Both agents publish partial work to the same topic**
- **Both agents discuss whether the solution is correct**
- **Agent A finalizes only after agreement**

This is simple enough to run live, but advanced enough to feel genuinely impressive.
