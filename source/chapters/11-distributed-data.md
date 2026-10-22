%derived Notebook chapter 2 (CAP theorem, consistency patterns, availability patterns, availability in numbers)
%added PACELC, formal consistency models and session guarantees, quorums, consistent hashing, rebalancing, hot partitions, anti-entropy and conflict resolution
# Consistency, Availability and Partitioning Data {#ch-distdata}

::: objectives
After this chapter you can:

- state the CAP theorem correctly, as a statement about behaviour *during a network partition*;
- explain linearizability, sequential, causal and eventual consistency, and the session guarantees;
- apply quorum rules and explain why R + W > N is necessary but not sufficient for strong guarantees;
- explain consistent hashing, virtual nodes, rebalancing and hot-partition mitigation;
- describe availability patterns (active-passive, active-active) and combine availability numbers.
:::

::: prereq
Chapters {ch:ch-sql} and {ch:ch-scaling-sql} (replication, sharding) and {ch:ch-nosql} (families, quorums), and Chapter {ch:ch-estimation} (availability arithmetic).
:::

::: terms
Network partition
: A failure in which some nodes cannot communicate with others, though each may still be running.

Linearizability
: A strong guarantee: every operation appears to take effect instantly at some point between its start and end, and all clients see one single, up-to-date copy.

Quorum
: A minimum number of nodes that must agree for an operation to count (usually a majority).

Consistent hashing
: A way of assigning keys to nodes so that adding or removing a node moves only a small fraction of keys.

Hot partition
: One partition receiving far more traffic than the others.

Anti-entropy
: Background processes that find and repair differences between replicas.
:::

## Why this chapter exists {#sec-whydist}

When data lives on **more than one machine**, three things become unavoidable. Messages between machines can be delayed or lost. Machines can fail independently. And copies can disagree. Everything in this chapter is about choosing, deliberately, what the system does when those facts collide with user requests. There are no free answers: each choice buys one property by spending another.

## The CAP theorem {#sec-cap}

A distributed data store can offer three desirable properties:

- **Consistency (C)**: every read receives the most recent write or an error (in CAP's precise sense, linearizability).
- **Availability (A)**: every request to a non-failing node receives a (non-error) response, though it may not contain the most recent write.
- **Partition tolerance (P)**: the system continues to operate despite messages between nodes being dropped or delayed.

The theorem (Gilbert and Lynch's proof of Brewer's conjecture) says: **when a network partition occurs, a system cannot be both consistent and available.** It must choose.

{{fig cap-partition | A partition separates two replicas. A write of x = 9 reaches node 1 only. A read at node 2 must either refuse (consistent, not available) or answer with the old value x = 5 (available, not consistent).}}

Look at {fig:cap-partition}. Node 1 accepted the write x = 9. The link to node 2 is cut. A client now reads x at node 2. If node 2 answers "5", it is **available** but **inconsistent** (stale). If node 2 refuses until it can confirm the latest value, it is **consistent** but **unavailable**. The system cannot do both.

::: note
**Clarification: "pick two of three" is misleading.** The notebook draws CAP as a triangle with a choice of two. That picture suggests you can choose to give up partitions, but **partitions are not optional**: networks fail, so any distributed system must tolerate P. The real decision is what to do *during a partition*: **CP** (stay consistent, refuse some requests) or **AP** (stay available, accept possible staleness). When the network is healthy you can have both. Also, CAP's "availability" and "consistency" are narrow technical definitions, so labelling an entire product "CP" or "AP" oversimplifies; many products let you choose per operation.
:::

**PACELC** extends the picture: *if there is a Partition, choose Availability or Consistency; Else (normal operation), choose Latency or Consistency.* Even without failures, strongly consistent replication requires waiting for coordination between nodes, which costs latency. This explains why some systems offer weaker consistency even when everything is healthy.

Table[cp-ap]: CP and AP behaviour in practice.

| | CP (consistency over availability) | AP (availability over consistency) |
|---|---|---|
| During a partition | Minority side refuses writes or reads | Both sides keep accepting requests |
| After healing | Nothing to reconcile | Divergent data must be merged |
| Good for | Money, inventory, locks, coordination data | Feeds, shopping carts, counters, DNS, social data |
| Examples (tendencies) | Consensus-backed stores, single-leader databases with quorum writes | Dynamo-style stores with eventual consistency |

## Consistency models {#sec-consmodels}

"Consistency" in a replicated system is about *what a read may return after a write*. Models run from strongest to weakest:

- **Strong consistency (linearizability)**: after a write completes, every subsequent read, anywhere, sees it. The system behaves as if there were one copy. Achieved with synchronous replication or consensus; costs latency and availability under partition. Suits bank balances, uniqueness checks, leader election.
- **Sequential consistency**: all clients see operations in the same order, but that order need not match real time.
- **Causal consistency**: operations that are causally related (a reply to a question) are seen in that order by everyone; unrelated operations may be seen in different orders. Cheaper than linearizable and often "good enough".
- **Eventual consistency**: if writes stop, all replicas converge. Until then reads may be stale or disordered. Cheap, fast, highly available; suits counters, likes, feeds, DNS.

Table[consistency]: The notebook's three patterns, with the models behind them.

| Pattern | After a write, a read... | How it is achieved | Typical systems |
|---|---|---|---|
| Weak | May or may not see it; the system makes best effort | Asynchronous copy, no repair guarantees | Memcached-style caches, real-time voice and video |
| Eventual | Will see it soon (typically milliseconds to seconds) | Asynchronous replication with convergence | DNS, email, Dynamo-style stores |
| Strong | Always sees it | Synchronous replication, consensus | File systems, relational databases with synchronous replicas |

{{fig consistency-timeline | The same write seen under three models. The writer sets x = 1 at time t0. Strong: every read after t0 returns 1. Eventual: reads return 0 for a while, then 1. Weak: reads may keep returning 0 and the write may even be lost.}}

### Session guarantees

Between "eventual" and "strong" sit practical promises you can give a *single user session* cheaply:

- **Read-your-writes**: a user always sees their own updates.
- **Monotonic reads**: once you see a value, you never see an older one.
- **Monotonic writes**: your writes are applied in the order you made them.
- **Consistent prefix**: you never see an effect before its cause.

These are often enough for user-facing apps and are implemented by routing a session to the same replica or tracking version numbers (Chapter {ch:ch-scaling-sql}).

## Quorums {#sec-quorum}

Suppose a value is stored on **N** replicas. A write succeeds when **W** replicas acknowledge it; a read queries **R** replicas and takes the newest version. If **R + W > N**, the set of replicas read must overlap the set written in at least one node, so a read will include the latest acknowledged write.

{{fig quorum | N = 3 replicas, W = 2, R = 2. The write reached A and B; a read of B and C overlaps at B, which holds the newest version, so the read returns the latest value.}}

Typical settings for N = 3: **W = 2, R = 2** (balanced; tolerates one failure for both); **W = 3, R = 1** (fast reads, but writes fail if any replica is down); **W = 1, R = 3** (fast writes, slow reads, risk of loss). Setting both low (R = W = 1) favours latency and availability at the price of stale reads.

::: warning
**R + W > N is not magic.** It does *not* by itself give linearizability. Pitfalls: *sloppy quorums* (during failures, writes go to stand-in nodes outside the usual N, so the overlap guarantee disappears until the data is handed back); concurrent writes, where "newest" is ambiguous when clocks disagree; a write that succeeded on fewer than W nodes is not rolled back and may later appear; and a replica that restored from an old backup can reintroduce stale data. Use consensus ({ch:ch-consensus}) when you truly need linearizable behaviour.
:::

## Conflicts and repair {#sec-conflict}

AP systems accept concurrent writes on different replicas, so copies diverge and must be reconciled.

- **Last-write-wins (LWW)**: keep the version with the latest timestamp. Simple, but discards a concurrent update silently and depends on clocks (Chapter {ch:ch-consensus}).
- **Version vectors**: each replica tracks counters per node, so the system can tell whether one version *descends* from another or whether the two are truly *concurrent*; concurrent versions are kept as "siblings" and merged by the application.
- **CRDTs (conflict-free replicated data types)**: data structures (counters, sets) designed so that merging any two copies, in any order, gives the same result. A grow-only counter merges by taking the maximum per node.

Replicas also repair themselves in the background (**anti-entropy**): **read repair** (a read that sees differing versions writes the newest back to stale replicas); **hinted handoff** (a node holds writes meant for a temporarily unavailable node and delivers them later); and **Merkle trees** (hash trees that let two replicas compare large datasets by exchanging a few hashes and drilling into the parts that differ).

## Availability patterns {#sec-availpatterns}

Consistency is only half the story; the other half is staying up when parts fail. Two families of patterns, usually combined.

**Fail-over** keeps a spare ready.

- **Active-passive** ("master-slave" fail-over): the active node serves traffic and sends *heartbeats* to a passive standby. If heartbeats stop, the standby takes over the active's address (or the router is updated). A *hot* standby is already running and in sync; a *cold* standby must be started. Downtime is the detection-plus-switch time. Risk: data loss if replication to the standby was asynchronous, and the passive node's capacity sits idle.
- **Active-active** ("master-master"): both nodes serve traffic and share the load, so loss of one halves capacity but does not require a switch. The application or DNS must know both addresses; with data, both accept writes, so conflicts must be handled.

**Replication** makes failure survivable by keeping copies (Chapter {ch:ch-scaling-sql}). Its disadvantages (notebook): potential data loss if the active fails before replicating, and extra hardware and complexity; with multiple write nodes, conflict resolution.

{{fig failover | Active-passive fail-over (left): the standby watches heartbeats and takes over. Active-active (right): both nodes serve traffic behind a balancer.}}

### Availability in numbers

Recall the arithmetic of Chapter {ch:ch-estimation}: components **in series** multiply (more dependencies, less availability), **in parallel** (independent replicas) multiply the *unavailability*. If the web tier is 99.9% available, the database 99.9% and a third-party API 99.9%, a request needing all three gets about 99.7%, roughly 26 hours of downtime a year. Redundancy only helps if failures are independent: two replicas in the same rack or running the same buggy release fail together. Spread across **availability zones** or regions, and roll out changes gradually.

## Partitioning data with consistent hashing {#sec-conshash}

Chapter {ch:ch-scaling-sql} introduced hash sharding: `node = hash(key) mod N`. Its flaw: changing N changes the result for almost every key, so adding one server forces nearly all data to move (and a cache would lose almost all entries at once).

**Consistent hashing** fixes this. Place both **nodes** and **keys** on a conceptual ring using the same hash function. Each key belongs to the **first node clockwise from its position**. When a node is added, it takes over only the keys between itself and its predecessor; when a node leaves, only its keys move to the next node.

{{fig hash-ring | A consistent-hash ring with three nodes. Each key is stored on the first node clockwise from it. Adding node D between B and C moves only the keys that fall between B and D.}}

::: worked
**How much moves?** With plain `mod N` hashing and 10 nodes, going to 11 nodes changes the owner of about 10/11, roughly 91%, of keys. With consistent hashing the new node takes about 1/11, roughly 9%, of the keys (assuming an even spread). For a 10 TB store that is about 0.9 TB instead of 9.1 TB of data movement: the difference between a routine operation and an outage.
:::

Plain consistent hashing spreads unevenly with few nodes (random positions leave unequal arcs). The fix is **virtual nodes (vnodes)**: each physical server owns many (for example 100 to 256) positions on the ring. Load evens out statistically, a new server takes small slices from many others, and a more powerful server can be given more vnodes. Replication fits naturally: store each key on its owner and the next *N − 1* distinct servers clockwise.

### Rebalancing and hot partitions

Moving data must not stop service. Practical approaches: move **whole vnodes or logical shards** (units fixed in advance), copy in the background, then switch ownership with a short cutover; throttle the transfer to protect live traffic; and verify before deleting the old copy.

Even a perfect hash cannot fix **hot keys**: a viral post or a celebrity account gets millions of reads while others get few. Mitigations: **cache** the hot item in front of the store; **replicate** the hot key to more nodes and spread reads; **split** the key with a random suffix (write `counter#0..#9`, read all and sum); give heavy tenants **dedicated capacity**; **rate limit** (Chapter {ch:ch-entry}); and detect hot keys with metrics so you can react.

::: failure
**Failure modes.** A partition causing both sides of a multi-leader system to accept conflicting writes; clock skew making last-write-wins pick the wrong version; a majority partition that elects a new leader while the old leader, isolated, still serves stale reads; a rebalancing storm that saturates the network when many nodes join at once; a hot partition overwhelmed while the cluster average looks healthy; sloppy quorum data lost when a stand-in node dies before handing data back; correlated failures defeating "independent" replicas.
:::

::: misconception
- *"CAP means choose two of three."* Partitions happen; the choice is C or A *during a partition*.
- *"AP systems are inconsistent forever."* They converge when the partition heals (eventual consistency).
- *"R + W > N guarantees strong consistency."* Not with sloppy quorums, concurrent writes or clock problems.
- *"Replication across three zones makes us 'five nines'."* Only if failures are independent and the software, configuration and deployment process are not shared SPOFs.
:::

::: interview
**Q1. Explain CAP in your own words.**
Under a network partition a replicated store must either reject some requests to avoid returning stale data (consistency) or keep answering and risk staleness (availability). Without a partition it can offer both; partitions cannot be ruled out, so the real choice is CP versus AP during failure.

**Q2. What is eventual consistency and when is it acceptable?**
Replicas converge if updates stop; reads may be stale meanwhile. Acceptable for likes, feeds, counters, profile views; not for balances or inventory without extra controls.

**Q3. Why consistent hashing?**
It minimises key movement when nodes change, avoiding mass reshuffles and cache wipe-outs; virtual nodes smooth the load.

**Q4. A user posts and immediately does not see the post. Which guarantee is violated and how do you fix it?**
Read-your-writes; route their reads to the leader or an up-to-date replica for a short time, or carry a version token.
:::

::: exercise
1. N = 5. Choose R and W for (a) fast reads, (b) fast writes, (c) balanced, all with R + W > N, and state how many node failures each tolerates for reads and for writes.
2. A 10-node cluster uses `hash mod N`. Compute the fraction of keys that move going to 11 nodes if the hash is uniform. Compare with consistent hashing.
3. Classify each as CP or AP-leaning and justify: (a) account balance, (b) number of likes, (c) distributed lock, (d) shopping cart.
4. Three services in series have availability 99.95%, 99.9% and 99.99%; the middle one is made redundant with two independent replicas. What is the new overall figure?

**Answers.**
1. (a) R = 1, W = 5: reads tolerate 4 failures, writes tolerate none. (b) R = 5, W = 1 (writes tolerate 4 failures; reads none; risk of loss). (c) R = W = 3: both tolerate 2 failures.
2. A key keeps its node only if hash mod 10 equals hash mod 11, which happens for about 1 in 11 keys (a little more by small-number effects), so roughly 90% move. Consistent hashing moves about 1/11 ≈ 9%.
3. (a) CP: wrong balances are unacceptable. (b) AP: slightly stale counts are fine. (c) CP: two holders of a lock is the failure. (d) AP: a cart can merge copies (Dynamo's classic example).
4. The middle pair: 1 − 0.001² = 0.999999. Overall ≈ 0.9995 × 0.999999 × 0.9999 ≈ 0.9994, i.e. 99.94% (from 99.84% before).
:::

::: summary
- During a partition choose consistency or availability; partitions cannot be avoided; PACELC adds the latency-versus-consistency choice in normal operation.
- Models: linearizable (single copy illusion), causal, eventual; session guarantees give cheap, user-visible promises.
- Quorums (R + W > N) give overlap but not a full guarantee; AP systems need conflict handling (LWW, version vectors, CRDTs) and anti-entropy.
- Fail-over (active-passive, active-active) and replication provide availability; numbers multiply in series; independence is essential.
- Consistent hashing with virtual nodes limits data movement; hot partitions need caching, replication or key splitting.
:::

::: revision
- [ ] I can explain CAP with a partition diagram.
- [ ] I can define strong, causal and eventual consistency and the session guarantees.
- [ ] I can pick R and W for N = 3 and 5 and explain the limits of R + W > N.
- [ ] I can draw a consistent-hash ring with vnodes.
- [ ] I can explain active-passive versus active-active.
:::
