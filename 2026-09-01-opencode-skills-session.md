# OpenCode Skills Session — Creating Custom Agent Skills

**Date:** 2026-09-01 | **Session:** Built 5 custom skills in `~/.config/opencode/skills/` + did a graphs DSA deep dive

## What we covered

- How opencode agent skills work (`SKILL.md` + frontmatter `name`/`description`, discovery from `~/.config/opencode/skills/<name>/SKILL.md`)
- Which community skill collections exist (anthropics/skills, addyosmani/agent-skills, ComposioHQ/awesome-claude-skills)
- A full DSA study guide deep-dive on Graphs (Java)
- A simple explanation of Dynamic Programming
- Created 5 new skills, listed below

## Key takeaways

### Skills created (all in `~/.config/opencode/skills/`)

1. **explain-simply** — explains any technical topic: one-liner → analogy → plain explanation → worked code example → ASCII diagram → misconceptions → self-test
2. **dsa-deep-dive** — deep-researches a DSA topic and produces a 9-section study guide (mastery definition, must-know checklist, ranked resources, practice ladder, tips/tricks, beginner + advanced confusions, what's next, interview corner)
3. **code-review-critique** — reviews code/diffs across 5 axes (correctness, edge cases, complexity, security, craft), findings ranked 🔴/🟡/🔵 with evidence, improved version, lessons
4. **explain-by-analogy** — "ELI5" fallback: vivid story (no jargon) → mapping table → where the analogy breaks → one-liner → click-check question
5. **session-notes-to-github** — this note's creator: writes a `YYYY-MM-DD-topic.md` from the session and pushes to `sumanjeet0012/temporary`

### Dynamic Programming one-liner
Solving a big problem by breaking it into small ones, writing answers down, never solving the same subproblem twice. Top-down (memoization) vs bottom-up (tabulation). Fibonacci naive = O(2^n), DP = O(n).

### Graphs (Java) — key facts
- Traversal O(V+E); BFS for unweighted shortest path, DFS for reachability/cycles/topo
- Dijkstra fails on negative weights → Bellman-Ford; negative cycles = undefined shortest path
- Topological sort: DFS post-order reversal or Kahn's BFS (indegree)
- Java: `ArrayDeque` for queues (not LinkedList), `Integer.compare` in PQ comparator (avoid overflow)
- Start with VisuAlgo (visualgo.net/en/dfsbfs), then CP-Algorithms, USACO Guide

## Resources mentioned

- https://github.com/anthropics/skills
- https://github.com/addyosmani/agent-skills
- https://github.com/ComposioHQ/awesome-claude-skills
- https://visualgo.net/en/dfsbfs
- https://cp-algorithms.com/graph/depth-first-search.html
- https://usaco.guide/bronze/intro-graphs
- https://neetcode.io

## Open questions / next steps

- Restart opencode to load the new skills (discovery happens at session start)
- Skill candidates for later: system-design-primer, concept-quizzer, git-rescue, error-message-decoder, static-site-debugger
