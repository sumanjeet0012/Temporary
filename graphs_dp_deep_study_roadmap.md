# Deep Graphs + Dynamic Programming Study Roadmap

## Goal

Build **deep algorithmic understanding** of Graph Data Structures and
Dynamic Programming---not just enough to solve interview-pattern
problems.

The target is that, for important algorithms, you can:

1.  Explain the problem they solve.
2.  Derive the algorithm rather than memorize it.
3.  Implement it from scratch.
4.  Prove or explain why it is correct.
5.  Analyze time and space complexity.
6.  Explain when it fails or when another algorithm is better.
7.  Recognize variations of the underlying idea in unfamiliar problems.

------------------------------------------------------------------------

# 1. Overall Learning Sequence

Follow this order:

``` text
Prerequisites
    ↓
MIT 6.006 — Foundations
    ↓
Graph Theory + Graph Algorithms
    ↓
Dynamic Programming
    ↓
CLRS — Deep theoretical reference
    ↓
MIT 6.046 — Advanced algorithm design
    ↓
Advanced Graph + DP
    ↓
LeetCode / Codeforces for mastery
```

Do **not** try to complete every resource cover-to-cover at maximum
depth.

Use each resource for a different purpose:

  --------------------------------------------------------------------------
  Resource                Role                       Depth
  ----------------------- -------------------------- -----------------------
  MIT 6.006               Main foundation course     High

  CLRS                    Mathematical/theoretical   High for relevant
                          reference                  chapters

  Sedgewick & Wayne       Implementation and         Medium
                          intuition                  

  Aditya Verma            DP supplementary           High for selected DP
                          explanation                topics

  MIT 6.046               Advanced algorithm design  High

  LeetCode                Pattern recognition +      High
                          practical problem solving  

  Codeforces              Unfamiliar/advanced        Later
                          problem solving            
  --------------------------------------------------------------------------

------------------------------------------------------------------------

# 2. Phase 0 --- Prerequisites

Before starting the main roadmap, make sure you understand:

-   Big-O, Big-Theta, Big-Omega
-   Recursion
-   Arrays
-   Linked lists
-   Stacks
-   Queues
-   Hash tables
-   Binary trees
-   Binary search
-   Sorting
-   Heaps / priority queues
-   Basic mathematical reasoning

## Depth required

You do **not** need expert-level knowledge here.

You should be able to:

-   Implement the data structures.
-   Analyze basic operations.
-   Understand recursion.
-   Calculate basic time complexity.

If you already know these well, move on quickly.

**Suggested time:** 3--7 days for review if already familiar.

------------------------------------------------------------------------

# 3. Phase 1 --- MIT 6.006: Introduction to Algorithms

## Primary resource

MIT OpenCourseWare:

https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-fall-2011/

Course materials:

https://courses.csail.mit.edu/6.006/fall11/notes.shtml

## How deeply should you study it?

**High depth, but not every exercise.**

MIT 6.006 should be your **main foundation course**.

Do not treat it as something to finish as quickly as possible. The
important outcome is learning how to think about algorithms.

## Recommended sequence

### A. Algorithm analysis

Study deeply:

-   Worst-case analysis
-   Big-O
-   Big-Theta
-   Recurrences
-   Amortized reasoning at a basic level
-   Running-time analysis

### B. Sorting and searching

Study:

-   Insertion sort
-   Merge sort
-   Quicksort
-   Counting/radix-style ideas if covered
-   Binary search
-   Lower/upper-bound style reasoning

Depth:

**Medium-high.**

You don't need to memorize every sorting algorithm, but you should
understand why different algorithms have different complexity.

### C. Heaps and priority queues

Study deeply enough to understand:

-   Heap invariant
-   Heap operations
-   Heap sort
-   Priority queues
-   Why heap operations are logarithmic

This becomes important later for Dijkstra.

### D. Hashing

Study:

-   Hash functions
-   Collision handling
-   Expected complexity
-   Hash tables

Depth:

**Medium.**

### E. Binary search trees

Study:

-   BST property
-   Search
-   Insert
-   Delete
-   Tree traversal
-   Complexity

Depth:

**Medium-high.**

### F. Divide and conquer

Study deeply:

-   Recurrence formulation
-   Merge sort
-   Binary search
-   Recursive algorithm analysis

This is important because it teaches a general algorithm-design
technique.

### G. Graph algorithms

Study **very deeply**.

You should understand:

-   Graph representations
-   Adjacency lists
-   Adjacency matrices
-   Directed vs undirected graphs
-   Weighted vs unweighted graphs
-   BFS
-   DFS
-   Connected components
-   Cycle detection
-   Topological sorting
-   Shortest paths

Do not move on until you can implement BFS and DFS without looking at
code.

### H. Dynamic programming

Study **very deeply**.

Understand:

-   Optimal substructure
-   Overlapping subproblems
-   Recursion → memoization
-   Memoization → tabulation
-   State definition
-   State transitions
-   Base cases
-   Evaluation order
-   Space optimization

This is the most important part of 6.006 for your goal.

## MIT 6.006 completion criterion

You do **not** need to solve every problem in the course.

You should be able to explain and implement the important algorithms
from the course without copying.

------------------------------------------------------------------------

# 4. Phase 2 --- Graphs Deep Dive

After the foundation, temporarily specialize in Graphs.

**Suggested time: 3--5 weeks**

## Stage 1: Graph fundamentals

Master:

-   Graph terminology
-   Vertices and edges
-   Degree
-   Directed/undirected graphs
-   Weighted/unweighted graphs
-   Adjacency list
-   Adjacency matrix
-   Edge list

Implement:

-   BFS
-   DFS
-   Iterative DFS
-   Recursive DFS

Then understand:

-   Connected components
-   Cycle detection
-   Bipartite graphs

### Depth

**Very high.**

BFS and DFS should become second nature.

------------------------------------------------------------------------

# 5. Graphs --- Topological Sorting and DAGs

Study:

-   Topological ordering
-   Kahn's algorithm
-   DFS-based topological sort
-   DAG properties
-   Shortest path in DAGs
-   Longest path in DAGs

Important insight:

> A DAG is one of the simplest places where Graphs and Dynamic
> Programming meet.

### Depth

**High.**

You should understand both the algorithm and why DAG structure allows
dynamic programming.

------------------------------------------------------------------------

# 6. Graphs --- Shortest Paths

Study in this order:

1.  BFS shortest path
2.  Dijkstra
3.  Bellman-Ford
4.  DAG shortest paths
5.  Floyd-Warshall

For each algorithm learn:

-   Problem definition
-   Assumptions
-   Algorithm
-   Correctness intuition
-   Complexity
-   Failure cases
-   When to choose it

## Dijkstra --- especially deep

You should be able to explain:

-   Why greedy selection works.
-   What the relaxation operation means.
-   Why negative edges break the standard algorithm.
-   Why a priority queue is useful.
-   Why the complexity depends on the graph representation.

### Depth

**Very high.**

Dijkstra is an important algorithmic building block.

------------------------------------------------------------------------

# 7. Graphs --- Minimum Spanning Trees

Study:

-   Spanning trees
-   Minimum spanning trees
-   Cut property
-   Kruskal
-   Union-Find / DSU
-   Prim

Understand:

-   Why Kruskal works.
-   Why DSU is needed.
-   Why Prim works.
-   Difference between MST and shortest-path trees.

### Depth

**High.**

Implement:

-   DSU from scratch
-   Kruskal
-   Prim

------------------------------------------------------------------------

# 8. Graphs --- Advanced Topics

After the fundamentals are strong, study:

## Strongly Connected Components

-   Kosaraju
-   Tarjan

## Bridges and Articulation Points

Understand:

-   Discovery times
-   Low-link values
-   Why the algorithms work

## Eulerian Paths/Circuits

Understand:

-   Necessary conditions
-   Construction

## Network Flow

Eventually study:

-   Max flow
-   Min cut
-   Ford-Fulkerson
-   Edmonds-Karp
-   Dinic

## Bipartite Matching

Study after understanding flow.

### Depth

For a first pass:

**Medium-high.**

You do not need to master every advanced graph algorithm immediately.

The priority should be:

``` text
BFS/DFS
    ↓
Topological Sort
    ↓
Shortest Paths
    ↓
MST + DSU
    ↓
SCC
    ↓
Bridges / Articulation Points
    ↓
Flow / Matching
```

------------------------------------------------------------------------

# 9. Phase 3 --- Dynamic Programming Deep Dive

**Suggested time: 5--8 weeks**

DP deserves more time than most other topics.

The goal is not to memorize "DP patterns."

The goal is to learn how to **design the state yourself**.

For every DP problem ask:

1.  What is my state?
2.  What does the state mean?
3.  What are the transitions?
4.  What are the base cases?
5.  In what order should states be calculated?
6.  Can I reduce memory?
7.  What is the complexity?

------------------------------------------------------------------------

# 10. DP Stage 1 --- Recursion → Memoization → Tabulation

Start with:

-   Fibonacci
-   Climbing Stairs
-   House Robber
-   Min Cost Climbing Stairs
-   Basic grid problems

For every problem solve it three ways:

``` text
Recursion
    ↓
Memoization
    ↓
Tabulation
    ↓
Space optimization
```

### Depth

**Very high.**

This transition is more important than the individual problems.

------------------------------------------------------------------------

# 11. DP Stage 2 --- Knapsack Family

Study deeply:

-   0/1 Knapsack
-   Unbounded Knapsack
-   Subset Sum
-   Equal Sum Partition
-   Count of Subsets
-   Target Sum
-   Coin Change

The important objective is to recognize the shared structure.

Do not memorize separate templates.

Ask:

> What is the state?

> What decision am I making?

> What smaller problem does each decision create?

### Depth

**Very high.**

------------------------------------------------------------------------

# 12. DP Stage 3 --- Sequence DP

Study:

-   Longest Common Subsequence
-   Longest Increasing Subsequence
-   Edit Distance
-   Longest Palindromic Subsequence
-   Palindrome-related DP

### Depth

**Very high.**

These problems are excellent for learning state design.

------------------------------------------------------------------------

# 13. DP Stage 4 --- Grid DP

Study:

-   Unique Paths
-   Minimum Path Sum
-   Obstacles
-   Multi-state grid problems
-   Grid problems with movement constraints

### Depth

**High.**

The goal is to understand how the dimensions of the state correspond to
the problem.

------------------------------------------------------------------------

# 14. DP Stage 5 --- Interval DP

Study:

-   Matrix Chain Multiplication
-   Burst Balloons
-   Palindrome Partitioning
-   Optimal BST

The key idea:

> The answer for an interval depends on how we split that interval.

### Depth

**High.**

This is a major conceptual jump from simple 1D DP.

------------------------------------------------------------------------

# 15. DP Stage 6 --- Tree DP

Now combine Graphs and DP.

Study:

-   DP on trees
-   Maximum independent set on a tree
-   Tree diameter DP
-   Rerooting DP

### Depth

**High.**

This is one of the most useful bridges between Graph algorithms and DP.

------------------------------------------------------------------------

# 16. DP Stage 7 --- DAG DP and Graph DP

Study:

-   DP on DAGs
-   Longest path in DAG
-   Shortest path in DAG
-   State-space graph DP

Understand that many DP problems can be viewed as:

> Finding an optimal value over a directed acyclic state graph.

This is an important conceptual insight.

------------------------------------------------------------------------

# 17. DP Stage 8 --- Bitmask DP

Study:

-   Bitmask representation
-   Subset DP
-   State compression
-   Traveling Salesman Problem

### Depth

**Medium-high initially.**

Increase depth later if you want competitive-programming-level
expertise.

------------------------------------------------------------------------

# 18. DP Stage 9 --- Advanced DP

Only after the above is comfortable:

-   Digit DP
-   Divide-and-conquer DP optimization
-   Convex Hull Trick
-   Knuth optimization
-   Other specialized DP optimizations

### Depth

**Medium initially.**

These are advanced topics. Do not rush into them.

------------------------------------------------------------------------

# 19. Aditya Verma --- How to Use It

Resource:

https://www.youtube.com/playlist?list=PL_z_8CaSLPWekqhdCPmFohncHwz8TY2Go

Use Aditya Verma mainly as a **second explanation for DP**.

Do not make it your primary algorithm theory course.

Recommended use:

``` text
MIT 6.006 / CLRS
        ↓
Understand DP concept
        ↓
Aditya Verma
        ↓
Compare the explanation
        ↓
Implement yourself
        ↓
Problems
```

### Depth

For the major DP families:

**High.**

For every single video:

**Not necessary.**

Skip duplicate/basic material once you understand it.

------------------------------------------------------------------------

# 20. CLRS --- How Deeply Should You Study It?

Resource:

https://mitpress.mit.edu/9780262046305/introduction-to-algorithms/

Do **not** read all of CLRS linearly just because you bought it.

Use it as your deep reference.

## Read deeply

Prioritize chapters/topics covering:

-   Algorithm analysis
-   Divide and conquer
-   Heaps
-   Hash tables
-   Binary search trees
-   Graph algorithms
-   BFS
-   DFS
-   Topological sorting
-   Minimum spanning trees
-   Shortest paths
-   Dynamic programming
-   Greedy algorithms

### Depth

For Graphs + DP:

**Very high.**

For unrelated chapters:

**Medium or skip initially.**

The goal is to understand the proofs and reasoning, not finish every
page.

------------------------------------------------------------------------

# 21. Sedgewick & Wayne --- How Deeply?

Resource:

https://sedgewick.io/books/algorithms/

Use this primarily for:

-   Implementation
-   Visualization
-   Practical intuition
-   Graph algorithms
-   Performance comparisons

### Depth

**Medium-high.**

You don't need to study it independently from MIT/CLRS.

Use it when you want a different explanation or implementation
perspective.

------------------------------------------------------------------------

# 22. Phase 4 --- MIT 6.046

After Graphs + DP are strong, study:

MIT 6.046:

https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/

This course is where you start thinking more seriously about **algorithm
design**.

Study deeply:

-   Divide and conquer
-   Dynamic programming
-   Greedy algorithms
-   Randomized algorithms
-   Amortized analysis
-   Advanced complexity ideas
-   Advanced algorithm design

### Depth

**High.**

You don't necessarily need every assignment.

Focus on understanding the design techniques.

------------------------------------------------------------------------

# 23. Problem-Solving Strategy

Do not start with hundreds of LeetCode problems.

Use a layered approach.

## For every new algorithm

### Step 1 --- Theory

Understand the algorithm.

### Step 2 --- Implement

Write it from scratch.

### Step 3 --- Analyze

Write down:

``` text
Time:
Space:
Invariant:
Why correct:
Failure conditions:
```

### Step 4 --- Easy problems

Solve 3--5 problems.

### Step 5 --- Medium problems

Solve 5--10 problems.

### Step 6 --- Hard problems

Solve a smaller number of carefully selected problems.

### Step 7 --- Re-derive

A few days later, implement the algorithm without notes.

This last step is extremely important.

------------------------------------------------------------------------

# 24. LeetCode Strategy

Use LeetCode as a **testing environment**, not as your textbook.

Suggested progression:

``` text
Learn BFS
   ↓
Implement BFS
   ↓
3 easy problems
   ↓
5 medium problems
   ↓
1–2 difficult problems
   ↓
Move to DFS
```

For DP:

``` text
Learn 1D DP
   ↓
Implement
   ↓
5–10 problems
   ↓
Learn 2D DP
   ↓
5–10 problems
   ↓
Knapsack
   ↓
Sequence DP
   ↓
Interval DP
```

Do not solve 100 random DP problems.

Solve problems that teach **different state-design ideas**.

------------------------------------------------------------------------

# 25. When to Move On

Use mastery checkpoints rather than a calendar alone.

## Graph checkpoint

Before moving away from Graph fundamentals, you should be able to
implement without help:

-   BFS
-   DFS
-   Connected components
-   Cycle detection
-   Bipartite checking
-   Topological sort
-   Dijkstra
-   Bellman-Ford
-   Kruskal
-   DSU
-   Prim

And explain the complexity and assumptions of each.

------------------------------------------------------------------------

## DP checkpoint

You should be able to take an unfamiliar medium-level DP problem and
systematically ask:

``` text
What are the choices?
        ↓
What information affects the future?
        ↓
That information becomes the state
        ↓
What are the transitions?
        ↓
What are the base cases?
        ↓
What is the evaluation order?
```

If you can do this, you're making real progress.

------------------------------------------------------------------------

# 26. Suggested 12--16 Week Schedule

This assumes roughly **1.5--3 hours/day** of focused study.

## Weeks 1--2

### MIT 6.006 foundation

Focus on:

-   Complexity
-   Recursion
-   Sorting
-   Searching
-   Heaps
-   Hashing
-   Trees

Depth: **Medium-high**

------------------------------------------------------------------------

## Weeks 3--5

### Graph fundamentals

Study:

-   Representation
-   BFS
-   DFS
-   Components
-   Cycles
-   Bipartite
-   Topological sort
-   DAGs

Depth: **Very high**

------------------------------------------------------------------------

## Weeks 6--7

### Advanced core Graph algorithms

Study:

-   Dijkstra
-   Bellman-Ford
-   Floyd-Warshall
-   MST
-   Kruskal
-   DSU
-   Prim

Depth: **Very high**

------------------------------------------------------------------------

## Week 8

### Advanced Graphs

Study:

-   SCC
-   Bridges
-   Articulation points
-   Eulerian paths

Depth: **Medium-high**

Do not get stuck here for weeks.

------------------------------------------------------------------------

## Weeks 9--10

### DP foundations

Study:

-   Recursion
-   Memoization
-   Tabulation
-   1D DP
-   2D DP
-   Knapsack

Depth: **Very high**

------------------------------------------------------------------------

## Weeks 11--12

### Advanced DP patterns

Study:

-   Sequence DP
-   Grid DP
-   Interval DP

Depth: **Very high**

------------------------------------------------------------------------

## Weeks 13--14

### Tree/DAG/Bitmask DP

Study:

-   Tree DP
-   Rerooting
-   DAG DP
-   Bitmask DP
-   TSP

Depth: **High**

------------------------------------------------------------------------

## Weeks 15--16

### MIT 6.046 + consolidation

Start:

-   Advanced DP
-   Greedy algorithms
-   Divide and conquer
-   Randomization
-   Algorithm design

At the same time, revisit weak Graph/DP areas.

------------------------------------------------------------------------

# 27. What "Deep" Means for Different Resources

Do not give every resource equal effort.

## MIT 6.006

**8/10 depth**

Understand the concepts and implement important algorithms.

## Graph algorithms

**10/10 depth**

This is one of your two primary goals.

## Dynamic programming

**10/10 depth**

This is your other primary goal.

## CLRS

**9/10 depth for Graph + DP chapters**

Use it for proofs, analysis, and deeper understanding.

## Sedgewick

**6/10 depth**

Use it as a complementary implementation resource.

## Aditya Verma

**8/10 depth for selected DP families**

Use it to strengthen DP intuition.

## MIT 6.046

**8/10 depth**

Study after the foundation rather than before.

## LeetCode

**7/10 depth, not maximum volume**

Focus on representative problems.

## Codeforces

**6/10 initially → 9/10 later**

Use it after you can comfortably solve standard problems.

------------------------------------------------------------------------

# 28. The Most Important Principle

Do not optimize for:

> "How quickly can I finish this course?"

Optimize for:

> "Can I reconstruct the algorithm from first principles?"

For example, don't just memorize Dijkstra:

``` text
priority_queue
relax edges
repeat
```

Be able to reason:

``` text
Why can I finalize the closest vertex?
Why does non-negative weight matter?
Why does relaxation work?
Why does the priority queue improve efficiency?
What invariant is maintained?
```

Likewise, don't memorize:

``` text
dp[i][j] = ...
```

Instead learn to derive:

``` text
What does i represent?
What does j represent?
What decisions exist?
What information about the past affects the future?
What is the smallest state containing that information?
```

That is the difference between **learning algorithms** and **learning
algorithmic thinking**.

------------------------------------------------------------------------

# 29. Final Resource Order

Bookmark these in this order:

### 1. MIT 6.006

https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-fall-2011/

**Main foundation.**

↓

### 2. Graphs deep dive

Use MIT + CLRS + Sedgewick.

**Primary specialization.**

↓

### 3. Dynamic Programming

Use MIT + CLRS + Aditya Verma.

**Primary specialization.**

↓

### 4. CLRS

https://mitpress.mit.edu/9780262046305/introduction-to-algorithms/

**Deep theoretical reference.**

↓

### 5. MIT 6.046

https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/

**Advanced algorithm design.**

↓

### 6. LeetCode

**Structured practice.**

↓

### 7. Codeforces

**Advanced/unfamiliar problem solving.**

------------------------------------------------------------------------

# 30. The End Goal

After completing this roadmap, you should not merely have a list of
algorithms memorized.

You should be comfortable seeing a new problem and thinking:

``` text
What is the underlying structure?

Graph?
Tree?
DAG?
Sequence?
Interval?
State space?

        ↓

What choices exist?

        ↓

What information determines the future?

        ↓

Can I formulate a recurrence?

        ↓

Can I exploit a graph structure?

        ↓

Can I prove the approach?

        ↓

What is the complexity?

        ↓

Can I optimize it?
```

That is the level of understanding you should aim for.

**Do not rush the roadmap. Depth beats completion speed.**
