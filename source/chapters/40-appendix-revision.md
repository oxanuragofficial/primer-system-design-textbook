%part Back Matter | Appendices | Revision sheets, the coverage matrix, the glossary and the references.
%label A
%derived Notebook chapter 15 (revision sheets: symptom to first fix, numbers and formulas, one-line trade-offs)
%added formulas with units, decision tables, failure-to-remedy map and an extended one-line trade-off list covering the supplemental chapters
# Revision Sheets and Formulas {#app-revision}

::: summary
Use this appendix in the last days before an interview or exam. Everything here is explained in the chapters; the sheets compress it. If a line is unfamiliar, follow the chapter reference.
:::

## Symptom to first fix {#sec-rev-symptom}

Table[rev-symptom]: Start with the cheapest fix that attacks the measured bottleneck.

| Symptom | Likely cause | First fix | Where |
|---|---|---|---|
| Slow page, database CPU high | Hot repeated reads | Cache (cache-aside), add index | {ch:ch-cache}, {ch:ch-sql} |
| Slow queries on one table | Missing or wrong index, full scans | Inspect the query plan, add index | {ch:ch-sql} |
| Read load exceeds one DB | Read-heavy traffic | Read replicas (mind lag) | {ch:ch-scaling-sql} |
| Write load exceeds one DB | Write-heavy or huge data | Tune, federate, then shard | {ch:ch-scaling-sql} |
| Users far away see slow loads | Distance and latency | CDN, regional deployment | {ch:ch-entry} |
| Spiky load crashes the service | No buffering | Queue, rate limit, back pressure | {ch:ch-async} |
| Slow work blocks requests | Synchronous heavy work | Move to a queue and workers | {ch:ch-async} |
| One slow dependency freezes everything | No timeouts or isolation | Timeouts, circuit breaker, bulkheads | {ch:ch-resilience} |
| Retries make an outage worse | Retry storm | Backoff with jitter, retry budgets | {ch:ch-resilience} |
| Duplicate side effects | At-least-once delivery | Idempotency keys, idempotent consumers | {ch:ch-api}, {ch:ch-async} |
| Stale reads after a write | Replica lag, cache | Read from primary after write, versioning | {ch:ch-distdata} |
| Cache miss storm after expiry | Stampede | Single flight, jittered TTL | {ch:ch-cache} |
| Single server failure takes site down | Single point of failure | Redundancy across zones, load balancer | {ch:ch-aws} |
| Two leaders after a network split | Split brain | Consensus, leases with fencing tokens | {ch:ch-consensus} |
| One tenant slows others | Shared resources | Quotas, isolation, per-tenant limits | {ch:ch-entry} |
| Deploy causes outage | Big-bang release | Canary, blue-green, feature flags, rollback | {ch:ch-cloud} |
| Cannot tell what is wrong | No observability | Metrics, structured logs, traces, SLO alerts | {ch:ch-observability} |
| Credential leak | Secrets in code | Secrets manager, rotation, least privilege | {ch:ch-security} |

## Numbers and formulas {#sec-rev-numbers}

Table[rev-formulas]: Formulas to be able to derive, with units.

| Quantity | Formula | Example |
|---|---|---|
| Seconds per day | 86,400 ≈ 10⁵ | |
| Seconds per month (30 days) | 2.592×10⁶ ≈ 2.5×10⁶ | |
| Average request rate | requests per day / 86,400 | 10⁸ per day ≈ 1,160 per second |
| Peak rate | average × peak factor (2 to 10) | 1,160 × 4 ≈ 4,600 per second |
| Storage | items × bytes per item × retention | 10⁹ × 1 KB = 1 TB |
| Bandwidth | requests per second × bytes per response | 1,000 × 100 KB = 100 MB/s = 800 Mbps |
| Little's law | concurrent requests = rate × latency | 2,000/s × 0.1 s = 200 in flight |
| Servers needed | peak rate / (capacity per server × target utilisation) | 4,600 / (200 × 0.6) ≈ 39 |
| Availability of serial parts | A = A₁ × A₂ × … | 0.999 × 0.999 = 0.998 |
| Availability of parallel parts | A = 1 − (1 − A₁)(1 − A₂) | two 0.99 nodes: 0.9999 |
| Downtime per year | (1 − A) × 525,600 minutes | 99.9% → 526 minutes (8.8 h) |
| Quorum overlap | R + W > N | N = 3, R = 2, W = 2 |
| Majority | ⌊N/2⌋ + 1 | 5 nodes: 3; tolerates 2 failures |
| Cache average latency | h × t_cache + (1 − h) × t_backend | 0.8 × 4 + 0.2 × 150 = 33.2 ms |
| Bloom filter bits per item | ≈ 1.44 log₂(1/p) | p = 1%: about 9.6 bits |
| Bidirectional BFS cost | ≈ 2·d^(L/2) vs d^L | d = 300, L = 4: 1.8×10⁵ vs 8.1×10⁹ |
| Consistent hashing movement | ≈ 1/(N + 1) of keys when adding a node | N = 10: about 9% |
| Exponential backoff | delay = min(cap, base × 2ⁿ) × random jitter | base 100 ms, n = 3: 800 ms |

**Latency numbers to remember** (orders of magnitude; see Chapter {ch:ch-estimation}): memory read about 100 ns; SSD random read about 100 μs; datacentre round trip about 500 μs; disk seek about 10 ms; cross-continent round trip about 100 to 150 ms.

## One-line trade-offs {#sec-rev-tradeoff}

- **Cache:** faster reads against possible staleness and invalidation work.
- **Replication:** availability and read scale against lag and failover complexity.
- **Sharding:** write and storage scale against cross-shard queries and rebalancing.
- **Denormalisation:** fast reads against duplicate data to keep consistent.
- **NoSQL:** scale and flexible shape against weaker queries and transactions.
- **Strong consistency:** simple reasoning against latency and lower availability under partition.
- **Eventual consistency:** availability and speed against surprising stale reads.
- **Queue:** smoothing and decoupling against delay and at-least-once duplicates.
- **Microservices:** independent teams and scaling against distributed-system costs.
- **Synchronous call:** simple and immediate against coupling and cascading failure.
- **Retries:** resilience to transient errors against load amplification and duplicates.
- **Two-phase commit:** atomicity across systems against blocking and coordinator dependency.
- **Saga:** availability across services against temporary inconsistency and compensation logic.
- **Fan-out on write:** fast reads against heavy writes for popular authors.
- **Fan-out on read:** cheap writes against slow reads.
- **Bloom filter:** tiny memory against false positives and no deletion.
- **LRU:** simple, adaptive eviction against vulnerability to scans.
- **Batch:** accuracy and throughput against latency; **stream:** freshness against operational complexity.
- **Vertical scaling:** simplicity against a ceiling and a single point of failure; **horizontal:** growth and redundancy against coordination.

::: revision
- [ ] I can recite the symptom table without looking.
- [ ] I can derive each formula and its units.
- [ ] I can state both sides of every trade-off in one breath.
:::
