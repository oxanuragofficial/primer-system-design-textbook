%part Part IX | Practice and Real-World Architectures | Twenty-three further design questions to practise with, and a method for learning from the architectures of real systems.
%derived Notebook chapter 14 (the practice bank of additional questions and the lists of real-world and company architectures)
%added a structured starting sketch for every question (clarifying questions, core design, the hard part, chapters to revisit), a self-assessment rubric, and a study plan
# Practice Bank: Twenty-Three More Design Questions {#ch-practice}

::: objectives
After this chapter you can:

- start any of the notebook's additional questions with the right clarifying questions and a defensible skeleton;
- identify the single hardest sub-problem in each and the chapter that covers it;
- assess your own answer against a rubric and plan further practice.
:::

::: prereq
All of Part VII (the interview method and the worked designs). Attempt each question for 30 to 40 minutes *before* reading its sketch.
:::

::: supplement
**How these sketches were written.** The notebook lists the questions (with reading links) but gives no answers. Each entry below is the book's own starting sketch: it names what to ask, the core components, the hard part, and where in this book to look. They are seeds for your design, not complete solutions, and they are not taken from the linked articles.
:::

## How to use the bank {#sec-pr-use}

Follow the loop from Chapter {ch:ch-interview}: requirements, estimates, API, data model, high-level design, deep dive, bottlenecks, failure handling. Time-box yourself, speak your reasoning aloud (or write it), then compare with the sketch and the **rubric** in Table {tab:pr-rubric}.

Table[pr-rubric]: Self-assessment rubric (score each 0 to 2; 14 is the maximum).

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Requirements | Started designing at once | Some questions | Functional, non-functional and scope agreed |
| Estimates | None | Rough | Used to justify choices |
| API and data | Missing | Partial | Clear contracts, keys, indexes |
| Architecture | Boxes only | Flow explained | Flows, consistency and scaling explained |
| Deep dive | Skipped | Described | Alternatives and trade-offs weighed |
| Failure | Not mentioned | A few cases | Systematic, with recovery and monitoring |
| Communication | Disorganised | Mostly clear | Structured, checks in with the interviewer |

## The questions {#sec-pr-q}

**1. File sync like Dropbox.** *Ask:* file sizes, devices per user, conflict policy, sharing. *Core:* split files into content-addressed **chunks** (hash each), upload only chunks the server lacks (deduplication), keep file→chunk-list metadata in a database, chunks in object storage; a notification channel tells other devices of changes; clients keep a local index and sync by diffing versions. *Hard part:* **conflict resolution** when two devices edit offline (keep both copies, or merge). *Revisit:* {ch:ch-nosql}, {ch:ch-async}, {ch:ch-distdata}.

**2. A search engine like Google.** *Ask:* corpus size, freshness, ranking quality. *Core:* crawler, document store, inverted index, ranking, query serving with caches. *Hard part:* index partitioning and tail latency. *Revisit:* {ch:ch-crawler}, {ch:ch-querycache}.

**3. A scalable web crawler.** *Core:* priority and politeness frontier, URL and content de-duplication, shard by host. *Hard part:* traps and politeness at scale. *Revisit:* {ch:ch-crawler}.

**4. Google Docs (collaborative editing).** *Ask:* number of simultaneous editors, offline support. *Core:* clients send **operations** to a server that orders them; **operational transformation** or a **CRDT** (conflict-free replicated data type) merges concurrent edits; persist an operation log with periodic snapshots; presence over WebSockets. *Hard part:* convergence: all replicas end with the same text regardless of arrival order. *Revisit:* {ch:ch-distdata}, {ch:ch-consensus} (ordering and clocks).

**5. A key-value store like Redis.** *Core:* in-memory hash table, single-threaded event loop or sharded threads, durability by snapshots plus an append-only log, primary-replica replication, sharding by consistent hashing. *Hard part:* durability versus latency (fsync policy) and failover. *Revisit:* {ch:ch-ds}, {ch:ch-distdata}, {ch:ch-querycache}.

**6. A cache like Memcached.** *Core:* slab-style memory management, LRU per slab class, client-side consistent hashing, no persistence. *Hard part:* memory fragmentation and hot keys. *Revisit:* {ch:ch-querycache}, {ch:ch-cache}.

**7. Recommendations like Amazon's "customers also bought".** *Core:* offline batch job computing item-to-item co-occurrence (or embeddings), results stored per item, online lookup behind a cache, filters for stock and region. *Hard part:* cold start and freshness versus cost. *Revisit:* {ch:ch-salesrank}, {ch:ch-cache}.

**8. TinyURL or Bitly.** *Core:* unique code generation, key-value store, cache, redirect service. *Hard part:* collision-free code generation across servers. *Revisit:* {ch:ch-pastebin}.

**9. A chat service like WhatsApp.** *Ask:* group size limits, history retention, end-to-end encryption. *Core:* persistent connections to a gateway, a per-user inbox (queue), delivery receipts, offline storage, group fan-out through a messaging service. *Hard part:* ordering and exactly-once *effects* (message ids, ack and retry), and connection fleet scaling. *Revisit:* {ch:ch-async}, {ch:ch-oo-ds}.

**10. Photo sharing like Instagram.** *Core:* object storage plus CDN for images, asynchronous thumbnail pipeline, sharded metadata, feed generation. *Hard part:* feed fan-out for popular accounts. *Revisit:* {ch:ch-twitter}, {ch:ch-entry}.

**11. A news feed (Facebook).** *Core:* hybrid fan-out, ranking stage, caches. *Hard part:* celebrities and ranking freshness. *Revisit:* {ch:ch-twitter}.

**12. A timeline (Facebook).** *Core:* per-user post lists in cache backed by durable storage; read-heavy. *Hard part:* keeping lists consistent with deletes and privacy changes. *Revisit:* {ch:ch-twitter}, {ch:ch-cache}.

**13. Facebook-style chat with presence.** *Core:* chat design plus a **presence** service holding short-lived "online" state (heartbeats with TTL), with fan-out limited to active friends. *Hard part:* presence churn volume (batch and rate-limit updates). *Revisit:* {ch:ch-async}, {ch:ch-cache}.

**14. Graph search.** *Core:* social graph storage plus inverted indexes over typed edges and attributes, privacy filters. *Hard part:* query planning and visibility checks. *Revisit:* {ch:ch-socialgraph}, {ch:ch-crawler}.

**15. A CDN like Cloudflare.** *Core:* edge points of presence, routing by DNS or anycast, tiered cache, origin shield, purge API. *Hard part:* cache invalidation worldwide and origin protection. *Revisit:* {ch:ch-entry}, {ch:ch-network}.

**16. Trending topics.** *Core:* stream processing over sliding windows, approximate counting, top-k heap, time-decay scoring, spam filtering. *Hard part:* distinguishing a surge from a baseline (compare with a historical average). *Revisit:* {ch:ch-salesrank}, {ch:ch-ds}.

**17. Random ID generation.** *Core:* a time-ordered 64-bit id of timestamp, machine id and sequence (a Snowflake-style scheme), or pre-allocated id ranges per server. *Hard part:* clock going backwards and machine-id assignment. *Revisit:* {ch:ch-consensus}.

**18. Top *k* requests in a window.** *Core:* hash counts per time bucket plus a min-heap of size *k*; at scale, partition by key and merge partial top-*k*s; use a count-min sketch for bounded memory. *Hard part:* accuracy versus memory. *Revisit:* {ch:ch-ds}, {ch:ch-salesrank}.

**19. Serving from multiple data centers.** *Core:* geo-routing, replication (synchronous within a region, asynchronous across), conflict handling, failover drills. *Hard part:* write conflicts and the choice of consistency. *Revisit:* {ch:ch-distdata}, {ch:ch-consensus}, {ch:ch-cloud}.

**20. An online multiplayer card game.** *Core:* authoritative server holds game state; rooms and turns as a state machine; real-time channel; reconnect handling; anti-cheat (hide other players' cards on the server side). *Hard part:* consistent state with unreliable clients. *Revisit:* {ch:ch-oo-ds}.

**21. A garbage collection system.** *Core:* reference counting versus tracing (mark and sweep), generational collection, stop-the-world pauses versus concurrent marking. *Hard part:* cycles and pause times. *Revisit:* {ch:ch-concurrency}, {ch:ch-ds}.

**22. An API rate limiter.** *Core:* token bucket or sliding-window counters per key in a shared fast store, atomic increments, local approximation plus periodic sync. *Hard part:* accuracy across many gateway nodes. *Revisit:* {ch:ch-entry}, {ch:ch-cache}.

**23. A stock exchange.** *Core:* an **order book** per symbol with price-time priority, a single-writer matching engine, a sequencer assigning order, a journal for replay and recovery, market-data fan-out. *Hard part:* determinism and ultra-low latency (single thread per symbol, no locks). *Revisit:* {ch:ch-consensus}, {ch:ch-concurrency}.

## A study plan {#sec-pr-plan}

Over four weeks: **week 1**, redo the eight worked designs of Part VII from memory; **week 2**, questions 1 to 8 on paper, scoring yourself with the rubric; **week 3**, questions 9 to 16 with a partner who plays the interviewer; **week 4**, questions 17 to 23 plus two mock interviews, concentrating on the dimensions where your rubric score is lowest. Keep a log of *mistakes* (a missing estimate, an unexamined failure mode): they repeat.

::: worked
**Scoring example.** A candidate on question 22 scores: requirements 2, estimates 1, API and data 2, architecture 2, deep dive 1 (did not compare token bucket with sliding window), failure 0 (never discussed a Redis outage), communication 2. Total 10 of 14; the action is to practise failure discussion (what happens to limits if the store is down: fail open or fail closed?) and alternatives.
:::

::: misconception
- *"Memorise one answer per question."* Interviewers vary the constraints; practise the method.
- *"The hint sketches are complete designs."* They are starting points.
:::

::: interview
**Q1. You are asked a question you have never seen; what do you do?** Apply the same loop: clarify, estimate, draw the request path, find the hardest part, and name trade-offs.

**Q2. How do you choose which sub-problem to deep dive?** The one that is hardest or most specific to the problem (conflict resolution for sync, ordering for the exchange), or the one the interviewer signals.
:::

::: exercise
1. Pick question 4, 9 or 19 and write a one-page design using the rubric headings.
2. For question 17, show why a clock moving backwards can duplicate ids and give two mitigations.
3. For question 22, decide fail-open versus fail-closed for a login endpoint and for a public read API, with reasons.

**Answers.**
1. Compare your page with the sketch; a strong page contains numbers, a data model and a failure section.
2. If the timestamp part repeats while the sequence restarts at zero, two ids can collide. Mitigations: refuse to generate ids until the clock passes the last timestamp (wait), or keep a persisted high-water mark and use it as the minimum timestamp.
3. Login: usually fail closed or degrade to a stricter local limit, because unlimited attempts enable password guessing. Public read API: usually fail open with a local limit, because blocking all reads is a bigger harm than temporary over-use.
:::

::: summary
- Each question has a recognisable core, a hard part and a chapter to revisit.
- Practise with a time box and a rubric; log mistakes.
- The method transfers; memorised answers do not.
:::

::: revision
- [ ] I can state the hard part of every question in one sentence.
- [ ] I have scored at least eight practice answers with the rubric.
:::
