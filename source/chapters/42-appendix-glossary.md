%label C
%added the glossary, written for this book
# Glossary {#app-glossary}

Definitions are short on purpose; the chapter that teaches each term is in the last column.

Table[glossary]: Glossary of terms.

| Term | Meaning | Chapter |
|---|---|---|
| ACID | Atomicity, consistency, isolation, durability: the guarantees of a database transaction | {ch:ch-sql} |
| Availability | Fraction of time a system answers correctly; often quoted in "nines" | {ch:ch-estimation} |
| Back pressure | Signalling a producer to slow down when a consumer is overloaded | {ch:ch-async} |
| Bloom filter | Compact set structure with false positives but no false negatives | {ch:ch-ds} |
| Bulkhead | Isolating resources so one failure cannot exhaust all of them | {ch:ch-resilience} |
| Cache-aside | Application reads the cache first and fills it from the database on a miss | {ch:ch-cache} |
| Cache stampede | Many requests recompute the same expired entry at once | {ch:ch-cache} |
| CAP theorem | During a network partition a system must choose between consistency and availability | {ch:ch-distdata} |
| CDN | Content delivery network: edge caches close to users | {ch:ch-entry} |
| Circuit breaker | Stops calling a failing dependency for a while to let it recover | {ch:ch-resilience} |
| Consensus | Agreement of several nodes on one value despite failures (Paxos, Raft) | {ch:ch-consensus} |
| Consistent hashing | Mapping keys to nodes so adding or removing a node moves few keys | {ch:ch-distdata} |
| CRDT | Replicated data type whose copies merge without conflicts | {ch:ch-practice} |
| Dead-letter queue | Holds messages that repeatedly failed processing | {ch:ch-async} |
| Denormalisation | Storing redundant data to speed reads | {ch:ch-scaling-sql} |
| Eventual consistency | Replicas converge if updates stop, but reads may be stale meanwhile | {ch:ch-distdata} |
| Exactly-once | Marketing term; in practice at-least-once delivery plus idempotent processing | {ch:ch-async} |
| Fan-out | Delivering one event to many recipients | {ch:ch-twitter} |
| Federation | Splitting a database by function into separate databases | {ch:ch-scaling-sql} |
| Fencing token | Increasing number that lets a resource reject a stale lock holder | {ch:ch-consensus} |
| Heartbeat | Periodic signal showing a node is alive | {ch:ch-consensus} |
| Horizontal scaling | Adding more machines | {ch:ch-intro} |
| HTTP/3 | HTTP over QUIC, which runs over UDP | {ch:ch-network} |
| Idempotent | Repeating an operation has the same effect as doing it once | {ch:ch-api} |
| Index | Auxiliary structure that speeds lookups at the cost of writes and space | {ch:ch-sql} |
| Inverted index | Map from terms to the documents containing them | {ch:ch-crawler} |
| Isolation level | How much concurrent transactions can see of each other | {ch:ch-sql} |
| Latency | Time for one operation | {ch:ch-intro} |
| Leader election | Choosing one node to coordinate | {ch:ch-consensus} |
| Lease | Time-limited right to act as owner | {ch:ch-consensus} |
| Load balancer | Spreads requests across servers | {ch:ch-entry} |
| Load shedding | Rejecting some work deliberately to protect the rest | {ch:ch-resilience} |
| LRU | Least recently used eviction policy | {ch:ch-querycache} |
| LSM tree | Log-structured merge tree: write-optimised storage | {ch:ch-ds} |
| MVCC | Multi-version concurrency control: readers see snapshots | {ch:ch-sql} |
| Microservice | Small, independently deployable service owning its data | {ch:ch-microservices} |
| Observability | Ability to understand internal state from outputs (logs, metrics, traces) | {ch:ch-observability} |
| Outbox pattern | Write an event to a table in the same transaction as the data, publish it later | {ch:ch-async} |
| Partition (network) | Nodes cannot talk to each other | {ch:ch-distdata} |
| Partition (data) | A slice of data placed on one node; see sharding | {ch:ch-scaling-sql} |
| PACELC | Extends CAP: else (no partition) trade latency against consistency | {ch:ch-distdata} |
| Percentile | Value below which a given share of observations fall (p99) | {ch:ch-intro} |
| PITR | Point-in-time recovery from base backup plus log | {ch:ch-scaling-sql} |
| Pub/sub | Publishers send to topics; subscribers receive copies | {ch:ch-async} |
| QUIC | Encrypted transport over UDP with multiplexed streams | {ch:ch-network} |
| Quorum | Minimum number of replicas that must respond | {ch:ch-distdata} |
| Race condition | Outcome depends on unlucky timing | {ch:ch-concurrency} |
| Raft | Understandable consensus algorithm with a leader and a log | {ch:ch-consensus} |
| Rate limiting | Restricting request frequency | {ch:ch-entry} |
| Read replica | Copy of a database that serves reads | {ch:ch-scaling-sql} |
| Replication | Keeping copies of data on several nodes | {ch:ch-scaling-sql} |
| Reverse proxy | Server that forwards client requests to backends | {ch:ch-entry} |
| RPC | Remote procedure call | {ch:ch-api} |
| RPO | Recovery point objective: how much data loss is acceptable | {ch:ch-observability} |
| RTO | Recovery time objective: how long recovery may take | {ch:ch-observability} |
| Saga | Sequence of local transactions with compensations | {ch:ch-async} |
| Scalability | Ability to handle growth by adding resources | {ch:ch-intro} |
| Sharding | Splitting one dataset across nodes by key | {ch:ch-scaling-sql} |
| SLA / SLO / SLI | Contract / target / measurement of service quality | {ch:ch-observability} |
| Split brain | Two nodes both believe they are the leader | {ch:ch-consensus} |
| Stateless | Server keeps no per-user state between requests | {ch:ch-aws} |
| Strangler pattern | Gradually replace a legacy system piece by piece | {ch:ch-microservices} |
| Throughput | Operations per unit time | {ch:ch-intro} |
| Token bucket | Rate limiter allowing bursts up to a bucket size | {ch:ch-entry} |
| Trie | Prefix tree | {ch:ch-ds} |
| Two-phase commit | Atomic commit protocol with prepare and commit phases | {ch:ch-consensus} |
| Vertical scaling | Using a bigger machine | {ch:ch-intro} |
| WAL | Write-ahead log: changes are logged before being applied | {ch:ch-sql} |
