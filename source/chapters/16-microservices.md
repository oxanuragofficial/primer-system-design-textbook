%derived Notebook chapter 5 (separating web and application layers, microservices, service discovery, the comparison table and the drawbacks of each)
%added monolith versus modular monolith, bounded contexts and data ownership, service communication, the strangler migration, architecture diagrams, architecture decision records and API-contract testing
# Application Architecture and Microservices {#ch-microservices}

::: objectives
After this chapter you can:

- separate web and application tiers and explain why the application tier is stateless;
- compare a monolith, a modular monolith and microservices, and decide which suits a team and a problem;
- draw service boundaries around business capabilities and assign data ownership;
- explain service discovery and the communication patterns between services;
- migrate gradually with the strangler pattern, and record decisions in architecture decision records.
:::

::: prereq
Chapters {ch:ch-api} (contracts), {ch:ch-entry} (gateway, balancing), {ch:ch-async} (events, sagas) and {ch:ch-resilience}.
:::

::: terms
Monolith
: An application built and deployed as a single unit.

Microservice
: A small, independently deployable service owning one business capability and its data.

Bounded context
: A part of the business with its own vocabulary and model; a natural service boundary.

Service discovery
: The mechanism by which services find the current network address of other services.

Strangler pattern
: Replacing a legacy system piece by piece by routing more and more traffic to new components.

Architecture decision record (ADR)
: A short document capturing one decision, its context, alternatives and consequences.
:::

## Layers and tiers {#sec-tiers}

A web application usually has three logical layers: **presentation** (what the user sees), **application or business logic** (the rules), and **data** (storage). Putting web handling and business logic into **separate tiers** has benefits (from the notebook): they scale **independently** (many web servers for thin request handling, fewer heavy application servers); each can be **deployed and secured** separately (the application tier has no public address); and **teams** can own them separately. A **platform layer** can offer shared services (authentication, notifications) used by all.

{{fig tiers | Separating tiers. A web tier handles HTTP and delegates to an application tier of workers, which talk to the data stores. Each tier scales on its own.}}

The key property of the application tier is that it is **stateless**: nothing user-specific is kept in a server's memory, so any instance can serve any request (Chapter {ch:ch-intro}). State lives in databases, caches and queues. That is what lets you add instances during a spike and replace them when they fail.

## Monolith, modular monolith, microservices {#sec-styles}

A **monolith** is one deployable application containing all features. It is simple to build, test, run and debug (one process, one database, local function calls, real transactions), and is often the *right* starting point. It strains as teams and code grow: every change redeploys everything, a bug in one module can crash all, one language and framework for all, and scaling means scaling the whole thing.

**Microservices** split the system into many small services, each owning one business capability and its data, communicating over the network, deployed independently. Benefits: independent deployment and scaling; teams that own services end to end; technology choice per service; fault isolation if designed well. Costs (the notebook's "drawbacks" and more):

- **Distributed system complexity**: every call can be slow, fail or time out (Chapters {ch:ch-resilience}, {ch:ch-consensus}).
- **Data consistency**: no cross-service transactions; use events, outbox and sagas (Chapter {ch:ch-async}).
- **Operational overhead**: many deployments, pipelines, dashboards, on-call rotations; need strong automation, observability ({ch:ch-observability}) and platform tooling.
- **Network latency and chattiness**: a screen needing 20 service calls is slow and fragile.
- **Testing and debugging** across services is harder; versions must stay compatible.
- **Organisational demands**: small autonomous teams and clear ownership.

A middle path is the **modular monolith**: one deployable unit, but strictly separated modules with explicit interfaces and private data, so it can be split later if needed. Many successful products stay here for years.

{{fig styles | Three architectures. The monolith is one unit; the modular monolith adds enforced module boundaries inside one deployable; microservices split into independently deployed services, each with its own data.}}

Table[styles]: Choosing an architecture.

| Factor | Monolith / modular monolith | Microservices |
|---|---|---|
| Team size | Up to a few dozen engineers | Many teams needing autonomy |
| Early-stage product | Strong fit: change is fast, boundaries unknown | Premature: boundaries guessed wrongly are costly |
| Deployment | Single, simple | Many, needs automation |
| Scaling needs | Uniform | Very different per component |
| Transactions | Easy (one database) | Hard (sagas, eventual consistency) |
| Operational maturity needed | Low | High |

::: note
**Clarification: microservices are an organisational tool as much as a technical one.** The notebook lists microservices as a way to scale and to let teams work independently. The honest summary is that they *trade technical simplicity for organisational independence*. If you do not have the organisational problem (many teams blocking each other), you pay the cost without the benefit. A well-known rule of thumb, *Conway's law*, says systems tend to mirror the communication structure of the organisation that builds them; design the teams and the architecture together.
:::

## Drawing the boundaries {#sec-boundaries}

Bad boundaries cause more pain than bad technology. A **distributed monolith** (services so tightly coupled that they must be deployed together and call each other constantly) has all the costs and none of the benefits.

Guidelines:

- **Follow business capabilities** (orders, payments, catalogue, shipping), not technical layers ("the database service"). Domain-driven design calls these **bounded contexts**: each has its own model of, say, a "customer" (billing cares about invoices, support about tickets).
- **High cohesion inside, loose coupling between.** Things that change together live together. If two services always change in the same release, they are one service.
- **Each service owns its data.** No other service reads its tables directly. Others use its API or consume its events. This is *the* rule that makes independent change possible; shared databases recreate tight coupling.
- **Prefer coarse over fine** at first. It is easier to split a service later than to merge many tiny ones.
- **Design for failure at every boundary**: timeouts, retries, idempotency, fallbacks.

### Data ownership and duplication

Owning data means other services cannot join across it. They need *copies*: for example, the order service stores the product name and price **as of purchase** (a snapshot, which is *correct* behaviour for an order), and the search service keeps a read-optimised copy built from product events. Duplication is accepted; the rules are that **one service is the authority** for each fact, others hold derived copies that are updated by events, and everyone tolerates short staleness.

## Communicating between services {#sec-svcomm}

Table[svcomm]: Ways services talk.

| Style | How | Use for | Risk |
|---|---|---|---|
| Synchronous request/response | REST or gRPC call | Queries needing an immediate answer | Latency adds up; failures propagate; availability multiplies down |
| Asynchronous messaging | Queue or topic | Commands that can wait, notifications | Eventual consistency, duplicates, debugging |
| Event-driven | Publish facts ("OrderPlaced") that others react to | Decoupling, many consumers | Hard to see the whole flow; event schema evolution |
| API composition / BFF | A backend-for-frontend aggregates several calls | Screens needing data from many services | The aggregator becomes a bottleneck or hides logic |

Chains of synchronous calls multiply failure probability and latency: five services in a chain, each 99.9% available, give about 99.5% overall. Prefer **fewer hops**, **parallel calls**, and **asynchronous events** for things that need not be immediate. A **service mesh** (sidecar proxies beside each service) can move retries, timeouts, mutual TLS and telemetry out of application code; it is useful at scale and adds its own complexity.

## Service discovery {#sec-discovery}

Instances come and go (autoscaling, deploys, crashes), so addresses cannot be hard-coded. **Service discovery** lets a caller find healthy instances by *name*.

{{fig discovery | Service discovery. Instances register with a registry and send heartbeats; a caller asks the registry for the healthy instances of a service and calls one directly.}}

How it works: when an instance starts it **registers** (name, address, port, metadata) with a **registry**; it renews with **heartbeats** or the registry actively runs **health checks**; unhealthy or silent instances are removed. Callers either **look up** addresses and cache them (client-side discovery, with client-side load balancing) or send requests to a **router or load balancer** that consults the registry (server-side discovery). Tools: **Consul**, **etcd**, **ZooKeeper** (the notebook's examples, built on consensus, Chapter {ch:ch-consensus}), Kubernetes' built-in service objects and DNS, and cloud-provider equivalents. Plain **DNS** can serve as a simple registry, with the caveat of TTL caching (Chapter {ch:ch-network}).

Drawbacks (notebook): the registry is itself critical infrastructure that must be highly available, and clients must tolerate stale results and register or deregister correctly.

## Migrating: the strangler pattern {#sec-strangler}

Rewriting a working system from scratch is notoriously risky. The **strangler fig** pattern grows new functionality around the old system: put a **routing layer** (a gateway or proxy) in front, build one capability at a time as a new service, route that capability's traffic to it, and retire the old code when nothing uses it.

{{fig strangler | The strangler pattern. A routing facade sends some paths to new services and the rest to the legacy system; over time more routes move until the legacy system can be removed.}}

Practical steps: pick a capability with clear boundaries and modest risk; build the new service behind the facade; **migrate data carefully** (dual-write or change-data-capture, with reconciliation); run both and **compare results** (shadow traffic); move traffic gradually (1%, 10%, 50%, 100%) with instant rollback; delete the old path. Each step is reversible, and value is delivered continuously.

## Recording architecture {#sec-adr}

Decisions must be understandable to the people who inherit them. Two lightweight tools:

**Architecture diagrams.** The *C4 model* uses four zoom levels: **context** (the system among users and other systems), **containers** (deployable units: web app, services, databases), **components** (inside one container), **code**. Draw at the right level, label every arrow with *what flows and how* (HTTP, event), and keep one purpose per diagram.

{{fig c4 | A container-level diagram for a shop. Each box is deployable; each arrow is labelled with the protocol and purpose.}}

**Architecture decision records (ADRs).** A short, dated file per decision, stored with the code:

```text
ADR-014: Use a transactional outbox for order events
Status:   Accepted (2026-10-02)
Context:  Orders must be saved and OrderPlaced published atomically. We run
          PostgreSQL and a managed message broker; no distributed transactions.
Options:  (1) publish after commit  - can lose events on a crash
          (2) 2PC across DB and broker - unsupported, blocking
          (3) outbox table + relay    - at-least-once, needs idempotent consumers
Decision: Option 3.
Consequences: + no lost events  - consumers must deduplicate; relay is a new
          component to monitor. Revisit if event volume exceeds 5,000/s.
```

An ADR records *why*, the alternatives rejected, and when to revisit; it turns "who decided this and why?" from folklore into documentation. Update the status (Superseded by ADR-031) rather than rewriting history.

::: failure
**Failure modes.** Distributed monolith (changes ripple across services); a "chatty" service graph with latency and failure amplification; a shared database coupling services; the registry down or stale; version skew between services during deployment (old caller, new callee); a service becoming a bottleneck because everything depends on it; inconsistent data between copies; no one owning a service when it breaks at 3 a.m.; migration stalled half-way with two systems to maintain.
:::

::: warning
**Common mistakes.** Starting with microservices before understanding the domain. Splitting by technical layer. Letting services read each other's databases. Synchronous call chains everywhere. No tracing, so nobody can see a request's path. Creating a service per entity instead of per capability. Skipping contract tests.
:::

::: supplement
**Contract testing.** When services deploy independently, you need confidence that a change to a provider will not break its consumers. **Consumer-driven contract tests** let each consumer record the requests it makes and the responses it relies on; the provider's pipeline replays them and fails the build if a change breaks any. This gives fast, reliable feedback without standing up the whole system for end-to-end tests. Combine with additive-only API changes (Chapter {ch:ch-api}) and gradual rollouts.
:::

::: misconception
- *"Microservices are more scalable."* They allow independent scaling of parts; a monolith can scale horizontally too.
- *"Every company should use microservices."* They solve organisational scaling problems; small teams usually should not.
- *"Services are small, so each can use its own database engine freely."* Possible, but every extra technology is an operational cost.
- *"We can always split later, so design does not matter now."* Good module boundaries make splitting possible; a tangled monolith is hard to split.
:::

::: interview
**Q1. Monolith or microservices for a new startup?**
Start with a (modular) monolith: boundaries are unknown, the team is small, transactions are simple. Extract services when a clear organisational or scaling need appears.

**Q2. How do you decide a service boundary?**
By business capability and bounded context, with data owned by one service, high cohesion inside and low coupling outside; things that change together stay together.

**Q3. How do services find each other?**
Service discovery: instances register with a registry (Consul, etcd, ZooKeeper, Kubernetes) and heartbeat; callers resolve healthy instances by name, client-side or through a load balancer.

**Q4. How would you migrate a legacy monolith?**
Strangler pattern behind a routing facade, one capability at a time, with careful data migration, shadow comparisons, gradual traffic shifts and rollback.
:::

::: exercise
1. A shop has Orders, Payments, Inventory and Search. Propose service boundaries, name each service's data, and say which interactions are synchronous and which asynchronous.
2. Five services in a synchronous chain have availability 99.9% each. Compute the chain's availability and propose two ways to improve it.
3. Write an ADR for "use a message queue between the order service and the email service".
4. Two services always change together and share tables. What is your recommendation?

**Answers.**
1. Orders (orders, order lines), Payments (transactions), Inventory (stock levels), Search (read-optimised index built from product events). Synchronous: Orders asks Inventory to reserve stock and Payments to charge (fast, needs an immediate answer); asynchronous: OrderPlaced event to Search indexing and to Email; saga for the order flow with compensations.
2. 0.999⁵ ≈ 0.995 (99.5%, about 44 hours per year). Improve by removing hops (merge or parallelise), making some calls asynchronous, adding fallbacks, caching, and redundancy.
3. Context: email is slow and may fail; orders should not wait. Options: synchronous call, queue, event topic. Decision: queue with retries and a dead-letter queue. Consequences: delayed delivery; duplicates need an idempotent email sender; queue age to be monitored.
4. Merge them into one service: the boundary is wrong (a distributed monolith); split only along a real seam with separate data.
:::

::: summary
- Separate web and application tiers; keep the application tier stateless so it scales out.
- Monoliths are simple; modular monoliths keep options open; microservices buy independence at the price of distributed-system and operational costs.
- Draw boundaries by business capability; each service owns its data; share by API and events, tolerate duplication and staleness.
- Service discovery lets callers find healthy instances; the registry must itself be highly available.
- Migrate with the strangler pattern; record decisions in ADRs and diagrams.
:::

::: revision
- [ ] I can argue monolith versus microservices for a given team and product.
- [ ] I can define a service boundary and assign data ownership.
- [ ] I can draw service registration and lookup.
- [ ] I can describe a strangler migration and write an ADR.
:::

::: supplement
**Further reading.** Sam Newman, *Building Microservices* and *Monolith to Microservices*; Eric Evans, *Domain-Driven Design*; Simon Brown, the C4 model (c4model.com); Michael Nygard, "Documenting Architecture Decisions" (2011); Martin Fowler's articles on the strangler fig and on microservice trade-offs.
:::
