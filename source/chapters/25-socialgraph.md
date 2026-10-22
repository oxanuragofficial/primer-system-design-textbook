%derived Notebook chapter 12.5 (social network data structures: Person, Person Server, Lookup Service, Graph Service, BFS for shortest path, sharding persons across servers, scale table)
%added bidirectional BFS and its cost analysis, adjacency-list storage, graph partitioning trade-offs, caching hot neighbourhoods, privacy filtering, degrees-of-separation limits, and graph databases as an alternative
# Case Study: Social Graph and Shortest Path {#ch-socialgraph}

::: objectives
After this chapter you can:

- model a social network as a graph and estimate its storage and query load;
- explain why a single-machine breadth-first search fails at scale;
- design a sharded person store with a lookup service;
- run and cost a bidirectional BFS across shards, with caching and limits;
- discuss privacy, hot nodes and graph-database alternatives.
:::

::: prereq
Chapters {ch:ch-ds}, {ch:ch-estimation}, {ch:ch-distdata} (sharding) and {ch:ch-cache}.
:::

## Problem and requirements {#sec-sg-req}

**The problem.** Given two users, find the **shortest path** of friendships connecting them ("how many degrees of separation?"), for a network with hundreds of millions of users, so that the data does not fit on one machine.

**Functional requirements.** Given user A and user B, return a shortest path (or its length) if one exists within a limit. Friend relations are **undirected** (mutual). Friends can be added and removed.

**Non-functional requirements.** Low latency (hundreds of milliseconds to a few seconds), high availability for reads, and scalability across many machines. **Privacy** applies: only traverse friendships the requester may see.

**Scope.** We assume an unweighted, undirected graph, an approximate or length-limited answer is acceptable (say up to 6 hops), and the graph store is already sharded. Weighted paths, recommendations ("people you may know") and real-time graph updates in search results are extensions.

## Scale estimate {#sec-sg-scale}

Table[sg-scale]: Assumptions and derived quantities (the notebook gives the style of calculation; the figures are assumptions).

| Quantity | Assumption | Derived |
|---|---|---|
| Users | 400 million | |
| Friends per user | 300 average (heavy tail: some have 5,000+) | 1.2×10¹¹ adjacency entries (each friendship stored twice) |
| Entry size | 8-byte id | ≈ 1 TB of adjacency data (more with metadata) |
| Queries | 100 million shortest-path requests per month | ≈ 40 per second average |
| Branching | average degree d = 300 | level k holds about 300ᵏ users |

**What the numbers say.** About a terabyte of adjacency lists does not fit in one machine's memory comfortably but fits in a cluster of 10 to 50 machines with replication. The read rate is modest; the *cost per query* is the problem. With d = 300, level 1 has 300 users, level 2 has about 90,000, level 3 about 27 million (so most of a country), and a path of length 6 would need to touch nearly the whole network. Plain BFS from A to depth 6 is hopeless; we need to be clever.

## Why naive BFS fails {#sec-sg-bfs}

Breadth-first search explores all neighbours of the start, then their neighbours, level by level, and finds a shortest path in an unweighted graph. On one machine the notebook's `shortest_path` uses a queue of nodes to visit and a `visited` set, following `friend_ids` to neighbours. On a sharded graph each step "fetch this person's friend list" is a **network call** to whichever server holds the person, found through a **Lookup Service** (person id to Person Server). Exploring millions of nodes means millions of calls.

**Bidirectional BFS** is the key optimisation. Search from A and from B simultaneously, expanding the smaller frontier each time, and stop when the frontiers meet.

{{fig sg-bibfs | Bidirectional BFS. Each side expands only a few levels, so the explored region is two small balls instead of one huge one.}}

**Cost.** If the shortest distance is L and the branching factor is d, one-sided BFS visits about dᴸ nodes, bidirectional visits about 2·d^(L/2). For d = 300 and L = 4: one-sided 300⁴ = 8.1×10⁹ versus bidirectional 2 × 300² = 180,000. That difference (five orders of magnitude) turns an impossible query into a feasible one. For L = 6 the numbers are 7×10¹⁴ versus 5.4×10⁷, still heavy, which is why production systems cap the depth, use caching, or precompute.

## Architecture {#sec-sg-arch}

{{fig sg-arch | Components. The Graph Service runs the search; the Lookup Service finds the shard of each person; Person Servers hold adjacency lists.}}

The notebook's components, with their roles:

- **Person Server**: holds a partition of persons, each with an id, name and list of friend ids (the adjacency list).
- **Lookup Service**: maps `person_id` to the Person Server that stores it, as an in-memory map or by a fixed hash function.
- **Graph Service (User Graph Service)**: receives (A, B), performs bidirectional BFS, batching lookups and friend-list fetches, and returns the path.
- **Client/API**: authenticates the requester and applies privacy rules.

**Sharding the graph.** Partition persons across servers by **hash of id** (balanced, trivial lookup, but neighbours are scattered, so a traversal touches many servers), or by **community/locality** (people who are friends tend to share a shard, reducing cross-server calls, but needs a graph-partitioning algorithm and can become unbalanced and hard to maintain). Start with hash partitioning plus caching; consider locality-aware partitioning when the cross-shard traffic dominates cost.

**Batching.** Instead of fetching one friend list at a time, expand a whole frontier level: group the frontier ids by shard and send one batched request per shard. A frontier of 90,000 ids across 50 shards becomes 50 requests, not 90,000, turning latency from "number of nodes" into "number of levels times one round trip".

## Algorithm in detail {#sec-sg-algo}

```
function shortest_path(a, b, max_depth):
    if a == b: return [a]
    seen_a = {a: None}; seen_b = {b: None}
    frontier_a = {a};   frontier_b = {b}
    for depth in 1..max_depth:
        # expand the smaller frontier
        if len(frontier_a) <= len(frontier_b):
            frontier_a = expand(frontier_a, seen_a)
        else:
            frontier_b = expand(frontier_b, seen_b)
        meet = frontier_a ∩ frontier_b   (or seen_a ∩ seen_b)
        if meet not empty:
            return build_path(meet.any, seen_a, seen_b)
    return NOT_FOUND

function expand(frontier, seen):
    new = {}
    for shard, ids in group_by_shard(frontier):      # batched, parallel
        for person, friends in shard.get_friends(ids):
            for f in friends:
                if f not in seen:
                    seen[f] = person                  # parent pointer
                    new.add(f)
    return new
```

**Why correct.** Each expansion adds one level around its source; the first time the two balls share a node, the sum of their radii is the shortest distance (BFS levels are by increasing distance). To get exactly the shortest path when frontiers are expanded unevenly, finish the level in progress before returning. The parent pointers in `seen` rebuild the path from both halves.

**Complexity.** Time is proportional to nodes and edges examined (bounded by the two balls); memory is the size of both seen sets. Both are controlled by `max_depth` and by the **frontier size cap**.

::: worked
**Dry run.** Friendships: A–C, C–D, D–E, E–B, A–X, X–Y. Search A to B; seen sets start as {A} and {B}. Step 1: frontiers tie in size, so expand A: frontier {C, X}. Step 2: B's frontier (1) is smaller, expand it: {E}; no overlap. Step 3: expand B's side again: {D}; no overlap. Step 4: expand D, reaching C, which is already in A's seen set: the frontiers meet at C. Parent pointers give A, C on one side and C, D, E, B on the other: path A, C, D, E, B (length 4). The branch X, Y was never explored beyond X.
:::

## Caching, hot nodes and limits {#sec-sg-cache}

- **Cache adjacency lists** of popular users in memory; a celebrity with millions of friends appears in many paths. Use an LRU cache (Chapter {ch:ch-cache}) in front of Person Servers.
- **Hot nodes** can poison the search: expanding a user with 5 million friends explodes the frontier. Strategies: cap the number of friends expanded per node, skip "super-nodes" unless the path needs them (and prefer paths through ordinary users), or precompute hub-to-hub distances.
- **Limits**: maximum depth (6), maximum nodes visited, and a deadline. Return "not found within limit" rather than run unbounded: this is an *approximate* answer, which must be stated.
- **Result caching**: cache (A, B) answers briefly, since the graph changes slowly and popular pairs repeat.
- **Precomputation**: offline jobs can compute landmarks (distances from some hub nodes) giving bounds that prune the search; or maintain 2-hop neighbour sets for active users at a storage cost.

## Privacy, consistency and operations {#sec-sg-ops}

**Privacy.** Do not reveal connections that the requester should not see. Each edge may carry visibility (public, friends only). The Graph Service must filter edges by what the requester can see *during* traversal, or a path can leak existence of a private friendship. This can make the "shortest" path depend on the viewer.

**Consistency.** Friendship changes are written to the owning shard(s); because each friendship is stored on both endpoints, which may live on different shards, an update touches two shards and can be briefly inconsistent (one side present). Writes use an idempotent two-step update with repair jobs (or a durable queue) to converge; reads tolerate brief staleness (Chapter {ch:ch-distdata}).

**Failures.** A Person Server down: replicas serve reads; if a shard is unavailable return a partial or failed result rather than a wrong "no path". *Distinguish "no path exists" from "could not search"*.

**Operations.** Metrics: p50/p99 latency, nodes visited per query, cache hit ratio, batched request fan-out, percentage of limited or failed searches, hot-node events. Cost is dominated by memory for the adjacency data and cache.

## Alternatives and trade-offs {#sec-sg-alt}

Table[sg-alt]: Decisions and alternatives.

| Decision | Chosen | Alternative | Reason | Revisit if |
|---|---|---|---|---|
| Search | Bidirectional BFS, depth-limited | One-sided BFS | Orders of magnitude fewer nodes | Tiny graph |
| Partition | Hash of person id | Community-aware | Simplicity and balance | Cross-shard cost dominates |
| Storage | Adjacency lists in sharded KV or memory | Graph database | Predictable scale | Rich graph queries needed |
| Expansion | Batched per shard | Node-by-node | Latency | Single shard |
| Hubs | Cap or skip super-nodes | Expand all | Bounded cost | Exact answers required |

**Follow-ups.** *Mutual friends count?* Intersect two adjacency lists (sorted lists, merge, or a bitmap). *Friend suggestions?* Count friends-of-friends not already friends, ranked by number of mutual friends, precomputed offline. *Weighted edges?* Use Dijkstra or A* with a heuristic. *Billions of users?* Locality-aware sharding, in-memory graph, precomputed landmarks.

::: failure
**Failure modes (summary).** Exploding frontier at a hub; cross-shard call storms; stale or half-written friendships; wrong "no path" during shard outage; privacy leak through paths; memory exhaustion from large seen sets.
:::

::: misconception
- *"BFS is cheap."* It is exponential in depth with a high branching factor.
- *"Sharding makes the graph query parallel for free."* Cross-shard traversals add latency unless batched.
- *"Not found means no connection."* It may mean the limit was reached.
:::

::: interview
**Q1. Why bidirectional BFS?** It explores two balls of radius L/2 instead of one of radius L: about 2·d^(L/2) rather than dᴸ nodes.

**Q2. How do you traverse a sharded graph efficiently?** Lookup service plus batching of each level by shard, with caching of hot lists.

**Q3. How do you handle celebrities?** Cap or skip super-nodes, cache their lists, precompute hubs.

**Q4. How do you keep privacy?** Filter edges by viewer permission during traversal.
:::

::: exercise
1. With average degree 200, compute nodes explored by one-sided BFS and by bidirectional BFS for distance 4 and for distance 6.
2. Suppose 60 shards and a frontier of 120,000 ids. How many requests with batching versus without?
3. Show that a friendship stored on two shards needs an idempotent update. What breaks otherwise?
4. Give a limit policy that yields a bounded response time.

**Answers.**
1. L = 4: 200⁴ = 1.6×10⁹ vs 2×200² = 80,000. L = 6: 200⁶ = 6.4×10¹³ vs 2×200³ = 1.6×10⁷.
2. Batched: at most 60 requests per level (per-shard); unbatched: 120,000.
3. A retry after a partial failure could add a duplicate edge or leave one direction missing; an idempotent "add friend (a,b)" on both sides plus repair makes retries safe.
4. Maximum depth 6, a cap on nodes (say 5 million) and a deadline (say 1 second); return not-found-within-limit with the reason.
:::

::: summary
- Social graphs have high branching, so one-sided BFS is infeasible beyond a few hops.
- Bidirectional BFS reduces the work from dᴸ to about 2·d^(L/2).
- Shard by person id; use a lookup service, batched level expansion and caches.
- Limit depth and handle hubs; make approximate answers explicit.
- Respect privacy during traversal; keep friendship writes idempotent.
:::

::: revision
- [ ] I can explain why bidirectional BFS is cheaper and compute the gain.
- [ ] I can describe the roles of Person Server, Lookup Service and Graph Service.
- [ ] I can explain batching per shard and hub handling.
:::
