%derived Notebook chapter 6 (replication, master-slave and master-master, federation, sharding, denormalization, SQL tuning) and chapter 12.5 / 12.8 uses of these techniques
%added replication lag and read-your-writes, failover and split brain, shard-key selection and resharding, hot partitions, connection pooling, backups versus replicas, point-in-time recovery
# Scaling Relational Databases {#ch-scaling-sql}

::: objectives
After this chapter you can:

- explain, in order, the tools for scaling a relational database: tuning, caching, replicas, federation, denormalisation and sharding;
- describe leader-follower and multi-leader replication, replication lag, and the anomalies lag causes;
- explain failover and how split-brain happens and is prevented;
- choose a shard key, compare range, hash and directory sharding, and explain resharding and hot shards;
- distinguish backups, replicas and failover, and explain point-in-time recovery.
:::

::: prereq
Chapter {ch:ch-sql} (indexes, transactions) and Chapter {ch:ch-estimation} (capacity estimation).
:::

::: terms
Leader (primary, master)
: The node that accepts writes; its changes are copied to followers.

Follower (replica, standby, slave)
: A node that copies the leader's changes and can serve reads.

Replication lag
: The delay between a write on the leader and its appearance on a follower.

Shard
: One horizontal slice of a table's rows stored on its own database server.

Shard key
: The column whose value decides which shard holds a row.

Failover
: Promoting a follower to leader when the leader fails.

Split brain
: Two nodes both believing they are the leader.
:::

## The scaling ladder {#sec-ladder}

A single database server handles a surprising amount, often thousands of queries per second and terabytes of data. Scale it in this order, cheapest and least risky first:

1. **Tune**: add missing indexes, fix slow queries, right-size the schema (Chapter {ch:ch-sql}). Often a 10× to 100× improvement and costs nothing.
2. **Scale up**: more memory (so the working set fits), faster disks, more cores.
3. **Cache**: keep hot results in memory so reads never reach the database (Chapter {ch:ch-cache}).
4. **Replicate**: add read-only copies to multiply read capacity and improve availability.
5. **Split by function (federation)**: separate databases for separate features.
6. **Denormalise**: duplicate data to avoid expensive joins.
7. **Shard**: split one table across many servers to scale writes and data size.

Each step adds complexity. Measure first; many systems never need step 7.

{{fig ladder | The scaling ladder for a relational database. Each rung is more powerful and more complex than the one below.}}

## Replication {#sec-repl}

**Replication** keeps copies of the same data on several servers. It serves two goals that must not be confused: **availability** (another copy survives a failure) and **read scaling** (followers answer read queries). It does *not* by itself scale writes: every write still goes through the leader (in a single-leader design).

### Leader-follower

All writes go to the **leader**, which records each change in a replication log (the same write-ahead log used for durability). **Followers** stream and apply that log. Reads can go to any follower.

{{fig leader-follower | Leader-follower replication. The application writes to the leader; changes stream to followers, which serve reads. If the leader fails, a follower can be promoted.}}

**Synchronous replication** makes the leader wait for a follower to confirm before acknowledging the write: no acknowledged write is lost if the leader dies, but latency rises and an unavailable follower can block writes. **Asynchronous replication** acknowledges immediately and ships changes in the background: faster and more available, but the most recent writes may be lost if the leader fails before they reach a follower. A common compromise is *semi-synchronous*: one follower is synchronous, the rest asynchronous.

### Replication lag and its anomalies

With asynchronous replication, followers are slightly behind: **replication lag**, usually milliseconds, but seconds or more under load. This causes visible anomalies, collectively an *eventual consistency* effect:

- **Read-your-writes violation**: a user posts a comment (written to the leader), reloads, and the read goes to a lagging follower, so the comment is missing.
- **Monotonic reads violation**: a user sees newer data, then on the next request (another follower) sees *older* data, as if time went backwards.
- **Causality violation**: a reply appears before the question it answers, because the two were replicated from different partitions at different speeds.

Remedies: route a user's reads to the **leader for a short time after they write**, or track the log position of the user's last write and only read from a follower that has caught up; **pin a user to one follower** (for monotonic reads); and for rare critical reads, always read from the leader. Cheap in code, but they must be designed in, not discovered in production.

::: warning
**Common mistake.** Treating replicas as a backup. A replica faithfully copies a bad `DELETE` or a corrupted row within moments. Replication protects against *hardware failure*, not against *human or software error*; only backups with point-in-time recovery protect against that (see below).
:::

### Multi-leader replication

In **multi-leader** (master-master) replication, two or more nodes accept writes and replicate to each other. This helps write availability across data centres (each region writes locally) and tolerates the loss of a leader without failover. The cost is **write conflicts**: two users edit the same row on two leaders at once. Resolution strategies include *last-write-wins* (simple, but silently discards one update), merging, custom application logic, or conflict-free replicated data types. Because conflict handling is hard, avoid multi-leader unless you need it, and require that most writes for a given record go to one leader. Also be careful with auto-increment keys and constraints: they cannot be enforced globally without coordination.

Table[repltypes]: Replication styles compared.

| | Leader-follower | Multi-leader |
|---|---|---|
| Writes accepted at | One node | Several nodes |
| Read scaling | Yes (followers) | Yes |
| Write scaling | No | Partly (by region), with conflicts |
| Conflicts | None | Must be detected and resolved |
| Complexity | Moderate | High |
| Typical use | Most applications | Multi-region writes, offline-first apps |

### Failover and split brain

When the leader fails, the system must **fail over**: detect the failure (heartbeats, timeouts), choose the most up-to-date follower, promote it, and redirect writes and the other followers to it. This is risky:

- With asynchronous replication, the promoted follower may lack the old leader's last writes (**data loss**), and if the old leader returns, its extra writes conflict.
- A *slow* leader may be wrongly declared dead; if it later wakes up and still accepts writes while a new leader exists, you have **split brain**: two leaders, diverging data.
- Timeouts that are too short cause needless failovers during a brief pause; too long extends the outage.

Defences: use a **majority vote** (a consensus system, Chapter {ch:ch-consensus}) to elect a single leader and require a quorum; **fence** the old leader (cut its network or storage access, or use leases and fencing tokens so a stale leader's writes are rejected); and practise failover regularly.

## Federation and denormalisation {#sec-fed}

**Federation** (functional partitioning) splits the database *by feature*: one database for users, one for products, one for forums. Each is smaller, fits more of its working set in memory, and can be scaled and tuned independently; write load is spread across servers. The costs: application code must know which database holds what, **cross-database joins** become application-level work, and **transactions across databases** are no longer simple.

{{fig federation | Federation. The application talks to separate databases for users, products and forums instead of one large one. A query that needs data from two of them must be assembled in code.}}

**Denormalisation** trades write simplicity for read speed by storing redundant data so frequent queries avoid joins. For example, store the author's display name on each comment, or keep a precomputed `comment_count` on each post. Reads become one lookup; writes must update every copy, and copies can drift apart if an update is missed. Denormalise only for measured hot paths. **Materialised views** (stored query results the database refreshes) are a managed version of the same idea.

## Sharding {#sec-shard}

**Sharding** (horizontal partitioning) splits *one table's rows* across several servers, each holding a **shard**: users A to H on one, I to P on another. Unlike replication, each shard holds *different* data, so both **writes** and **total data size** scale roughly with the number of shards.

{{fig sharding | Sharding by user id. A routing layer (in the application or a proxy) maps each user to one shard. Each shard is itself usually replicated for availability.}}

### Choosing the shard key

The shard key decides everything. A good key:

- is **present in most queries**, so each query touches one shard instead of all of them (a scatter-gather query across all shards is slow and fragile);
- has **high cardinality** and spreads data and traffic **evenly**;
- is **stable**, because changing a row's key moves it between shards.

Table[shardstrat]: Sharding strategies.

| Strategy | How | Strengths | Weaknesses |
|---|---|---|---|
| Range | Key ranges per shard (A-H, I-P) | Efficient range queries | Hot spots (new users all land on the last shard); uneven sizes |
| Hash | `hash(key) mod N` | Even spread | Range queries scatter; changing N moves most keys |
| Consistent hash | Keys and nodes on a ring | Adding a node moves only a fraction of keys | More complex (Chapter {ch:ch-distdata}) |
| Directory (lookup) | A table maps key to shard | Maximum flexibility; easy rebalancing | The directory is a dependency and potential bottleneck; must itself be fast and replicated |

### What sharding costs

- **Cross-shard queries** and **joins** are expensive or unsupported; design so common operations stay within one shard.
- **Cross-shard transactions** lose simple ACID; you need patterns such as sagas (Chapter {ch:ch-async}) or two-phase commit (slow, blocking).
- **Hot shards**: a celebrity user or a popular product concentrates traffic on one shard even if data is evenly distributed. Mitigate with finer keys (split a hot key into several sub-keys), caching, or dedicated shards for the heaviest tenants.
- **Resharding** (changing the number of shards) is a major operation: data must move while the system keeps serving. Plan for it: start with many **logical shards** (say 1,024) mapped to few physical servers, so growth means moving whole logical shards to new servers rather than re-splitting data.
- **Global uniqueness**: auto-increment IDs conflict across shards; use UUIDs, a central ID service, or time-ordered ID schemes.
- **Operational load**: backups, schema changes, monitoring and failover multiply by the shard count.

::: worked
**How many shards?** The messaging example of Chapter {ch:ch-estimation} needed about 330 TB and 10,000 writes per second at peak. Suppose one database server comfortably holds 4 TB and handles 2,000 writes per second. Capacity needs: 330 / 4 ≈ 83 servers; writes: 10,000 / 2,000 = 5 servers. Data volume, not write rate, drives the count: about 83 shards (each with replicas). That prompts questions that could shrink it: can old messages be archived to cheaper storage? Is 200 bytes per message accurate? With a hot set of recent messages only a fraction of the data needs fast storage. Estimates guide, then measurement decides.
:::

## SQL tuning checklist {#sec-tuning}

Before adding machines, apply the notebook's tuning list in this order.

- **Benchmark and profile** (load tests, slow-query logs) to find the real bottleneck; fix the biggest first.
- **Tighten the schema**: use the smallest suitable types (`INT` instead of `BIGINT` when it fits; `DECIMAL` for money, never floating point; `CHAR` for fixed-length, `VARCHAR` for variable); `NOT NULL` where possible; avoid storing large blobs in rows (store them in an object store and keep a reference).
- **Use good indexes** on columns used in `WHERE`, `ORDER BY`, `GROUP BY`, `JOIN`; remember the cost to writes.
- **Avoid expensive joins**: denormalise where the profile shows a hot join.
- **Partition tables** so hot recent data is separate from old data; **archive** old rows.
- **Tune the query cache and buffer pool**: ensure the working set fits memory.
- **Use a connection pool** so thousands of application threads share a few dozen database connections; each connection costs memory and a thread on the server.

## Backups, replicas and failover {#sec-backup}

These three are often confused. They protect against *different* failures.

Table[backuprepl]: Backups, replicas and failover are different tools.

| | Backup | Replica | Failover |
|---|---|---|---|
| What it is | A separate copy at a point in time | A live, continuously updated copy | The act of switching to another node |
| Protects against | Deletion, corruption, bugs, ransomware, disasters | Hardware or node failure; read load | Leader outage |
| Does *not* protect against | Downtime (restore takes time) | A bad write or delete (copied instantly) | Data errors; also may lose recent writes |
| Recovery time (RTO) | Minutes to hours or longer | Seconds to minutes | Seconds to minutes |
| Data loss (RPO) | Since last backup, or near zero with log archiving | Near zero (sync) or small (async) | Depends on replication mode |

**Point-in-time recovery (PITR)** combines a periodic full backup with continuously archived write-ahead log. To undo an accidental `DROP TABLE` at 14:03, restore the last full backup, then replay the log up to 14:02:59. Define two targets before an incident: the **recovery point objective** (RPO: how much data loss is tolerable, measured in time) and the **recovery time objective** (RTO: how long recovery may take). Keep backups in a *different* account or region, protect them from deletion, and **test restores regularly**: an untested backup is not a backup.

::: failure
**Failure modes.** Lag so large that read replicas serve minutes-old data or fall permanently behind; split brain after a bad failover; a hot shard overloaded while others are idle; a shard key that cannot support the dominant query; resharding that stalls under live traffic; a migration run on every shard inconsistently; replicas backing up the same corrupt data; backups that were never restorable; connection exhaustion in a failover storm when every client reconnects at once.
:::

::: misconception
- *"Replication scales writes."* In leader-follower it does not; only sharding (or multi-leader with conflicts) does.
- *"We have replicas, so we have backups."* Replicas copy mistakes instantly.
- *"Sharding is the first thing to do when the database is slow."* Tuning, caching and replicas come first.
- *"Hash sharding avoids hot spots."* It evens out *keys*, not *traffic*; a single hot key is still hot.
:::

::: interview
**Q1. How would you scale a read-heavy relational database?**
Tune and index; cache hot reads; add read replicas with asynchronous replication, handling lag (read-your-writes by routing recent writers to the leader). Only then consider sharding.

**Q2. What is replication lag and how does it affect users?**
Followers apply changes after the leader, so reads may be stale; users may not see their own writes or may see time go backwards. Mitigate with leader reads after writes and session pinning.

**Q3. How do you choose a shard key?**
High cardinality, even distribution, present in most queries so they hit one shard, and stable. Evaluate hot-key risk and resharding cost; consider logical shards.

**Q4. What is split brain and how do you prevent it?**
Two nodes both acting as leader. Prevent with quorum-based election, fencing of the old leader (leases, fencing tokens, cutting access), and conservative failover.
:::

::: exercise
1. A database has 50,000 reads/s and 2,000 writes/s at peak; one node handles 15,000 reads/s and 5,000 writes/s. Design with replicas and state the minimum number of nodes.
2. After posting, a user's page does not show the post. Explain why and give two fixes.
3. You shard `orders` by `customer_id` with hash mod 8. Which queries are cheap? Which are expensive? What changes when you go to 16 shards?
4. Order these by recovery speed and data protection: nightly backup, asynchronous replica, continuously archived log with a weekly backup.

**Answers.**
1. Reads: 50,000 / 15,000 → 4 nodes; writes 2,000 fit on the leader alone. Use one leader plus 3 followers (4 nodes), preferably 4 followers for headroom and failover; one follower can take over as leader. Still watch replication lag.
2. The read hit a follower that had not yet applied the write. Fixes: read from the leader for a short window after the user writes; or track the write's log position and read only from a sufficiently caught-up follower.
3. Cheap: anything filtered by `customer_id` (one shard). Expensive: "all orders from today" or by product (every shard queried and merged). Moving from 8 to 16 shards with plain mod moves about half of all keys, so use consistent hashing or logical shards to move less.
4. Fastest recovery: asynchronous replica (seconds, but copies mistakes); nightly backup restore is slowest and loses up to a day; log-archived PITR restores in minutes-hours with near-zero data loss and protects against mistakes. Best protection overall: PITR plus replicas.
:::

::: summary
- Scale in order: tune, scale up, cache, replicate, federate, denormalise, shard.
- Replication scales reads and availability, not writes; lag causes read-your-writes and monotonic-read anomalies.
- Failover needs consensus and fencing to avoid split brain and data loss.
- Sharding scales writes and size but breaks cross-shard queries and transactions; the shard key is the critical decision; plan resharding and hot-key handling.
- Backups, replicas and failover solve different problems; restore drills and PITR are essential.
:::

::: revision
- [ ] I can list the scaling ladder in order and justify it.
- [ ] I can describe lag anomalies and their remedies.
- [ ] I can explain split brain and fencing.
- [ ] I can pick a shard key and name its risks.
- [ ] I can say how backups, replicas and failover differ and define RPO and RTO.
:::

::: supplement
**Further reading.** Kleppmann, *Designing Data-Intensive Applications*, chapters 5 (replication) and 6 (partitioning); the replication and PITR chapters of the PostgreSQL and MySQL manuals; engineering write-ups on sharding from large social companies (search for the sharding of their main MySQL or PostgreSQL clusters).
:::
