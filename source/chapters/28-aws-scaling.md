%derived Notebook chapter 12.8 (scaling on AWS from one user to millions: the staged evolution from a single box, to separate web and database tiers, load balancing, read replicas, CDN, caches, auto scaling, asynchronism, SQL scaling patterns, NoSQL, and monitoring)
%added the reasoning that triggers each stage, cost and reliability trade-offs, multi-zone design, stateless tier rules, a capacity table, a migration order, and vendor-neutral equivalents
# Case Study: Scaling from One User to Millions {#ch-aws}

::: objectives
After this chapter you can:

- describe the staged evolution of a web system from one server to a multi-zone architecture;
- name the *trigger* (the metric or failure) that justifies each next step;
- map each stage to managed cloud building blocks and vendor-neutral equivalents;
- estimate capacity and cost at each stage and order the work sensibly;
- avoid premature complexity.
:::

::: prereq
Chapters {ch:ch-intro}, {ch:ch-entry} (load balancers, CDN), {ch:ch-scaling-sql}, {ch:ch-cache}, {ch:ch-async} and {ch:ch-cloud}.
:::

## Problem and approach {#sec-aws-req}

**The problem.** You start with a simple application and one user. Over time the user base grows to millions. How should the architecture evolve, and when should each change be made?

This chapter is a *narrative* case study rather than a single design: the lesson is the **order of decisions**. Each stage is introduced only when a measurable problem appears (high CPU, a saturated database, a single point of failure, slow pages for far-away users). Doing everything at once wastes money and adds failure modes; doing nothing until an outage wastes users' trust. Names of services follow the notebook's use of Amazon Web Services; every component has an equivalent elsewhere (Table {tab:aws-map}).

## Stage 1: one box (users: 1 to 1,000) {#sec-aws-s1}

Everything runs on one virtual machine: web server, application code and database, with a static public address from DNS. **Benefits**: cheap, simple to build and debug. **Risks**: one failure takes down everything; web and database compete for CPU, memory and disk; no isolation. Do keep **backups** and **infrastructure as code** even here (Chapter {ch:ch-cloud}), because rebuilding a hand-configured box is slow and error-prone.

**Trigger to move on**: resource contention, a need for safe deploys, or the first outage that mattered.

## Stage 2: separate tiers and vertical scaling (to about 10,000) {#sec-aws-s2}

Move the database to a **managed relational database** (backups, patching, failover handled by the provider) and keep the web tier separate. Scale **vertically** first: a larger instance is the quickest fix and needs no code change (Chapter {ch:ch-intro}). Put **static assets** (images, scripts, downloads) in **object storage** served by a **CDN**, taking the largest bytes off the web servers and reducing latency worldwide (Chapter {ch:ch-entry}).

**Choice of database.** Start with SQL unless the access pattern clearly demands otherwise (Chapter {ch:ch-sql}); use NoSQL for specific high-volume, simple-access data such as sessions or event logs (Chapter {ch:ch-nosql}).

**Trigger**: the largest instance is still saturated, or a single instance failure is unacceptable (vertical scaling has a ceiling and a single point of failure).

## Stage 3: load balancing and a stateless web tier (to about 100,000) {#sec-aws-s3}

{{fig aws-s3 | Stage 3: multiple stateless web servers behind a load balancer across two zones, a primary database with a standby replica, object storage and a CDN for static content.}}

Add a **load balancer** and **several web servers** across at least **two availability zones**, so that losing a zone does not take the site down (see {fig:aws-s3}). This requires the web tier to be **stateless**:

- user sessions move out of server memory into a shared store (a cache or database) or become signed tokens;
- uploaded files go to object storage, not local disks;
- configuration comes from the environment, not hand-edited files;
- health checks tell the load balancer which servers to use, and **graceful shutdown** drains connections.

Run the database as a **primary with a synchronous or asynchronous standby** in another zone for failover (Chapter {ch:ch-scaling-sql}; remember replication lag and the split-brain risk). Introduce **auto scaling** on a metric such as CPU or request rate, with a minimum of two instances.

**Trigger**: database CPU or connections saturate; read queries dominate; p99 latency grows.

## Stage 4: caching, read replicas and asynchronism (to about 1 million) {#sec-aws-s4}

{{fig aws-s4 | Stage 4: add an in-memory cache, read replicas, and a queue with background workers so slow work leaves the request path.}}

Because most traffic is reads, three moves relieve the database in order of effort:

1. **Cache** hot reads in an in-memory store using cache-aside (Chapter {ch:ch-cache}): usually the biggest single improvement.
2. **Read replicas**: send read-only queries that tolerate small staleness to replicas, writes to the primary. Remember read-your-writes (Chapter {ch:ch-distdata}).
3. **Asynchronism**: move slow or non-urgent work (emails, image resizing, reports) onto a queue processed by workers (Chapter {ch:ch-async}); pre-compute expensive pages in the background; respond to users with a "we're working on it" status where appropriate. Workers auto scale on queue depth.

Add **monitoring and alerts** now (Chapter {ch:ch-observability}): without metrics you will not know which stage to fix next.

**Trigger**: write volume or data size outgrows one primary; a single table is huge; replicas lag.

## Stage 5: scaling the data tier (millions of users) {#sec-aws-s5}

When one primary cannot take the writes or hold the data, apply the SQL scaling patterns (Chapter {ch:ch-scaling-sql}) in this order of preference, each adding operational cost:

1. **Tune and index** queries; archive old data; denormalise carefully for hot reads.
2. **Federation**: split databases by function (users, orders, products).
3. **Sharding**: partition large tables by a key such as user id (and pay the cross-shard query and rebalancing costs).
4. **NoSQL** for data whose access pattern is simple and enormous (sessions, feeds, events), with query-first modelling (Chapter {ch:ch-nosql}).

At the same time: multiple **regions** if latency to far users or regional disaster tolerance requires it (with the consistency complications of multi-region writes, Chapter {ch:ch-distdata}); **service decomposition** where team or scaling boundaries justify it (Chapter {ch:ch-microservices}); and **automation** (deployment pipelines, autoscaling, runbooks).

## Capacity and cost along the way {#sec-aws-cap}

Table[aws-cap]: An illustrative capacity ladder (all numbers are assumptions to practise estimation, not benchmarks).

| Users (daily active) | Requests/s (avg, peak) | Typical architecture | Main risk |
|---|---|---|---|
| 1,000 | 0.1, 1 | One box | Single failure |
| 10,000 | 1, 10 | Web + managed DB, CDN | DB and web contend |
| 100,000 | 10, 100 | LB, 2+ web servers, DB standby | DB saturation |
| 1,000,000 | 100, 1,000 | + cache, read replicas, queue | Write volume |
| 10,000,000 | 1,000, 10,000 | + sharding or NoSQL, multi-zone, autoscale | Operational complexity |

**Worked arithmetic.** 1 million daily users, 30 requests each per day: 3×10⁷ requests/day ÷ 86,400 ≈ 350 per second average; with a peak factor of 5, about 1,750 per second. If one web instance serves 200 per second at 50% target utilisation (100 per second), you need 1,750 / 100 ≈ 18 instances at peak, plus one zone's worth of spare (a third more) for zone failure: about 24. If 80% of reads hit the cache, the database sees roughly 20% of read traffic.

::: worked
**Which step first?** Symptoms: p99 latency doubled; the database CPU is 90%; web servers at 30% CPU; 85% of the DB load is the same 20 queries. Candidate actions: (a) more web servers: no effect, the web tier is not the bottleneck; (b) bigger database: works short term, expensive; (c) cache the hot queries: attacks 85% of the load directly and cheaply; (d) shard: heavy and premature. Choose (c) first, then (b) if necessary, and schedule (d) only when writes demand it. The method: *measure, find the bottleneck, apply the cheapest effective fix.*
:::

## Vendor-neutral map {#sec-aws-map}

Table[aws-map]: Building blocks and equivalents.

| Role | AWS example | Generic equivalent |
|---|---|---|
| Compute | EC2, containers, functions | Virtual machines, container orchestrator, functions |
| Load balancer | Elastic Load Balancing | NGINX, HAProxy, cloud LB |
| Relational DB | RDS, Aurora | Managed PostgreSQL or MySQL |
| NoSQL | DynamoDB | Cassandra, MongoDB, other key-value stores |
| Cache | ElastiCache | Redis, Memcached |
| Object storage and CDN | S3, CloudFront | Any object store and CDN |
| Queue | SQS, SNS | RabbitMQ, Kafka, managed brokers |
| DNS | Route 53 | Any authoritative DNS with health checks |
| Monitoring | CloudWatch | Prometheus, Grafana, OpenTelemetry |

## Failure thinking at every stage {#sec-aws-fail}

Ask at each stage "what is the single point of failure now?" Stage 1: everything. Stage 2: the web server and the one database instance. Stage 3: the load balancer is managed and redundant; the database primary remains (mitigated by standby). Stage 4: the cache (a cold cache must not crush the database: Chapter {ch:ch-cache}). Stage 5: shard placement metadata, cross-region links. Practise failure injection ("game days", Chapter {ch:ch-resilience}). Backups are not replicas: test restores (Chapter {ch:ch-scaling-sql}).

::: failure
**Failure modes (summary).** Stateful web servers blocking horizontal scaling; autoscaling without limits causing a cost or database connection storm; replica lag causing stale reads; cache loss sending a miss storm to the database; premature sharding; missing alerts; deployment without rollback; single-zone design.
:::

::: misconception
- *"Scale-out from day one."* Start simple; add each stage when a metric demands it.
- *"Autoscaling fixes everything."* It scales stateless tiers; databases need other strategies, and scaling the web tier can overload the database.
- *"Multi-AZ means backups."* It protects against zone loss, not against a bad delete.
:::

::: interview
**Q1. Your site is slow with growing traffic; what do you do?** Measure first; find the bottleneck; apply cache, replicas, queue or scaling accordingly, cheapest first.

**Q2. Why must web servers be stateless?** So any server can handle any request, allowing load balancing, autoscaling and replacement without losing sessions.

**Q3. When would you shard?** When a single primary cannot handle write volume or data size after tuning, caching, replicas and federation.

**Q4. What is the first step to improve availability?** Remove single points of failure: multiple servers across zones behind a load balancer, a database standby, and tested backups.
:::

::: exercise
1. 5 million daily users, 20 requests each, peak factor 4. Compute average and peak requests per second, and the number of instances if each handles 150 requests per second at 60% target utilisation, with one-third spare for a zone loss.
2. Your database has 70% reads and a 90% cache hit ratio is achieved on reads. What fraction of the original database operations remain?
3. List what must change in an application before it can run on multiple web servers.
4. Which stage addresses "a deploy takes down the site for 10 minutes"? Describe how.

**Answers.**
1. 10⁸ requests/day / 86,400 ≈ 1,160 per second average; peak ≈ 4,630. Each instance: 150 × 0.6 = 90. 4,630/90 ≈ 52; add one third ≈ 69 instances.
2. Reads become 0.7 × 0.1 = 0.07; writes remain 0.30; total 0.37, so 37% of the original operations remain.
3. Externalise sessions, store uploads in shared object storage, use environment configuration, ensure no local state or scheduled jobs run on every node, add health checks and graceful shutdown.
4. Stage 3: multiple servers behind a load balancer allow rolling or blue-green deployments with health checks, so servers are updated a few at a time.
:::

::: summary
- Evolve in stages, each triggered by a measured problem.
- A stateless web tier plus load balancer across zones is the foundation of horizontal scaling.
- Cache, read replicas and queues relieve the database before sharding.
- Always identify the next single point of failure and the next bottleneck.
- Managed services map to open equivalents; the principles are portable.
:::

::: revision
- [ ] I can list the stages and their triggers.
- [ ] I can do the capacity arithmetic.
- [ ] I can explain why statelessness matters.
:::
