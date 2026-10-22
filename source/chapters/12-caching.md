%part Part IV | Performance and Asynchrony | Making reads fast with caches and making slow work invisible with queues.
%derived Notebook chapter 8 (why cache, caching levels, what to cache, the four update strategies with their drawbacks, cache-aside and write-through and write-behind and refresh-ahead diagrams)
%added hit-ratio mathematics, eviction policies, cache stampede, penetration and avalanche remedies, hot keys, stale-read analysis, and sizing
# Caching {#ch-cache}

::: objectives
After this chapter you can:

- compute the effect of a cache's hit ratio on average latency and on backend load;
- name the layers at which data can be cached and what each is good for;
- implement and compare cache-aside, write-through, write-behind and refresh-ahead;
- choose an eviction policy and a TTL, and explain why caching never removes stale reads;
- prevent cache stampede, penetration and avalanche, and handle hot keys.
:::

::: prereq
Chapter {ch:ch-ds} (hash maps, LRU idea), Chapter {ch:ch-estimation} (latency numbers), Chapter {ch:ch-sql} (database reads).
:::

::: terms
Cache
: A fast, usually smaller store that keeps copies of data so future requests are served faster than from the original source.

Hit ratio
: The fraction of requests answered from the cache: hits / (hits + misses).

TTL (time to live)
: How long an entry may stay in the cache before it is considered expired.

Eviction
: Removing entries to make room when the cache is full.

Invalidation
: Removing or updating cached data because the source has changed.

Cache stampede (thundering herd)
: Many requests simultaneously miss on the same key and all hit the backend.
:::

## Why caching works {#sec-whycache}

Reading from memory takes about 100 nanoseconds; a database query over the network takes milliseconds, a difference of ten thousand times or more (Chapter {ch:ch-estimation}). Caching exploits a property of real workloads: **locality**. A small fraction of items receives most requests (popular videos, the current news), and recently used items are likely to be used again. Keep those in fast memory and most requests never touch the slow store.

The benefit is quantified by the **hit ratio** *h*. If a hit costs *t_c* and a miss costs *t_c + t_s* (check the cache, then the source), the average latency is

> average = *t_c* + (1 − *h*) × *t_s*.

::: worked
**What a cache buys.** Cache hit: 1 ms (network call to a cache server). Database read: 20 ms. Peak traffic: 10,000 reads per second.

- No cache: every read costs 20 ms and the database sees 10,000 reads/s.
- *h* = 90%: average = 1 + 0.10 × 20 = 3 ms; database load = 1,000 reads/s.
- *h* = 99%: average = 1 + 0.01 × 20 = 1.2 ms; database load = 100 reads/s.

Going from 90% to 99% (a modest-sounding 9 points) cuts database load **tenfold** and makes the system far more tolerant of a database slowdown. Conversely, a cache with a 50% hit ratio saves only half the load and adds a component to operate: small hit-ratio changes at the high end matter enormously. That is why teams track the hit ratio as a first-class metric.
:::

Caching helps only when data is **read much more often than it changes**, requests **repeat**, and **some staleness is acceptable**. It does not help write-heavy workloads, unique one-off queries, or data that must always be perfectly current.

## Where caches live {#sec-levels}

{{fig cache-levels | Caching layers between a user and the database. A request is answered at the first layer that holds a valid copy; each layer further left is faster and closer to the user, but less shared.}}

Table[cachelevels]: Cache layers, from the user inward.

| Layer | What it holds | Strength | Limits |
|---|---|---|---|
| Client (browser, app) | Files, API responses (via HTTP cache headers) | Zero network cost | Per user; hard to invalidate |
| CDN | Static and cacheable responses near users | Offloads origin, low latency globally | Staleness, purge cost (Chapter {ch:ch-entry}) |
| Reverse proxy / web server | Rendered pages, static files | Protects application servers | Per-server unless shared |
| Application (in-process) | Objects in the server's memory | Fastest (no network) | Duplicated per server; lost on restart; inconsistent across servers |
| Distributed cache (Redis, Memcached) | Shared objects and query results | Shared by all servers, large | Network hop; another system to run |
| Database buffers | Hot pages and query plans | Automatic | Not under your control |

A useful rule: cache **as close to the user as correctness allows**, and use a **shared distributed cache** for data that many application servers need, because in-process caches multiply memory use and make servers disagree.

### What to cache

- **Query-level**: hash the SQL (plus parameters) as the key and store the result set. Simple, but hard to invalidate: when one row changes you must know which cached queries it affects, so keys often rely on short TTLs.
- **Object-level**: assemble the data into the application's own structure (a user profile, a rendered fragment) and cache *that*. Easier to invalidate (update the object by id) and lets several servers share the same assembled object. Usually preferable.

Good candidates: user sessions, fully rendered pages and fragments, activity streams, user graph data, product catalogue entries, results of expensive computations. Poor candidates: highly personalised, rapidly changing, or security-sensitive data unless keyed carefully.

## Update strategies {#sec-updatestrat}

The hard question is *when and how the cache gets its data and stays in step with the source*. There are four standard strategies.

### Cache-aside (lazy loading)

The application manages the cache. On a read it checks the cache; on a **miss** it reads the database, stores the result in the cache, and returns it. On a write it updates the database and **deletes** (invalidates) the cache entry so the next read reloads it.

{{fig cache-aside | Cache-aside. A hit returns immediately; a miss reads the database, fills the cache, then returns. A write goes to the database and invalidates the cached entry.}}

```python
def get_user(user_id):
    key = f"user:{user_id}"
    value = cache.get(key)
    if value is None:                      # miss
        value = db.query_user(user_id)     # slow path
        if value is not None:
            cache.set(key, value, ttl=300) # fill; TTL bounds staleness
    return value

def update_user(user_id, fields):
    db.update_user(user_id, fields)        # source of truth first
    cache.delete(f"user:{user_id}")        # invalidate; next read reloads
```

**Advantages:** only requested data is cached; a cache failure degrades speed, not correctness (the database still answers). **Disadvantages:** the first request is slow (a *cold start*, so caches may be *warmed* in advance); stale data is possible between a database change and expiry or invalidation; and the invalidate-after-write has a **race**: a reader that missed just before the write may refill the cache with the *old* value after the delete, leaving stale data until the TTL. A short TTL bounds the damage.

### Write-through

The application writes to the **cache**, and the cache synchronously writes to the database. Data in the cache is always current.

**Advantages:** reads are fast and fresh; simple reasoning. **Disadvantages:** every write has the latency of *both* stores; most written data may never be read, wasting cache space (mitigate with a TTL); a new node starts with an empty cache.

### Write-behind (write-back)

The application writes to the cache, which acknowledges immediately; the cache **asynchronously** writes to the database later, often batching and coalescing many writes to the same key.

{{fig write-through-behind | Write-through (left) writes to cache and database before acknowledging. Write-behind (right) acknowledges after the cache and flushes to the database later.}}

**Advantages:** very fast writes, fewer database writes, absorbs bursts. **Disadvantages:** **data loss** if the cache fails before flushing (the only copy of recent writes is in memory); complex to implement correctly (ordering, retries, failure handling); reads from the database directly may see stale data.

### Refresh-ahead

The cache **proactively reloads** entries that are likely to be requested again, shortly *before* they expire, so popular items never cause a miss. **Advantages:** lower latency than lazy loading for hot data. **Disadvantages:** needs a good prediction of what will be requested; wrong guesses waste reads and cache space.

Table[updatecmp]: Update strategies compared.

| Strategy | Read latency | Write latency | Staleness | Data-loss risk | Complexity |
|---|---|---|---|---|---|
| Cache-aside | Miss: slow; hit: fast | Fast (DB only) | Until TTL or invalidation | None | Low |
| Write-through | Fast | Slow (both) | None | None | Medium |
| Write-behind | Fast | Fastest | Database lags the cache | **Yes** | High |
| Refresh-ahead | Fastest for hot data | n/a | Bounded | None | High |

::: note
**Clarification: caching does not remove stale reads.** The notebook lists the *drawbacks* of each strategy; the common thread deserves stating plainly. Unless every read goes through a single linearizable path, a cache holds a *copy*, and a copy can lag the original. Cache-aside is stale until invalidation or TTL; write-through is current only for writes that go through it; any second writer (another service, a batch job, a manual fix) makes it stale. Design for the staleness you can tolerate: choose TTLs deliberately, version keys, and never cache data whose staleness causes harm unless you also check the source of truth at decision points (for example, re-read the balance from the database before charging a card).
:::

## Eviction policies {#sec-evict}

A cache is smaller than the data, so it must decide what to throw away.

Table[evict]: Eviction policies.

| Policy | Evicts | Good for | Weak spot |
|---|---|---|---|
| LRU (least recently used) | The entry unused for longest | General workloads with temporal locality | A one-time large scan evicts the hot set |
| LFU (least frequently used) | The entry used fewest times | Stable popularity | Old popular items linger; needs ageing |
| FIFO | The oldest entry | Simplicity | Ignores usage |
| Random | A random entry | Cheap; surprisingly decent | Unpredictable |
| TTL | Entries past their lifetime | Bounding staleness | Not a space policy by itself |

LRU is the usual default: a hash map plus a doubly linked list gives O(1) lookup, update and eviction (a design exercise in {ch:ch-oo-ds}). Real systems add refinements such as **segmented LRU** or **TinyLFU** admission to resist scans. Combine eviction (for space) with **TTL** (for freshness).

## Failure patterns and remedies {#sec-cachefail}

{{fig cache-failures | Three ways a cache can hurt the backend: a stampede on one expired hot key, penetration by keys that do not exist, and an avalanche when many keys expire together.}}

**Cache stampede (thundering herd).** A hot key expires; hundreds of concurrent requests all miss and all query the database for the same data, possibly overwhelming it. Remedies: **single-flight / request coalescing** (the first miss takes a lock or marker and loads; others wait for its result); **stale-while-revalidate** (serve the expired value briefly while one request refreshes it); **probabilistic early refresh** (each request near expiry refreshes with a small random chance, so refresh is spread out); and **refresh-ahead** for hot keys.

**Cache penetration.** Requests for keys that *do not exist* (random ids, or an attack) miss every time and always reach the database. Remedies: **negative caching** (cache the "not found" result for a short TTL), a **bloom filter** of valid keys in front of the cache (Chapter {ch:ch-ds}), and input validation and rate limiting.

**Cache avalanche.** Many keys expire at the same moment (all given the same TTL at startup), or the cache cluster restarts empty, sending the full load to the database at once. Remedies: **add random jitter** to TTLs (for example 300 s ± 10%), warm the cache gradually, keep cache clusters redundant, and protect the database with rate limits and load shedding (Chapter {ch:ch-resilience}).

**Hot key.** One key gets so much traffic that its single cache node saturates. Remedies: a small in-process **local cache** in front of the distributed cache with a very short TTL; **replicate** the key under several names (`key#1..#8`) and read a random one.

```python
# single-flight sketch: one loader per key, others wait for its result
inflight = {}                      # key -> future (per process)
def get_with_coalescing(key, loader, ttl):
    v = cache.get(key)
    if v is not None: return v
    fut = inflight.get(key)
    if fut is None:
        fut = inflight.setdefault(key, Future())
        if fut.owner_is_me():      # first caller loads
            try:
                v = loader(); cache.set(key, v, ttl=ttl + jitter())
                fut.set_result(v)
            finally:
                inflight.pop(key, None)
    return fut.result(timeout=2)
```

::: supplement
**Sizing a cache.** Use the 80/20 heuristic as a first guess: if 20% of items cause 80% of reads, size the cache to hold that 20%. Better, measure the hit ratio at several sizes (a *miss-ratio curve*): memory is usually wasted beyond the knee of the curve. Account for per-entry overhead (keys, metadata can double the memory for small values), replication (a cache replica doubles memory), and headroom for peaks. Consider **serialisation cost** and entry size: caching a 5 MB object per request wastes bandwidth even on hits.
:::

::: warning
**Common mistakes.** Treating the cache as the source of truth (it can be flushed at any time). Caching without a TTL and relying on perfect invalidation. Using the same TTL everywhere. Caching errors ("database timeout") as if they were values. Putting per-user data under a shared key (leaking private data between users). Forgetting that serialisation formats change between deployments, so old cached bytes break new code (include a version in the key).
:::

::: failure
**Failure modes.** Cache node loss: hit ratio collapses and the database is hit by the full load (design the database for the *miss* load, or have a fallback); network partition between application and cache (decide whether to fail open, reading the database directly, or fail closed); eviction storms when memory is tight; inconsistency between two cache layers (browser, CDN and Redis holding different versions); stale data after a missed invalidation event; thundering herd on restart.
:::

::: misconception
- *"A cache makes the system consistent faster."* It adds another copy that can be stale.
- *"Write-behind is just write-through but faster."* It can lose acknowledged data.
- *"Bigger cache always means better."* Beyond the knee the hit ratio barely moves.
- *"Invalidate on write, so stale reads are impossible."* The refill race and multiple writers still allow them.
:::

::: interview
**Q1. Explain cache-aside and its drawbacks.**
Application checks the cache, loads from the database on a miss and fills the cache; writes go to the database and delete the entry. Drawbacks: cold-start misses, staleness between change and invalidation, and a refill race; mitigate with TTLs and warming.

**Q2. What is a cache stampede and how do you prevent it?**
Many simultaneous misses on one expired hot key overload the database. Use request coalescing, stale-while-revalidate, jittered TTLs or early probabilistic refresh.

**Q3. Cache-aside versus write-through versus write-behind?**
Cache-aside: simple and safe, possibly stale; write-through: fresh, slower writes; write-behind: fastest writes, risk of loss and complexity.

**Q4. How do you keep cache and database consistent?**
You cannot make them perfectly consistent cheaply; bound staleness with TTLs and invalidation, write the database first and then delete the cache entry, version keys, and re-check the database for critical decisions.
:::

::: exercise
1. Cache hit costs 2 ms, database 30 ms, hit ratio 95%. Compute average latency and the database load at 8,000 requests per second.
2. 100,000 keys are loaded at startup with a 600-second TTL. What problem appears at 10 minutes and what is the fix?
3. Give a timeline showing the cache-aside refill race, then one mitigation.
4. For each datum say which caching layer(s) and update strategy you would use: (a) company logo, (b) a user's profile page, (c) a bank balance, (d) a leaderboard updated 5,000 times a second.

**Answers.**
1. Average = 2 + 0.05 × 30 = 3.5 ms. Database load = 5% × 8,000 = 400 per second.
2. An avalanche: all keys expire together and the database receives a burst of 100,000 loads. Add random jitter to TTLs and warm gradually.
3. Reader R1 misses and reads old value v1 from the database; writer W updates the database to v2 and deletes the cache key; R1 then writes v1 into the cache. The cache holds stale v1 until its TTL. Mitigations: short TTLs, writing with a version check (set only if the version is newer), or deferred double-delete.
4. (a) Browser and CDN with a long TTL and versioned URL. (b) Distributed cache with cache-aside and a short TTL (plus maybe a CDN for the public parts). (c) Do not cache for decisions; read the database (possibly cache for display only, with a very short TTL). (d) Write-behind into an in-memory sorted structure with periodic persistence, accepting a small loss window, or cache-aside for reads with batched database updates.
:::

::: summary
- Caching exploits locality; hit ratio drives latency and backend load dramatically at the high end.
- Cache at multiple layers; prefer object-level entries in a shared distributed cache for application data.
- Cache-aside is the safe default; write-through gives fresh reads with slower writes; write-behind is fast but can lose data; refresh-ahead helps hot keys.
- Evict with LRU or similar; bound freshness with TTL and jitter.
- Defend against stampede, penetration, avalanche and hot keys; never assume the cache is the source of truth, and never assume it is perfectly fresh.
:::

::: revision
- [ ] I can compute average latency from a hit ratio.
- [ ] I can write cache-aside code and name its race.
- [ ] I can compare the four update strategies in a table from memory.
- [ ] I can name three cache failure patterns and a remedy for each.
:::

::: supplement
**Further reading.** The Redis and Memcached documentation on eviction and expiry; Facebook's "Scaling Memcache at Facebook" (NSDI 2013) for leases and stampede control; the Caffeine library's TinyLFU design notes; RFC 5861 for stale-while-revalidate.
:::
