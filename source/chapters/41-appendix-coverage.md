%label B
%derived Notebook chapter 15 coverage map (primer to notebook), extended to map each notebook section to its place in this book
%added a list of the topics this book adds beyond the notebook, with their locations
# Coverage Matrix: Notebook to Book {#app-coverage}

This appendix is the audit trail for the promise that **the notebook is the primary source for coverage**. Every section of the 51-page handwritten notebook (the book's source) appears in the left column; the right columns say where this book treats it. A topic is marked *expanded* when the book adds depth beyond the notebook's page.

Table[cov-main]: Notebook section to book section.

| Notebook section | Book location | Status |
|---|---|---|
| 1. The big picture: life of a request | {sec:sec-what}, {sec:sec-lifecycle} | Expanded |
| 1. Performance vs scalability | {sec:sec-perfscale} | Covered |
| 1. Latency vs throughput | {sec:sec-latency} | Expanded (percentiles) |
| 1. Scaling up vs scaling out | {sec:sec-scale} | Covered |
| 2. CAP theorem | {sec:sec-cap} | Expanded (PACELC, partitions) |
| 2. Consistency patterns | {sec:sec-consmodels}, {sec:sec-quorum} | Expanded |
| 2. Availability patterns | {sec:sec-availpatterns}, {sec:sec-failoverdesign} | Expanded |
| 2. Availability in numbers | {sec:sec-availmath} | Covered |
| 3. Layers in one minute | {sec:sec-layers} | Covered |
| 3. HTTP | {sec:sec-http} | Expanded (HTTP/1.1, 2, 3) |
| 3. TCP and UDP | {sec:sec-tcp}, {sec:sec-udp} | Expanded (QUIC, TLS) |
| 3. RPC | {sec:sec-rpc} | Covered |
| 3. REST | {sec:sec-rest}, {sec:sec-design} | Expanded |
| 4. DNS | {sec:dns} | Covered |
| 4. CDN | {sec:cdn} | Covered |
| 4. Load balancers | {sec:lb} | Expanded |
| 4. Reverse proxy | {sec:proxy} | Covered |
| 5. Separating web and application layers | {sec:sec-tiers} | Covered |
| 5. Microservices | {sec:sec-styles}, {sec:sec-boundaries} | Expanded |
| 5. Service discovery | {sec:sec-discovery} | Covered |
| 6. RDBMS and ACID | {sec:sec-acid}, {sec:sec-index} | Expanded |
| 6. Replication | {sec:sec-repl} | Covered |
| 6. Federation | {sec:sec-fed} | Covered |
| 6. Sharding | {sec:sec-shard} | Covered |
| 6. Denormalization | {sec:sec-fed} | Covered |
| 6. SQL tuning | {sec:sec-tuning} | Covered |
| 7. What is NoSQL? | {sec:sec-nosqlwhy} | Covered |
| 7. The four families | {sec:sec-families} | Covered |
| 7. SQL or NoSQL? | {sec:sec-sqlornosql} | Covered |
| 8. Why cache? | {sec:sec-whycache} | Covered |
| 8. When to update the cache | {sec:sec-updatestrat} | Expanded |
| 9. Asynchronous workflows | {sec:sec-whyasync}, {sec:sec-queues} | Expanded |
| 9. Security basics | {sec:sec-authn}, {sec:sec-authz}, {sec:sec-attacks} | Expanded |
| 10. Why estimate? | {sec:sec-whyest} | Covered |
| 10. Powers of two | {sec:sec-pow2} | Covered |
| 10. Latency numbers worth knowing | {sec:sec-latnum} | Covered |
| 10. Turning traffic into numbers | {sec:sec-traffic} | Covered |
| 11. The four steps | {sec:sec-steps} | Expanded |
| 11. The 20-point checklist | {sec:sec-checklist} | Covered |
| 12.1 Pastebin / URL shortener | {ch:ch-pastebin} | Expanded |
| 12.2 Twitter timeline and search | {ch:ch-twitter} | Expanded |
| 12.3 Web crawler and search | {ch:ch-crawler} | Expanded |
| 12.4 Mint | {ch:ch-mint} | Expanded |
| 12.5 Social network shortest path | {ch:ch-socialgraph} | Expanded |
| 12.6 Query cache (LRU) | {ch:ch-querycache} | Expanded |
| 12.7 Sales rank by category | {ch:ch-salesrank} | Expanded |
| 12.8 Scaling to millions on AWS | {ch:ch-aws} | Expanded |
| 13. OO design method, hash map, LRU, call center, cards, parking lot, chat | {ch:ch-oo-ds} | Expanded (code and tests) |
| 13. Circular array (open exercise) | {sec:sec-oo-circ} | Completed |
| 14. More questions to practise (23) | {ch:ch-practice} | Expanded |
| 14. Real-world architectures (17 systems) | {sec:sec-rw-systems} | Covered |
| 14. Company architectures (23 themes) | {sec:sec-rw-companies} | Covered |
| 14. Engineering blogs | {sec:sec-rw-blogs} | Covered (links not re-verified) |
| 15. Symptom to first fix | {sec:sec-rev-symptom} | Expanded |
| 15. Numbers and formulas | {sec:sec-rev-numbers} | Expanded |
| 15. Self-test: trade-offs | {sec:sec-rev-tradeoff} | Expanded |
| 15. Coverage map (primer to notebook) | {ch:app-coverage} | Superseded by this appendix |

## Topics added beyond the notebook {#sec-cov-added}

Every item below is **supplemental**: it was requested for a professional-level book and is not in the notebook. Each is labelled in its chapter opener as "added in this book".

Table[cov-added]: Supplemental topics and where they are treated.

| Topic | Location |
|---|---|
| Processes, threads, locks, races, deadlock | {ch:ch-concurrency} |
| Hash tables, B-trees, LSM trees, heaps, tries, Bloom filters, HyperLogLog | {ch:ch-ds} |
| Idempotency keys, pagination, versioning, webhooks | {sec:sec-idem}, {sec:sec-paging}, {sec:sec-version}, {sec:sec-webhook} |
| Rate limiting and token bucket | {sec:ratelimit} |
| Schema migrations (expand and contract) | {sec:sec-migrate} |
| PITR, backups versus replicas versus failover | {sec:sec-backup} |
| Quorums, consistent hashing, conflicts and repair | {sec:sec-quorum}, {sec:sec-conshash}, {sec:sec-conflict} |
| Cache failure patterns (stampede, penetration, hot keys) | {sec:sec-cachefail} |
| Outbox, sagas, dead-letter queues, back pressure | {sec:sec-outbox}, {sec:sec-retry}, {sec:sec-backpressure} |
| Clocks, fencing tokens, leader election, consensus, two-phase commit | {ch:ch-consensus} |
| Resilience patterns | {ch:ch-resilience} |
| Strangler pattern, architecture decision records | {sec:sec-strangler}, {sec:sec-adr} |
| Threat modelling, OAuth and tokens, secrets, privacy by design | {ch:ch-security} |
| Logs, metrics, traces, SLOs, incident response, RPO and RTO | {ch:ch-observability} |
| Containers, deployment strategies, autoscaling, cost, capacity planning | {ch:ch-cloud} |
| Payments and notification end-to-end exercises | {ch:ch-e2e} |
| Practice rubric and study plan | {sec:sec-pr-use}, {sec:sec-pr-plan} |

## Source content that could not be used {#sec-cov-gaps}

Nothing in the notebook text was unreadable. Two limitations are stated for honesty. First, the notebook's page of *company links* and *blog links* lists titles only; this book does not claim the linked articles say anything beyond those titles. Second, where the notebook's skeleton code contained defects (the LRU node without a key, constructors with wrong base-class calls), the book corrects them and says so ({sec:sec-oo-lru}, {sec:sec-oo-call}).
