%derived Notebook chapter 12.6 (key-value cache for search queries: Query API server, Reverse Index Service, Document Service, Memory Cache with LRU using a linked list and hash table, cache update, scale table)
%added distributed cache sharding with consistent hashing, hot-key and stampede protection, TTL and invalidation, negative caching, thread-safe LRU, approximations such as sampled LRU and TinyLFU, and measuring hit ratio
# Case Study: A Query Cache with LRU {#ch-querycache}

::: objectives
After this chapter you can:

- explain why a search service caches whole queries and estimate the hit ratio and memory required;
- implement an LRU cache with a hash map and doubly linked list in O(1);
- design a distributed, sharded cache and keep it consistent enough;
- prevent stampedes and hot-key overload, and choose TTLs and invalidation;
- test and monitor a cache.
:::

::: prereq
Chapters {ch:ch-ds} (hash tables, linked lists), {ch:ch-cache}, {ch:ch-distdata} (consistent hashing).
:::

## Problem and requirements {#sec-qc-req}

**The problem.** A search service receives about 40,000 queries per second (the notebook's scale). Each query runs a costly pipeline: parse and normalise, look up postings in the reverse index, rank, fetch titles and snippets. Many queries repeat ("weather", a trending news item). Design a **cache of query results** so repeated queries are served quickly and cheaply.

**Functional requirements.** Given a query string, return cached results if present, else compute, store and return. Evict old entries when full. Allow fast lookups.

**Non-functional requirements.** Very low latency (cache hit well under 10 ms), high hit ratio, high availability (a cache failure must degrade performance, not correctness), reasonable freshness (results may be minutes old).

**Scope.** We cache results for the *query string after normalisation*. Out of scope: personalised results (they fragment the key space; mention as an extension) and partial result caching.

## Scale and sizing {#sec-qc-scale}

Table[qc-scale]: Assumptions and derived quantities.

| Quantity | Assumption | Derived |
|---|---|---|
| Queries | 40,000 per second peak | 100 billion per month |
| Result size | 10 results × (title + snippet + url) ≈ 4 KB | |
| Distribution | Zipf-like: top 1% of queries produce about 50% of traffic | caching the head is very effective |
| Cache size | 100 million entries × 4 KB | ≈ 400 GB across the cache cluster |
| Hit ratio target | 60 to 80% | misses cut from 40,000 to 8,000 to 16,000 per second |

**Why a cache helps so much.** Query popularity is heavily skewed: a small head of queries is asked over and over, with a long tail asked once. A modest cache captures the head. If the hit ratio is 70%, the backend sees 12,000 queries per second instead of 40,000, and average latency falls from (say) 200 ms to 0.7 × 5 + 0.3 × 200 = 63.5 ms. The long tail never hits; do not expect 100%.

## LRU: the data structure {#sec-qc-lru}

**Least Recently Used** evicts the entry unused for the longest time, assuming recent use predicts near-future use. To do `get` and `put` in O(1) combine two structures:

- a **hash map** from key to node (O(1) lookup), and
- a **doubly linked list** ordered from most recently used (head) to least (tail), so moving a node to the head and removing the tail are O(1).

{{fig qc-lru | LRU cache internals: a hash map points into a doubly linked list ordered by recency. A hit moves the node to the front; an insertion at capacity evicts the tail.}}

```
class LRUCache:
    def __init__(self, capacity):
        self.cap = capacity
        self.map = {}              # key -> node
        self.head = Node(); self.tail = Node()   # sentinels
        self.head.next = self.tail; self.tail.prev = self.head

    def _remove(self, n):  n.prev.next = n.next; n.next.prev = n.prev
    def _push_front(self, n):
        n.next = self.head.next; n.prev = self.head
        self.head.next.prev = n; self.head.next = n

    def get(self, key):
        n = self.map.get(key)
        if n is None: return None          # miss
        self._remove(n); self._push_front(n)
        return n.value

    def put(self, key, value):
        n = self.map.get(key)
        if n:                              # update existing
            n.value = value; self._remove(n); self._push_front(n); return
        if len(self.map) >= self.cap:      # evict least recently used
            lru = self.tail.prev
            self._remove(lru); del self.map[lru.key]
        n = Node(key, value); self.map[key] = n; self._push_front(n)
```

**Invariants.** (1) `len(map)` equals the number of real nodes and never exceeds capacity; (2) every node in the list is in the map under its own key; (3) the list order is exactly recency order. **Tests:** get on empty returns miss; put up to capacity keeps all; adding one more evicts the oldest; a `get` refreshes recency so a different key is evicted; updating a key does not change size; capacity 1 works; concurrent get/put keeps the invariants (needs a lock, or one lock per shard).

**Concurrency.** A shared LRU needs a mutex because even `get` mutates the list. Under heavy contention shard the cache into many small LRUs by key hash (each with its own lock), or approximate LRU: sampled eviction (pick a few random entries and evict the oldest) and CLOCK, which avoid the global list.

**Beyond LRU.** One-time scans can flush valuable entries; policies such as **LFU**, **segmented LRU** and **TinyLFU** admit only items likely to be reused. Name the trade-off: LRU is simple and adapts quickly; frequency-aware policies resist scans.

## The query path {#sec-qc-path}

{{fig qc-path | Query flow with a cache: normalise, hash to a cache shard, hit returns at once; a miss runs the index and document services, then stores the result.}}

The notebook's pieces: the **Query API server** parses and normalises the query (trimming, lower-casing, removing stop words, correcting spelling), then checks the **Memory Cache**. On a **hit** it returns the stored results and refreshes recency. On a **miss** it calls the **Reverse Index Service** to find matching document ids and the **Document Service** for titles and snippets, writes the assembled result into the cache, and returns it.

**Cache key.** The normalised query plus anything that changes the answer (language, region, safe-search flag, result page). Forgetting a dimension returns the wrong results to the wrong user; including too many fragments the cache and kills the hit ratio.

## Distributed cache design {#sec-qc-dist}

One machine cannot hold 400 GB at 40,000 operations per second, so spread the cache over many nodes.

- **Sharding.** Choose the node by **consistent hashing** of the key (Chapter {ch:ch-distdata}), so adding or removing a node moves only a fraction of keys rather than reshuffling everything (a naive `hash mod N` would invalidate most of the cache on resize and send a flood to the backend).
- **Replication.** Replicate hot shards or accept loss: a cache node failure only costs hit ratio. Replicas add memory but lift availability and spread read load.
- **Client-side or proxy routing.** Clients or a proxy tier know the ring; the Query API servers talk directly to the owning node.
- **Local plus shared caches.** A tiny in-process cache (hundreds of the very hottest keys, TTL of seconds) in front of the shared cache removes network hops and absorbs hot keys.

## Freshness, stampedes and hot keys {#sec-qc-fresh}

**Freshness.** Results go stale as the index changes. Use a **TTL** (for instance 5 minutes for typical queries, 30 seconds for news-like queries) and optionally **invalidation** when a document that is in a cached result is updated (hard to do precisely: you would need a reverse map from documents to queries; most systems rely on TTL alone). State plainly that the cache serves **possibly stale** results.

**Cache stampede (thundering herd).** When a hot entry expires, thousands of requests miss at once and all hit the backend. Defences: **request coalescing** (single flight: one request recomputes, others wait for it), **jittered TTLs** so entries do not expire together, **stale-while-revalidate** (serve the old value while one request refreshes), and early probabilistic refresh. See Chapter {ch:ch-cache}.

**Hot keys.** One extremely popular query can overload a single cache node. Replicate the hot key across nodes, split it into several copies (`key#1..key#k`) and pick one at random, or serve from the local in-process tier.

**Negative caching.** Cache "no results" for a short time so repeated bad queries do not hammer the index; keep that TTL short.

**Cache poisoning and safety.** Never cache an error or a partial result as if it were complete (or cache it with a very short TTL and a flag). Validate input to avoid unbounded key sizes; cap the value size.

## Operations and failure modes {#sec-qc-ops}

**Metrics.** Hit ratio (overall and per shard), miss latency, eviction rate, memory usage, key and value size distributions, top keys, stampede events (concurrent recomputations per key), p99 latency. A falling hit ratio after a deploy often means a changed key format or normalisation.

**Failures.** *Cache node down*: ring routes its keys elsewhere; hit ratio dips; protect the backend with a **rate limit and load shedding** (Chapter {ch:ch-resilience}), since losing the cache can send 40,000 queries per second into a backend sized for 12,000. *Cold start*: warm the cache gradually (replay popular queries) before taking full traffic. *Network partition*: treat timeouts as misses, but with a circuit breaker so slow cache calls do not slow queries.

::: worked
**Hit-ratio and capacity.** Suppose the head of 10 million distinct queries accounts for 70% of traffic and each result is 4 KB. Caching that head needs 10⁷ × 4 KB = 40 GB. A 100 GB cluster (with headroom for overhead, say 1.5×) therefore covers the whole head; going to 400 GB adds only the thin tail, perhaps raising the hit ratio from 70% to 75%: diminishing returns. Plot hit ratio against cache size before buying memory.
:::

## Alternatives and trade-offs {#sec-qc-alt}

Table[qc-alt]: Decisions and alternatives.

| Decision | Chosen | Alternative | Reason | Revisit if |
|---|---|---|---|---|
| Eviction | LRU (sharded) | LFU / TinyLFU | Simple, adaptive | Scan-heavy traffic |
| Placement | Consistent hashing | Mod-N hashing | Minimal reshuffle on resize | Fixed size cluster |
| Freshness | TTL | Event-based invalidation | Simplicity | Strict freshness |
| Write path | Cache-aside | Write-through | Results are derived, not source | Pre-computed answers |
| Hot keys | Local tier plus key splitting | Do nothing | Protect a node | Uniform traffic |

::: failure
**Failure modes (summary).** Stampede on expiry; hot key melting one node; mod-N resize flushing the cache; stale results served too long; wrong key (missing locale) serving the wrong answer; caching errors; backend overload after cache loss; memory fragmentation or giant values.
:::

::: misconception
- *"Caching removes the need for a correct backend."* It must still cope with misses and cold starts.
- *"Higher TTL is always better."* It raises hit ratio but serves older data.
- *"LRU is always the best policy."* Scans and frequency effects can beat it.
- *"A cache node failure is harmless."* The backend must survive the miss storm.
:::

::: interview
**Q1. Implement an LRU cache.** Hash map plus doubly linked list; get and put in O(1); evict the tail.

**Q2. How do you scale it?** Shard with consistent hashing; replicate hot data; local tier; thread safety by per-shard locks.

**Q3. How do you stop a stampede?** Single flight, jittered TTL, stale-while-revalidate.

**Q4. How do you keep results fresh?** TTL by query type; invalidation where feasible; accept bounded staleness.
:::

::: exercise
1. A cache with capacity 3 receives: put A, put B, put C, get A, put D, get B, put E. Which keys remain and in what order (most recent first)?
2. Backend latency 150 ms, cache hit 4 ms, hit ratio 80%. Compute mean latency, and at 40,000 queries per second the backend load.
3. A cluster of 10 nodes uses mod-N hashing and gains an 11th node. Roughly what fraction of keys moves? How about with consistent hashing?
4. Write three unit tests that would catch a broken LRU.

**Answers.**
1. After A,B,C: order (recent first) C,B,A. get A: A,C,B. put D evicts B (tail): D,A,C. get B: miss (B was evicted). put E evicts C (tail): E,D,A. Remaining: E, D, A.
2. 0.8 × 4 + 0.2 × 150 = 3.2 + 30 = 33.2 ms. Backend: 0.2 × 40,000 = 8,000 per second.
3. Mod-N: a key stays only if hash mod 10 = hash mod 11, about 1/11 of keys stay in the same place, so roughly 10/11 ≈ 91% move. Consistent hashing: about 1/11 ≈ 9% (those taken over by the new node).
4. (a) Fill to capacity, add one, assert the first key is gone and the rest remain; (b) `get` the oldest key before adding, assert a different key is evicted; (c) update an existing key and assert size does not grow and value changes.
:::

::: summary
- Query popularity is skewed, so a modest cache removes most backend load.
- LRU = hash map + doubly linked list, O(1) get and put, with clear invariants and tests.
- Distribute with consistent hashing; add local tiers; protect against stampedes and hot keys.
- Freshness is bounded by TTL; design the backend to survive cache loss.
:::

::: revision
- [ ] I can write LRU get and put from memory.
- [ ] I can compute hit-ratio effects on latency and load.
- [ ] I can explain stampede and hot-key defences.
:::
