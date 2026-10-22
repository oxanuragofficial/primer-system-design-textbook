%part Part V | Reliability in Distributed Systems | Agreeing on facts without a shared clock, and surviving failure on purpose.
%derived Notebook chapter 2 (availability patterns: heartbeats, fail-over) and chapter 6 (master election in replication), and the "under development" topics the primer lists (consistent hashing, scatter-gather)
%added the whole chapter: clocks, failure detection, uncertainty after timeouts, leader election, leases and fencing tokens, consensus, two-phase commit
# Time, Coordination and Consensus {#ch-consensus}

::: objectives
After this chapter you can:

- explain why clocks on different machines disagree and what to use instead of wall-clock time for ordering;
- explain Lamport and vector clocks at an intuitive level;
- explain why a timeout leaves an operation's outcome uncertain and how to design for that;
- describe leader election, leases, split brain and fencing tokens;
- explain, at the level of an interview, how consensus (Raft-style) works, what quorum sizes tolerate, and what it costs;
- compare two-phase commit with sagas.
:::

::: prereq
Chapters {ch:ch-concurrency}, {ch:ch-scaling-sql} (failover, split brain) and {ch:ch-distdata} (quorums, CAP).
:::

::: terms
Clock skew / drift
: Difference between two machines' clocks (skew) and the rate at which a clock gains or loses time (drift).

Heartbeat
: A periodic "I am alive" message used to detect failure.

Lease
: A time-limited grant of a right (such as being leader) that expires unless renewed.

Fencing token
: A number that increases each time a lock or lease is granted; resources reject operations carrying an older token.

Consensus
: Getting a group of nodes to agree on a single value (or a sequence of values) despite failures.

Term / epoch
: A number identifying one era of leadership; a higher term supersedes a lower one.
:::

## Why time is hard {#sec-time}

On one machine, "which happened first?" is easy. Across machines it is not, because each has its own clock, and clocks differ.

- **Skew and drift.** Quartz clocks gain or lose a few milliseconds a day. Protocols such as NTP (Network Time Protocol) keep clocks within roughly milliseconds to tens of milliseconds over a network, sometimes worse; they can also *jump* a clock backwards or forwards when correcting it.
- **Two kinds of clock.** A **wall-clock (time-of-day)** gives the date and time and may jump. A **monotonic clock** only moves forward and is meant for *measuring durations* (timeouts, elapsed time) on one machine; its absolute value is meaningless across machines.
- **No global "now".** Message delays are variable and unbounded, so you cannot know how old a timestamp is.

Consequences: never use wall-clock timestamps from different machines to decide *which write came last* without understanding the risk (last-write-wins can silently discard the "later" write if its machine's clock was behind). Never measure a timeout with the wall clock. And never assume a lease granted for 10 seconds is still valid after your process paused for 15 (a long garbage-collection pause or a virtual-machine freeze).

### Ordering without clocks

What we usually need is not the exact time but the **order of causally related events**. Leslie Lamport's insight: if event A could have influenced event B, then A must be ordered before B; events with no such connection are *concurrent*, and any order is acceptable.

**Lamport clocks** give every event a counter. Each node keeps a counter, increments it on every event, attaches it to every message it sends, and on receiving a message sets its counter to max(own, received) + 1. If A causally precedes B then A's number is smaller, but the reverse does not hold (a smaller number does not prove causality). **Vector clocks** keep one counter *per node*; comparing two vectors tells you whether one event happened before the other or whether they are concurrent, which is what a store needs to detect conflicting writes (Chapter {ch:ch-distdata}).

{{fig lamport | Lamport clocks. Each node increments its counter on every event; a received message pushes the receiver's counter beyond the sender's value, so cause always has a smaller number than effect.}}

::: supplement
**Bounding uncertainty instead.** Google's Spanner database uses special hardware (GPS and atomic clocks) to expose a clock API that returns an *interval* of uncertainty (typically a few milliseconds) rather than a single instant, and it **waits out** the uncertainty before committing so that transaction order matches real time. **Hybrid logical clocks** combine a physical timestamp with a logical counter, so timestamps stay close to real time yet respect causality; several distributed databases use them.
:::

## Failure detection and the uncertain timeout {#sec-fd}

How do you know a node has failed? You cannot, you can only *suspect*. The usual method is a **heartbeat with a timeout**: if no heartbeat arrives within *T* seconds, declare the node dead. But a missing heartbeat has several explanations: the node crashed; it is overloaded or paused; the network between you dropped the message; the network dropped the reply. From the outside these look **identical**.

This leads to a foundational lesson: **when a request times out, you do not know whether it was executed.** The server may never have received it, may be still working on it, or may have finished and had its response lost. A client that retries blindly may duplicate the action; a client that gives up may have lost it. The honest options are:

1. Make the operation **idempotent** (or protect it with an idempotency key, Chapter {ch:ch-api}) so a retry is harmless.
2. **Query the outcome** before retrying ("did payment 123 happen?").
3. Treat the result as **unknown** and reconcile later, with a background job that compares systems.

Choosing the timeout is a trade-off: too short, and slow-but-alive nodes are wrongly removed, causing needless failovers and cascading load; too long, and real failures take a long time to notice. Adaptive detectors (the *phi accrual* detector) measure the heartbeat distribution and output a suspicion level instead of a hard yes or no.

## Leader election, leases and fencing {#sec-leader}

Many designs need exactly **one** node in charge at a time: the database leader, the scheduler that must run a job once, the owner of a shard. Two problems arise: *choosing* the leader, and *making sure the old leader stops*.

The naive approach (a node that stops hearing the leader declares itself leader) produces **split brain** whenever the network partitions: both sides elect a leader and both accept writes. The remedy is the **majority rule**: a node may act as leader only if it has the support of a *majority* of a fixed group. Two disjoint groups cannot both be a majority, so at most one leader exists.

Leadership is granted as a **lease**: a time-limited right that must be renewed. If the leader stops renewing (it crashed, or is partitioned), the lease expires and another node can be elected. But leases rely on clocks and timing, and a paused leader can *wake up believing its lease is still valid*. This is where **fencing tokens** come in: each grant of the lock or lease carries a monotonically increasing number, and the *protected resource* (the storage service or database) remembers the highest number it has seen and **rejects any request carrying a lower one**.

{{fig fencing | Fencing token. Client 1 gets a lock with token 33 and then stalls. The lease expires and client 2 gets token 34 and writes. When client 1 wakes and tries to write with token 33, the storage service rejects it.}}

Without fencing, correctness depends on timing assumptions that real systems violate. With it, even a zombie leader cannot corrupt data. The lock service alone is not enough; **the resource must check the token**.

## Consensus {#sec-consensus}

**Consensus** is the problem of getting several nodes to agree on a value (or on an ordered log of values) even if some fail and messages are delayed. It is the foundation for reliable leader election, configuration stores, distributed locks, and strongly consistent replicated databases. A famous result (**FLP impossibility**) shows that no deterministic algorithm can guarantee consensus in a fully asynchronous system with even one possible failure; practical algorithms (Paxos, Raft, Zab, Viewstamped Replication) get around it with timeouts and randomness, giving up *liveness* briefly rather than *safety* when the network misbehaves: they never agree on two different values, but they may pause.

### How Raft works (intuition)

Raft is designed to be understandable. A cluster of an odd number of nodes (3, 5 or 7) has at most one **leader** per **term**.

1. **Election.** Nodes start as followers. A follower that hears nothing from a leader for a random timeout becomes a **candidate**, increments the term, and asks the others for votes. A node votes once per term, for a candidate whose log is at least as up to date as its own. A candidate with **a majority of votes** becomes leader. Random timeouts make split votes rare and quickly resolved.
2. **Log replication.** Clients send commands to the leader, which appends them to its log and sends them to followers. When a **majority** has stored an entry, the leader **commits** it, applies it, and replies to the client. Followers apply committed entries in order, so all nodes run the same sequence of commands: a **replicated state machine**.
3. **Safety.** A new leader must have all committed entries (the vote rule guarantees this), so committed data is never lost; a deposed leader's uncommitted entries are overwritten.

{{fig raft | Raft in one picture. The leader replicates log entries to followers. An entry is committed once a majority has it (here 3 of 5 including the leader), so the cluster survives the loss of 2 nodes.}}

Table[quorum-sizes]: Cluster size and fault tolerance for majority-based consensus.

| Nodes | Majority needed | Failures tolerated | Note |
|---|---|---|---|
| 1 | 1 | 0 | No fault tolerance |
| 2 | 2 | 0 | Worse than 1 in availability: either failing blocks progress |
| 3 | 2 | 1 | Common minimum |
| 5 | 3 | 2 | Common for critical metadata |
| 7 | 4 | 3 | Rarely needed; more nodes make each commit slower |

Odd sizes are used because 4 nodes tolerate only 1 failure (majority is 3), just like 3 nodes, but cost more. Spread nodes across **failure domains** (racks, availability zones); three zones allow the loss of one entire zone.

### What consensus costs, and when to use it

Every commit needs a round trip to a majority, so writes are **slower** than on a single node, throughput is bounded by the leader, and a minority partition **cannot make progress** (it chooses consistency over availability, a CP system, Chapter {ch:ch-distdata}). Therefore: use consensus for **small, critical coordination data** (who is leader, configuration, locks, shard maps, schema versions), through an existing service such as **etcd**, **ZooKeeper** or **Consul**; do *not* put bulk application data through a hand-written consensus loop. Writing your own consensus protocol is almost always a mistake; use a proven library or service.

::: warning
**Common mistakes.** Implementing leader election with a database row and wall-clock timestamps and no fencing. Running a consensus cluster with an even number of nodes, or all nodes in one zone. Putting large data through the consensus log. Treating a lock as a guarantee without fencing. Forgetting that a majority is needed to *read* linearizably too (a stale leader could serve old reads unless it confirms leadership).
:::

## Atomic commit across systems {#sec-2pc}

What if one logical operation must update **two databases** atomically? **Two-phase commit (2PC)** uses a coordinator. *Phase 1 (prepare):* the coordinator asks every participant "can you commit?"; each makes its changes durable and replies yes or no, promising to commit if asked. *Phase 2 (commit):* if all said yes, the coordinator tells everyone to commit; otherwise to abort.

The trouble is that a participant that voted yes **cannot decide alone**; it must wait for the coordinator. If the coordinator crashes after prepare, participants hold locks and are **blocked** until it returns. 2PC therefore trades availability for atomicity, is slow, and is avoided across independent services. The alternative is a **saga** with compensations (Chapter {ch:ch-async}), which gives eventual rather than atomic consistency. When you truly need atomicity across data, put it in **one** database (or one shard).

Table[2pcsaga]: Two-phase commit versus saga.

| | Two-phase commit | Saga |
|---|---|---|
| Atomicity | Yes (all or none, with locks held) | Eventual, via compensations |
| Isolation | Yes (locks held across prepare) | No; intermediate states are visible |
| Availability | Blocks if the coordinator fails | Continues; compensates on failure |
| Latency | Several round trips, locks held | Each step local and fast |
| Best for | Few tightly coupled databases | Long-running, cross-service workflows |

## Duplicate and out-of-order events {#sec-dups}

Distributed systems deliver messages more than once, late, and out of order. Defences: **sequence numbers or versions** attached to entities so a consumer ignores events older than the latest applied; **idempotent handlers** (Chapter {ch:ch-async}); **event-time versus processing-time** distinction in stream processing; and **conditional writes** (`apply if version = n`). The goal is to make the *effect* of processing independent of delivery accidents.

::: failure
**Failure modes.** Split brain from naive election; a zombie leader writing after its lease expired; clock jumps breaking timeouts or lease checks; false failure detection under load causing failover storms; a minority partition unable to elect a leader (by design); consensus cluster losing a majority and freezing (requires careful manual recovery); 2PC coordinator crash blocking participants; correlated failures (all nodes in one zone); configuration changes (adding nodes) done unsafely, producing two majorities.
:::

::: misconception
- *"Timestamps tell me which write happened last."* Only with synchronised clocks and known error bounds; otherwise use versions or logical clocks.
- *"A timeout means the operation failed."* It means you do not know.
- *"A distributed lock guarantees mutual exclusion."* Not without fencing at the resource.
- *"Paxos/Raft make a system fast and always available."* They make it correct and fault tolerant, at the cost of latency and unavailability of a minority.
:::

::: interview
**Q1. Why can't you rely on timestamps to order events across servers?**
Clocks skew and jump; message delays vary. Use logical or hybrid clocks, versions, or a single sequencer.

**Q2. What is a fencing token?**
A monotonically increasing number issued with each lock or lease; the protected resource rejects requests with a smaller token, so a paused former lock holder cannot corrupt data.

**Q3. How does Raft elect a leader and why does it need a majority?**
Followers time out, become candidates and ask for votes; a majority makes a leader. Two disjoint groups cannot both be majorities, so at most one leader per term; committed entries exist on a majority, so any new leader has them.

**Q4. 2PC versus sagas?**
2PC gives atomic commit but blocks and is slow; sagas are available and cheap but only eventually consistent with compensations.
:::

::: exercise
1. A node has Lamport counter 5 and receives a message stamped 9. What is its counter after receiving? After sending a reply?
2. A five-node cluster is split 3 and 2 by a partition. Which side can elect a leader and commit? What happens to clients of the other side?
3. Process A holds a lease for 10 s, pauses for 20 s, then writes to storage. Explain what goes wrong without fencing and how tokens fix it.
4. Why is a 4-node consensus cluster not better than 3 nodes?

**Answers.**
1. After receiving: max(5, 9) + 1 = 10. After sending a reply (a new event): 11 (the message carries 11).
2. The side with 3 nodes (a majority) can elect and commit. The 2-node side cannot elect a leader or commit; its clients get errors or timeouts (consistency over availability).
3. During the pause the lease expired and B became leader and wrote; A wakes, still believes it holds the lease and overwrites B's data. With tokens, B's token (higher) was recorded by storage; A's write with the old token is rejected.
4. The majority of 4 is 3, so it tolerates only 1 failure, the same as 3 nodes, but needs more votes per commit and has more nodes to fail.
:::

::: summary
- Clocks disagree; use monotonic clocks for durations and logical or hybrid clocks (or versions) for ordering.
- A timeout means "unknown": design for idempotency, outcome queries and reconciliation.
- Elect leaders by majority; use leases with fencing tokens checked at the resource.
- Consensus (Raft, Paxos) replicates a log through a majority: safe, slower, minority unavailable; use it via etcd, ZooKeeper or Consul for small critical data.
- 2PC blocks; sagas are available but eventually consistent.
:::

::: revision
- [ ] I can explain skew, drift and wall versus monotonic clocks.
- [ ] I can update Lamport clocks on a message exchange.
- [ ] I can draw the fencing-token timeline.
- [ ] I can explain Raft election and commit, and quorum sizes.
- [ ] I can contrast 2PC and sagas.
:::

::: supplement
**Further reading.** Leslie Lamport, "Time, Clocks, and the Ordering of Events in a Distributed System" (1978); Diego Ongaro and John Ousterhout, "In Search of an Understandable Consensus Algorithm" (Raft, 2014) and the raft.github.io visualisation; Martin Kleppmann, "How to do distributed locking" (2016); Kleppmann, *Designing Data-Intensive Applications*, chapters 8 and 9; the Spanner paper (2012).
:::
