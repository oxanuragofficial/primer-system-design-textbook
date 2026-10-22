%derived Notebook chapters 2 and 9 (availability patterns, back pressure) and the "symptom to first fix" revision sheet
%added the whole chapter: timeouts, retry budgets and jitter, circuit breakers, bulkheads, load shedding, graceful degradation, failover design, chaos testing
# Resilience Patterns {#ch-resilience}

::: objectives
After this chapter you can:

- explain how a failure in one component spreads, and why slow is worse than down;
- set timeouts and retry policies (backoff, jitter, budgets) that heal failures instead of amplifying them;
- apply circuit breakers, bulkheads, load shedding and graceful degradation;
- design failover that has actually been exercised, and reason about blast radius.
:::

::: prereq
Chapter {ch:ch-network} (timeouts, TCP), Chapter {ch:ch-async} (retries, back pressure), Chapter {ch:ch-consensus} (uncertain outcomes).
:::

::: terms
Resilience
: The ability to keep providing acceptable service despite failures, and to recover quickly.

Cascading failure
: One component's failure causing others to fail, often via overload.

Blast radius
: How much of the system (or how many users) a single failure can affect.

Circuit breaker
: A guard that stops calling a failing dependency for a while, failing fast instead.

Bulkhead
: Isolating resources so that one failing part cannot exhaust the capacity of the others.

Load shedding
: Deliberately rejecting some requests to protect the rest.

Graceful degradation
: Offering reduced functionality instead of failing completely.
:::

## How failures spread {#sec-spread}

Components do not fail one at a time and politely. A typical outage chain: a database slows down; application threads wait on it; the thread pool fills; the web tier can no longer accept requests; the load balancer's health checks fail; healthy servers are removed; the remaining ones receive more traffic and fail faster. A *local* slowdown became a *global* outage. Three lessons:

1. **Slow is worse than down.** A dead dependency fails instantly (connection refused); a slow one ties up a thread, a connection and memory for every request until a timeout, so the failure *propagates upstream*.
2. **Retries multiply load.** If every client retries a failing call three times, a struggling service suddenly receives four times its normal traffic: a **retry storm** that stops recovery.
3. **Tail latency compounds across calls.** A request needing 100 internal calls at p99 = 1 s is slow for most users (Chapter {ch:ch-intro}).

Resilience engineering is the set of habits that stop these chains: bound every wait, limit retries, isolate resources, shed load, and degrade gracefully.

{{fig cascade | A cascading failure. A slow database makes application threads wait; the pool fills; the balancer sees failing health checks and removes servers; load on the survivors increases and the whole tier collapses.}}

## Timeouts {#sec-timeouts}

**Every network call needs a timeout.** The default in many libraries is infinite or minutes. Without a timeout, a hung dependency holds a thread forever, and the pool drains.

Choosing values: base them on measured latency of the dependency, for example a little above its p99.9, not on hope. Use separate **connect** and **read** timeouts. Propagate a **deadline** through the call chain: if the user's request has 1 s total, the first service gives its downstream at most 800 ms, which gives *its* downstream 600 ms, so no work is done after the client has already given up. Remember from Chapter {ch:ch-consensus}: a timeout means *outcome unknown*, so timeouts on non-idempotent calls require idempotency keys.

::: worked
**A deadline budget.** User request: 1,000 ms. Frontend processing: 50 ms. It calls the order service with a deadline of 900 ms. The order service spends 100 ms locally and calls inventory with 700 ms and pricing with 700 ms *in parallel* (not sequentially, which would need 1,400 ms). If inventory is slow and the call exceeds 700 ms, it is cancelled; the order service returns a degraded answer ("availability being checked") instead of waiting. Without deadlines each layer would use its own 5 s timeout and the user would wait 5 s on top of 5 s on top of 5 s.
:::

## Retries done right {#sec-retries}

Retries are the right response to **transient** failures (a dropped packet, a restarting server), and a dangerous one to **overload**. Rules:

- **Retry only safe operations**: idempotent calls or those with idempotency keys.
- **Retry only on retryable errors**: connection resets, timeouts, 503; never on 400-class errors that will fail again.
- **Exponential backoff**: wait 100 ms, 200, 400, 800, ... to give the dependency time to recover.
- **Jitter**: randomise each delay (for example, a random value between 0 and the backoff, called *full jitter*) so clients de-synchronise instead of retrying in lockstep.
- **Limit attempts** (2 to 3), and use a **retry budget**: retries may be at most, say, 10% of recent requests. When the budget is exhausted, fail fast. This caps the amplification during an outage.
- **Retry at one layer only.** If a client, the gateway and the service each retry three times, one failure becomes 27 attempts.

```python
def call_with_retry(fn, attempts=3, base=0.1, cap=2.0):
    for i in range(attempts):
        try:
            return fn(timeout=0.5)
        except RetryableError:
            if i == attempts - 1 or not retry_budget.try_acquire():
                raise
            sleep(random.uniform(0, min(cap, base * 2 ** i)))   # full jitter
```

**Hedged requests** (sending a second request after a short delay if the first is slow, taking whichever answers first) cut tail latency for idempotent reads, at the price of extra load; use them sparingly and only with a budget.

## Circuit breakers {#sec-breaker}

A **circuit breaker** wraps calls to a dependency and tracks recent failures. It has three states:

- **Closed**: calls pass through; failures are counted.
- **Open**: after too many failures (for example, 50% errors over 20 requests), calls **fail immediately** without touching the dependency, for a cool-down period. This protects both sides: the caller does not waste threads, and the struggling dependency gets breathing room to recover.
- **Half-open**: after the cool-down a few **trial** calls are allowed; if they succeed, the breaker closes; if they fail, it opens again.

{{fig breaker | The three states of a circuit breaker. Failures open it; after a cool-down a few trial requests decide whether to close it again.}}

When the breaker is open, the caller needs a **fallback**: a cached value, a default, a queued request, or a clear error. Tune thresholds to the dependency's normal error rate; too sensitive and the breaker flaps, too lax and it never helps.

## Bulkheads and isolation {#sec-bulkhead}

Ships are divided into watertight compartments so one hole does not sink the vessel. In software, a **bulkhead** gives each dependency, tenant or request class its **own** pool of threads, connections or capacity. If the recommendation service hangs and has its own 10-thread pool, it can exhaust only those 10 threads; checkout, with its own pool, keeps working. Without it, a shared pool is drained by the slowest dependency. Bulkheads also appear as **separate deployments** for critical and non-critical traffic, **per-tenant quotas**, **separate queues**, and **cell-based architecture**, in which the whole system is replicated into independent *cells*, each serving a subset of users, so a bad deployment or a poisoned request affects one cell's users only. That limits the **blast radius**.

## Load shedding and graceful degradation {#sec-shed}

When demand exceeds capacity, doing everything slowly means *everyone* times out. Doing *less*, quickly, keeps the system healthy.

- **Load shedding**: reject excess requests early and cheaply (HTTP 503 with `Retry-After`), preferably the **least important first** (analytics before checkout, anonymous before logged-in), and based on a cheap signal such as concurrency or queue age. Shed at the edge, before the work is started. Connection limits and the rate limiters of Chapter {ch:ch-entry} are forms of shedding.
- **Graceful degradation**: provide reduced but useful function. If personalised recommendations are down, show popular items; if the search ranking service is slow, return unranked results; serve slightly stale cached data; disable expensive features (autocomplete) under load. Decide in advance, per feature, **what is critical** and **what can degrade**, and make that a feature flag operators can flip.
- **Fail open versus fail closed**: if the authorisation service is unreachable, deny access (fail closed, safe for security); if the recommendation service is unreachable, show something anyway (fail open, safe for experience). Make the choice deliberately for each dependency.

## Designing failover {#sec-failoverdesign}

Redundancy is worthless unless the switch-over **works**. Principles:

- **Eliminate single points of failure** at every layer: balancers, application servers, caches, databases, DNS, power, network, and *humans* (the one engineer who knows how).
- **Spread across failure domains**: servers in several racks, **availability zones** (separate data centres within a region), and, for the highest requirements, **regions**. Size capacity so that after losing one zone the rest can carry the load (N+1 or "N+ a zone"): three zones, each at ≤ 66% utilisation, can lose one.
- **Automate detection and promotion**, but protect against false triggers and split brain (Chapter {ch:ch-consensus}).
- **Practise.** Untested failover fails. Run game days, kill instances in production under controlled conditions (**chaos engineering**: inject faults deliberately and observe), and rehearse regional evacuation. Time every recovery to know your real RTO.
- **Make recovery safe**: when a failed component returns, avoid *thundering herds* (ramp traffic up gradually; use slow start at balancers) and re-synchronise data before it serves.

Table[resilience]: Patterns and what each defends against.

| Pattern | Defends against | Cost or risk |
|---|---|---|
| Timeout and deadline | Hung dependencies, wasted work | Wrong values cause false failures |
| Retry with backoff, jitter and budget | Transient errors | Amplifies overload if unbounded |
| Circuit breaker | Persistent dependency failure | Needs fallbacks; tuning |
| Bulkhead | Resource exhaustion spreading | Lower utilisation (partitioned pools) |
| Load shedding | Overload | Some users are refused |
| Graceful degradation | Partial outages | Must be designed and tested per feature |
| Redundancy across zones | Hardware and zone failure | Cost; replication complexity |
| Chaos testing | Untested assumptions | Needs maturity and safeguards |

::: failure
**Failure modes of the resilience mechanisms themselves.** Timeouts shorter than normal latency causing self-inflicted errors; retries synchronised into storms; a circuit breaker that stays open forever or flaps; fallbacks that are untested and fail when first used; bulkheads sized too small, throttling normal traffic; health checks that remove all servers at once; failover that promotes a stale replica; "metastable" failures, in which a trigger (a brief overload) leaves the system in a bad state (queues full, caches cold, retries high) that persists *after* the trigger is gone, requiring shedding or a restart to recover.
:::

::: warning
**Common mistakes.** No timeouts. Retrying on every error, at every layer, with no jitter. Treating redundancy as availability without testing failover. Hiding failures: a fallback that silently returns wrong data. Health checks that depend on a shared dependency.
:::

::: misconception
- *"If we retry, we are more reliable."* Not when the failure is overload; unlimited retries destroy recovery.
- *"We have three replicas, so we are safe."* Only if failures are independent and failover is exercised.
- *"A circuit breaker fixes the failing service."* It protects callers and gives time; the service still needs repair.
- *"Graceful degradation is a nice-to-have."* For large systems it is the difference between a blip and an outage.
:::

::: interview
**Q1. A dependency becomes slow. What happens to your service and how do you protect it?**
Threads and connections pile up waiting; the pool drains and failure cascades upstream. Use timeouts and deadlines, a circuit breaker with a fallback, a bulkhead so other features keep their own pools, and load shedding.

**Q2. How should retries be configured?**
Only for idempotent or keyed operations and retryable errors; exponential backoff with jitter; two or three attempts with a retry budget; retry at a single layer; stop when the circuit is open.

**Q3. What is a circuit breaker?**
A state machine (closed, open, half-open) that fails fast after repeated errors to protect the caller and give the dependency time to recover, probing periodically.

**Q4. What is graceful degradation? Give an example.**
Serving reduced functionality instead of failing: if the recommendation service is down, show popular items from a cache.
:::

::: exercise
1. A service calls three dependencies sequentially, each with p99 = 400 ms and a 2 s timeout. What are the worst-case and typical-bad latencies, and how would you improve it?
2. A client library retries 3 times, the gateway retries 3 times, and the service retries 3 times against its database. How many database attempts can one user action cause?
3. Design a bulkhead scheme for a web app that calls payments (critical), recommendations (nice to have) and analytics (can be dropped).
4. Three zones each run at 60% utilisation. After losing one zone, what utilisation do the others face?

**Answers.**
1. Worst case ≈ 3 × 2 s = 6 s; typical bad ≈ 1.2 s. Improve: call them in parallel (about the slowest, not the sum), tighter timeouts near p99.9, a deadline for the whole request, fallbacks for the optional ones.
2. 3 × 3 × 3 = 27 attempts. Retry at a single layer.
3. Separate thread or connection pools: payments gets a protected pool and highest priority; recommendations a small pool with a short timeout and fallback to popular items; analytics a tiny pool or an asynchronous queue where events can be dropped under load.
4. Total load = 3 × 60% = 180% of one zone's capacity; spread over two zones that is 90% each, which leaves almost no headroom. Planning for about 50% per zone gives 150% / 2 = 75% after losing a zone.
:::

::: summary
- Failures cascade through waiting and retries; slow is worse than down.
- Timeouts with deadlines everywhere; retries only for safe, retryable errors, with backoff, jitter, a small budget and a single retrying layer.
- Circuit breakers fail fast; bulkheads isolate resources; load shedding and graceful degradation keep the core working.
- Redundancy needs independent failure domains, spare capacity, automation and regular practice.
:::

::: revision
- [ ] I can draw a cascade and say where each defence cuts it.
- [ ] I can write a retry loop with jitter and a budget.
- [ ] I can describe the three breaker states.
- [ ] I can decide fail-open versus fail-closed for a dependency.
:::

::: supplement
**Further reading.** Michael Nygard, *Release It!* (circuit breakers, bulkheads); Google's *Site Reliability Engineering* chapters on cascading failures and handling overload; Marc Brooker, "Timeouts, retries, and backoff with jitter" (AWS Builders' Library); Bronson et al., "Metastable Failures in Distributed Systems" (2021).
:::
