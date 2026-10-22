%derived Notebook chapter 12.8 (scaling to millions of users on AWS: the stage-by-stage table) and chapter 10 (capacity estimation)
%added containers and orchestration, infrastructure as code, deployment strategies (rolling, blue-green, canary, feature flags), autoscaling, managed building blocks, cost estimation and capacity planning, operational ownership
# Deployment, Cloud Infrastructure, Cost and Capacity {#ch-cloud}

::: objectives
After this chapter you can:

- explain virtual machines, containers and orchestration, and why infrastructure is defined as code;
- choose a deployment strategy (rolling, blue-green, canary) and use feature flags to separate deployment from release;
- design autoscaling that avoids oscillation and respects slow-starting capacity;
- estimate cloud cost for a design and spot the usual cost surprises;
- run a capacity-planning cycle with load tests and headroom, and describe operational ownership.
:::

::: prereq
Chapters {ch:ch-estimation}, {ch:ch-entry}, {ch:ch-resilience}, {ch:ch-microservices} and {ch:ch-observability}.
:::

::: terms
Virtual machine (VM)
: A software-emulated computer running its own operating system on shared hardware.

Container
: A packaged process with its dependencies, isolated by the host operating system and sharing its kernel; lighter than a VM.

Orchestrator (Kubernetes)
: A system that schedules containers onto machines, restarts them, scales them and wires up networking.

Infrastructure as code (IaC)
: Describing servers, networks and services in versioned files that tools apply automatically.

CI/CD
: Continuous integration (automatically build and test every change) and continuous delivery or deployment (automatically release it).

Region / availability zone (AZ)
: A geographic cloud area, and an isolated data centre within it.
:::

## From servers to platforms {#sec-platforms}

Running software requires machines. The history is a series of trades between control and effort:

- **Physical servers** you own: maximum control, long lead times, you pay for peak all year.
- **Virtual machines** (cloud instances): rented by the hour, resizable in minutes, still full operating systems you patch.
- **Containers**: package the application and its libraries into an image that runs the same everywhere; start in seconds; many per machine. An **orchestrator** such as **Kubernetes** decides where containers run, restarts failures, rolls out versions, and scales them.
- **Serverless / functions**: you supply code, the provider runs it on demand and scales to zero; you pay per invocation. Excellent for spiky, event-driven work; limits include cold starts, execution time caps and less control.
- **Managed services**: the provider runs the database, queue or cache for you (backups, patching, failover included), trading money and some control for far less operational work.

The right level is the one where your team's scarce attention is spent on the product, not the plumbing. A small team should lean hard toward managed services; a very large one may build its own for cost or control.

**Infrastructure as code.** Define networks, machines, databases and permissions in files (Terraform, CloudFormation, Pulumi, Kubernetes manifests) kept in version control and applied by a pipeline. Benefits: reviewable changes, reproducible environments (staging resembles production), disaster recovery by re-creating from code, and no undocumented manual changes ("configuration drift"). Treat secrets and state files with care (Chapter {ch:ch-security}).

## Shipping changes safely {#sec-deploy}

Most outages follow a change. The pipeline's job is to make changes **small, frequent, tested and reversible**.

**CI/CD pipeline:** commit; build; unit and integration tests; static analysis and security scans; package an immutable artifact (a container image); deploy to staging; automated tests; deploy to production in stages; verify with metrics; roll back automatically on regressions. **Immutable artifacts** (never patch a running server; replace it) make rollback simply "deploy the previous image".

{{fig deploy-strategies | Rolling, blue-green and canary deployments. Rolling replaces instances gradually; blue-green switches all traffic between two full environments; canary sends a small share of traffic to the new version first.}}

Table[deploystrat]: Deployment strategies compared.

| Strategy | How | Rollback | Extra capacity | Risk |
|---|---|---|---|---|
| Recreate | Stop old, start new | Redeploy old | None | Downtime |
| Rolling | Replace a few instances at a time | Roll forward or back gradually | Small | Mixed versions run together |
| Blue-green | Two identical environments; flip the router | Flip back instantly | A full second environment | Database changes must work for both versions |
| Canary | Send 1%, 5%, 25%, 100% to the new version, watching metrics | Route back to 0% | Small | Needs good automated metrics and enough traffic |

Because old and new versions **run side by side** during any gradual rollout, every change must be **backward and forward compatible**: schema migrations follow expand and contract (Chapter {ch:ch-sql}); APIs change additively (Chapter {ch:ch-api}); messages tolerate unknown fields.

**Feature flags** separate *deployment* (code reaches production, switched off) from *release* (the feature is enabled for users). They allow gradual exposure by percentage or user group, instant kill switches (also the degradation controls of Chapter {ch:ch-resilience}), and testing in production safely. Costs: flag debt (remove old flags), combinatorial testing, and the flag service becoming a dependency (default to a safe value if it is unreachable).

## Autoscaling {#sec-autoscale}

**Autoscaling** adds and removes instances automatically as load changes, so you pay for what you use and survive spikes. Three approaches: **reactive** (scale when a metric crosses a threshold: CPU, requests per instance, queue age), **scheduled** (known patterns: scale up before 9 a.m.), and **predictive** (forecast from history).

Pitfalls and rules:

- **Scale on a metric that tracks real load**, ideally one that *leads* trouble: requests per instance or queue age beat CPU for I/O-bound services.
- **Slow starts matter.** If a new instance needs two minutes to boot, warm caches and pass health checks, reactive scaling lags the spike. Scale earlier (a lower threshold), keep a **buffer of spare capacity**, use pre-warmed pools, and use faster-starting containers.
- **Avoid flapping**: use **cooldowns** and hysteresis (scale out at 60% utilisation, scale in only below 30%), and scale in slowly.
- **Set maximums** to cap cost and to protect downstream systems: scaling the web tier tenfold means ten times the database connections (Chapter {ch:ch-scaling-sql}); autoscaling a stateless tier does nothing for a saturated database.
- **State does not autoscale easily**: databases, caches and queues are scaled deliberately (replicas, shards), not by a threshold rule.

## A reference path: scaling a system up {#sec-scalingpath}

The notebook's final design problem walks one system from a handful of users to millions. Condensed here as a decision table; the full worked version is in {ch:ch-aws}.

Table[scalingpath]: A typical growth path and the next bottleneck at each stage.

| Stage (users) | Typical architecture | Next bottleneck | Next step |
|---|---|---|---|
| 1 to 100s | One server runs web, app and database | Everything shares one machine | Separate database; use a managed service |
| ~10,000 | Web servers behind a load balancer; managed database with a replica; object storage for files; CDN | Database reads | Cache; read replicas |
| ~100,000 | Stateless app tier autoscaled; cache; queue and workers for slow jobs | Database writes and size | Tune; federate; consider sharding |
| ~1,000,000 | Multiple AZs; sharded or federated data; search and analytics stores; observability and deploy automation | Operational complexity, cost | Platform teams; cost management |
| 10,000,000 and up | Multi-region; custom data stores; cells; extensive automation | Global latency, blast radius, cost | Regional isolation, data residency, specialisation |

## Cost: estimation and habits {#sec-cost}

Cloud makes cost *variable and visible*, and also easy to waste. A cost estimate follows the same pattern as capacity estimation (Chapter {ch:ch-estimation}): resources × unit price × time. Price lists change frequently, so use the provider's **current pricing calculator** and treat the figures below as illustrative arithmetic only.

::: worked
**A monthly estimate (illustrative prices, check current ones).** Assume: 10 application instances at $0.10 per hour; a database at $1.00 per hour with one replica at the same price; 5 TB of object storage at $0.023 per GB-month; 20 TB of outbound transfer at $0.09 per GB; a managed cache at $0.50 per hour. A month is about 730 hours.

- Compute: 10 × 0.10 × 730 = $730.
- Database: 2 × 1.00 × 730 = $1,460.
- Cache: 0.50 × 730 = $365.
- Storage: 5,000 GB × 0.023 = $115.
- Transfer out: 20,000 GB × 0.09 = $1,800.
- Total ≈ $4,470 per month, and **the single largest line is data transfer**, which many designs forget. A CDN (often cheaper per GB than origin egress), compression and keeping chatty traffic inside one zone each reduce it. Also notice what is *not* here: observability ingestion, load balancers, NAT gateways, cross-zone traffic and support plans, which routinely add 20 to 40 per cent.
:::

Habits that keep costs sane: **tag** every resource with owner and project so cost is attributable; budget alerts; **right-size** instances using real utilisation; use **committed-use or reserved discounts** for the steady base load and **spot (interruptible) instances** for fault-tolerant batch work; **delete** orphans (unattached disks, old snapshots, idle load balancers); **tier storage** (hot, infrequent, archive) with lifecycle rules; watch **egress** and **cross-AZ/region traffic**; log and trace selectively. And treat cost as a **design requirement**: "cost per thousand requests" is a metric worth tracking beside latency.

## Capacity planning {#sec-capacityplan}

Capacity planning ensures the system can meet next quarter's demand without over-buying. It is a cycle:

1. **Forecast demand**: growth trends, marketing events, seasonality (Chapter {ch:ch-estimation}).
2. **Measure capacity**: **load test** realistic traffic against a production-like environment, increasing load until latency or errors break the SLO; record the maximum sustainable throughput *per instance* and the first bottleneck. Include **soak tests** (hours at load, to find leaks) and **spike tests**.
3. **Compute needs** with headroom: peak forecast ÷ per-instance capacity ÷ target utilisation (50% to 70%), plus **N+1 or N+AZ** spare capacity for failures and deployments.
4. **Provision** (or configure autoscaling limits), and ensure **quotas** (cloud account limits) are raised in advance, including in the DR region.
5. **Monitor utilisation and saturation**, compare with the forecast, revisit.

::: worked
**Per-instance capacity and fleet size.** A load test shows one instance sustains 800 requests per second before p99 exceeds the SLO. Forecast peak next quarter: 12,000 requests per second. Target utilisation 60%: usable per instance = 480. Instances = 12,000 / 480 = 25. To survive the loss of one of three zones, size so that two zones carry the load: 25 × 3 / 2 ≈ 38 instances, about 13 per zone. If each costs $0.10 per hour, the fleet costs about 38 × 0.10 × 730 = $2,774 per month; the zone-failure tolerance costs 13 extra instances, about $949 per month, the price of the availability target.
:::

## Operational ownership {#sec-ownership}

Software that nobody owns breaks in the night with nobody responsible. Mature organisations follow **"you build it, you run it"**: the team that writes a service is on call for it, which aligns incentives (a service that pages its authors gets more reliable). Supporting practices: a **service catalogue** (owner, on-call, dashboards, runbooks, dependencies, tier), **production-readiness reviews** before launch (monitoring, alerts, capacity, rollback, security, DR), healthy **on-call** (rotation, handover, a cap on pages per shift, compensation), **runbooks** that are tested, and a **platform team** providing paved roads (templates, pipelines, observability) so product teams do not each reinvent infrastructure.

::: failure
**Failure modes.** A bad deploy to all instances at once; incompatible schema and code versions during a rollout; autoscaler oscillating, or scaling the app tier until the database falls over; configuration drift between environments; a flag service outage disabling features; a cost spike from a runaway job, an unbounded log, or egress; quota exhaustion during a spike or in the DR region; deployment pipeline credentials compromised; capacity plans based on averages and failing at peak; nobody knowing who owns a service.
:::

::: warning
**Common mistakes.** Deploying on Friday afternoon without a rollback plan. Testing in a staging environment that differs from production. Treating autoscaling as capacity planning. Ignoring egress and cross-zone costs. Running one environment manually "just this once". Starting with Kubernetes for a team of three because it is fashionable.
:::

::: misconception
- *"The cloud scales automatically."* Only the parts you configure (and only within quotas, and not your database).
- *"Containers make applications portable and therefore simple."* They simplify packaging; orchestration adds its own complexity.
- *"Blue-green deployment makes releases risk-free."* Shared databases and state still have to work for both versions.
- *"Cloud is always cheaper."* It is cheaper for variable load and small teams; steady, huge workloads can cost more than owned hardware.
:::

::: interview
**Q1. Rolling, blue-green and canary: when would you use each?**
Rolling: default, low extra capacity. Blue-green: instant switch and rollback when you can afford two environments. Canary: risky changes at scale, checking real metrics on a small share first.

**Q2. How do you deploy a database change without downtime?**
Expand and contract: backward-compatible schema first, dual-write, backfill, switch reads, remove the old structure later; deploy code compatible with both versions throughout.

**Q3. How would you design autoscaling for a web tier?**
Scale on requests per instance or queue age with a lower threshold than the danger point, cooldowns and hysteresis, max limits to protect the database, and warm capacity for slow starts.

**Q4. How would you estimate and reduce cloud cost?**
List resources by unit price and usage; find the dominant lines (often egress, storage, database); tag, right-size, use commitments for base load and spot for batch, tier storage, use a CDN, and delete orphans.
:::

::: exercise
1. Load test: one instance sustains 500 requests/s. Forecast peak is 9,000 requests/s; target utilisation 70%; two zones, must survive losing one. How many instances in total?
2. A canary at 5% shows an error rate of 0.9% versus 0.2% on the stable version, over 2,000 requests. Should you continue? What additional information do you want?
3. Estimate the monthly cost of transferring 50 TB out at $0.08 per GB, then show how a CDN with a 90% offload at $0.04 per GB changes it (ignore request fees).
4. Explain how a feature flag helps with a risky release and name two costs of flags.

**Answers.**
1. Per instance usable = 500 × 0.7 = 350. Needed = 9,000 / 350 ≈ 26 instances. Surviving the loss of one of two zones means each zone alone must carry everything: 26 per zone, 52 in total.
2. Probably no: 0.9% is more than four times 0.2%; with 100 canary requests per error the difference is likely real (about 18 errors vs 4 expected from 2,000 requests). Check statistical significance, error types, latency and whether the canary traffic is comparable; halt or roll back.
3. Direct: 50,000 GB × 0.08 = $4,000. With CDN: origin egress = 10% × 50,000 × 0.08 = $400 plus CDN delivery 50,000 × 0.04 = $2,000 (CDN delivery applies to all bytes), total $2,400: a saving of about 40% here; the saving grows if CDN prices drop with volume or caching removes more origin traffic.
4. A flag lets code ship off, then be enabled for 1%, 10%, then all users, and be turned off instantly if metrics degrade. Costs: stale flags accumulate (technical debt) and the number of untested combinations grows; the flag service becomes a dependency.
:::

::: summary
- Choose the level of platform (VMs, containers, serverless, managed) that frees your team's attention; define infrastructure as code.
- Ship small, tested, reversible changes; use rolling, blue-green or canary with compatible versions; feature flags separate deploy from release.
- Autoscale stateless tiers on leading metrics with cooldowns and limits; protect state tiers.
- Estimate cost from unit prices and watch egress; plan capacity from load tests with headroom and zone-failure margin.
- Teams own what they run; production-readiness reviews and a platform team make that sustainable.
:::

::: revision
- [ ] I can compare rolling, blue-green and canary.
- [ ] I can size a fleet from a load test, headroom and zone tolerance.
- [ ] I can estimate a monthly cost and find the dominant line.
- [ ] I can design autoscaling thresholds without flapping.
:::

::: supplement
**Further reading.** The AWS Well-Architected Framework (and the equivalents from other providers) for current guidance; Jez Humble and David Farley, *Continuous Delivery*; Kief Morris, *Infrastructure as Code*; the FinOps Foundation's framework for cloud cost management; Google's SRE Workbook on canarying releases.
:::
