%derived Notebook chapter 2 (availability in numbers) and chapter 9 (performance bottleneck hunting) and the "symptom to first fix" revision sheet
%added logs, metrics, traces, alerting, SLIs, SLOs, SLAs and error budgets, incident response, postmortems, RPO and RTO, backup restoration drills and disaster-recovery strategies
# Observability and Reliability Engineering {#ch-observability}

::: objectives
After this chapter you can:

- explain the three pillars (logs, metrics, traces) and what each is best for;
- choose useful metrics (RED, USE, the golden signals) and avoid high-cardinality traps;
- define SLIs, SLOs and SLAs, and compute an error budget;
- design alerts that page for user-visible symptoms and link to runbooks;
- run an incident and write a blameless postmortem;
- define RPO and RTO and choose a disaster-recovery strategy.
:::

::: prereq
Chapters {ch:ch-estimation} (availability arithmetic), {ch:ch-resilience} and {ch:ch-microservices}.
:::

::: terms
Observability
: The ability to understand a system's internal state from the data it emits (logs, metrics, traces) without shipping new code.

SLI (service level indicator)
: A measured quantity describing service quality, such as the fraction of requests answered successfully within 300 ms.

SLO (service level objective)
: A target for an SLI over a period, for example 99.9% over 30 days.

SLA (service level agreement)
: A contract with consequences (credits, penalties) if a promised level is missed.

Error budget
: The allowed amount of unreliability: 100% minus the SLO.

RPO / RTO
: Recovery point objective (how much data loss is tolerable, measured in time) and recovery time objective (how long recovery may take).
:::

## Seeing inside a running system {#sec-seeing}

With one server, you can log in and look. With a hundred containers across zones, calling dozens of services, you cannot. You must design the system to **emit** the evidence you will need during an outage you cannot yet predict. **Monitoring** answers known questions ("is CPU above 90%?"); **observability** lets you ask *new* questions ("why are requests from this region slow only for premium users?") by slicing rich data after the fact. Three kinds of telemetry cooperate.

Table[pillars]: The three pillars.

| Pillar | What it is | Best for | Cost and limits |
|---|---|---|---|
| Logs | Timestamped records of discrete events | Details of one event, errors, audits | Volume; expensive to store and search |
| Metrics | Numbers aggregated over time | Trends, dashboards, alerting, capacity | Lose per-request detail; cardinality limits |
| Traces | The path and timing of one request across services | Finding where latency or errors arise | Needs instrumentation; sampling loses some requests |

## Logs {#sec-logs}

Write **structured logs** (JSON key-value pairs), not free text: `{"ts":"...","level":"error","service":"orders","order_id":981,"msg":"payment timeout","trace_id":"ab12"}`. Machines can then filter and aggregate. Practices:

- Use **levels** (debug, info, warn, error) and set production to info or warn.
- Include a **correlation (request or trace) id** in every line and propagate it through every service call, so you can gather everything one request did.
- Log **events and decisions**, not secrets or personal data (Chapter {ch:ch-security}).
- Ship logs off the machine to central storage (a crashing machine takes its local logs with it); control volume (sampling, retention) because logs are often the biggest observability cost.
- Do not rely on logs for counting; count with metrics.

## Metrics {#sec-metrics}

Metric types: a **counter** only increases (requests served, errors; you chart its *rate*); a **gauge** goes up and down (queue depth, memory in use); a **histogram** records the distribution of values (request latency) so you can compute percentiles (Chapter {ch:ch-intro}). Never alert on average latency; use p95 or p99.

What to measure? Do not invent from scratch; use proven checklists.

- **RED** (for request-driven services): **R**ate (requests per second), **E**rrors (failed fraction), **D**uration (latency distribution).
- **USE** (for resources such as CPU, disk, network, connection pools): **U**tilisation (busy fraction), **S**aturation (queued or waiting work), **E**rrors.
- Google's **four golden signals**: latency, traffic, errors, saturation.

Add **business metrics** (signups, orders, payments succeeded) because an outage that technical metrics miss still shows up there. Keep metric **cardinality** under control: each distinct combination of label values is a separate time series; labelling by `user_id` or `url` with unlimited values creates millions of series and breaks the monitoring system. Use bounded labels (service, endpoint pattern, status class) and put high-cardinality detail in logs and traces.

## Traces {#sec-traces}

A **distributed trace** follows one request through many services. Each unit of work is a **span** with a start, duration, and a parent; the whole tree shares a **trace id** passed along in request headers (**context propagation**, standardised by W3C Trace Context and implemented by OpenTelemetry). The waterfall view shows exactly where time goes and which call failed.

{{fig trace | A trace waterfall for one request. The total of 480 ms is dominated by one slow inventory query inside the order service; no single service's metrics would show that so clearly.}}

Tracing every request is costly, so systems **sample**: keep a fixed fraction (say 1%), plus **all errors and slow requests** (tail-based sampling). Instrument at framework level (HTTP servers and clients, database drivers) so most spans appear automatically.

## Alerting {#sec-alerts}

An alert should mean *"a human must act now"*. Too many alerts cause **alert fatigue**: people stop reacting, and the one real page is ignored. Principles:

- **Alert on symptoms users feel** (error rate, latency, availability against the SLO), not on every cause (CPU 85%). Use cause-based signals for *dashboards and tickets*.
- **Page only for urgent, actionable** conditions; send the rest to a ticket queue or a chat channel.
- Use **burn-rate alerts** (below): they fire when the error budget is being consumed too fast, which is both sensitive and robust against noise.
- Every alert links to a **runbook**: what it means, how to confirm, likely causes, first mitigations, who to escalate to.
- Review alerts regularly: delete the noisy, add missing ones after incidents.

## SLIs, SLOs, SLAs and error budgets {#sec-slo}

Engineering reliability means deciding *how reliable is reliable enough*, because 100% is impossible and absurdly expensive.

- Choose **SLIs** that match user experience: *availability* (successful requests / valid requests), *latency* (fraction of requests faster than 300 ms), *freshness*, *correctness*, *durability*.
- Set an **SLO** for each: for example "99.9% of requests succeed, measured over a rolling 30 days".
- The **error budget** is the unreliability you may spend: 0.1% of requests (or about 43.8 minutes in 30 days). As long as budget remains, ship features and take risks; when it is exhausted, freeze risky changes and invest in reliability. This turns the argument between "move fast" and "be stable" into arithmetic.
- An **SLA** is a *contract* (with refunds) and is deliberately **looser** than the internal SLO, so you notice and fix problems before you owe money.

::: worked
**Error budget and burn rate.** SLO: 99.9% success over 30 days. A service handles 100 requests per second on average, so about 259 million requests in 30 days; the budget is 0.1% of them, about 259,000 failed requests. Today an incident causes 5% errors for 20 minutes: failed = 0.05 × 100 × 1,200 = 6,000 requests, so about 2.3% of the monthly budget is gone. The *burn rate* is how fast the budget is being spent relative to plan: 5% errors against an allowed 0.1% is a burn rate of 50, meaning the entire month's budget would vanish in 30 days / 50 = 14.4 hours. A common policy pages when the burn rate exceeds about 14 over one hour (the budget would be consumed in about two days), and raises a ticket for slow burns (rate 1 to 3 over days). This ties alerts directly to what users and the business care about.
:::

## Incident response {#sec-incident}

Incidents are inevitable; chaos during them is not.

1. **Detect and declare.** An alert or a report; declare an incident early, with a severity level (Sev1: major outage).
2. **Assign roles.** An **incident commander** coordinates (does not debug); **operations** investigates and changes things; a **communications lead** updates stakeholders and status pages; a **scribe** keeps the timeline. One voice, clear ownership.
3. **Mitigate first, diagnose later.** The goal is to stop user pain: roll back the last change, shift traffic, disable a feature flag, add capacity, shed load. Root causes can wait until the system is stable.
4. **Communicate** regularly, honestly, in plain language.
5. **Resolve and hand over**, then confirm recovery with the SLIs.
6. **Learn** with a postmortem.

A **blameless postmortem** examines how the system and process allowed the failure, not who erred (people act reasonably on what they know; fix the conditions). Include a timeline, impact (users, duration, budget spent), root causes and contributing factors, what went well, what went badly, where luck helped, and **owned, dated action items** (detection, mitigation, prevention). Share it widely. The best postmortems change systems, not just documents.

::: warning
**Common mistakes.** Alerting on causes instead of symptoms. Unbounded metric labels. No correlation ids. Debugging before mitigating. Postmortems that name a culprit and list no actions. SLOs set to 100%, or set and never reviewed. Dashboards nobody looks at because they do not answer "are users happy?".
:::

## Disaster recovery: RPO, RTO and strategies {#sec-dr}

Some failures take out more than a node: a region outage, ransomware, a destructive migration, an operator deleting production. **Disaster recovery (DR)** plans for them with two targets (introduced in Chapter {ch:ch-scaling-sql}):

- **RPO**: the maximum tolerable *data loss* measured in time ("we can lose at most 5 minutes of data").
- **RTO**: the maximum tolerable *downtime* ("we must be back within 1 hour").

The tighter the targets, the more it costs. Typical strategies:

Table[dr]: Disaster-recovery strategies, from cheapest to most expensive.

| Strategy | What runs in the second site | Typical RTO | Typical RPO | Cost |
|---|---|---|---|---|
| Backup and restore | Nothing; backups stored elsewhere | Hours to a day | Hours (since last backup; minutes with log archiving) | Lowest |
| Pilot light | Core data replicated; compute switched off | Tens of minutes to hours | Minutes | Low |
| Warm standby | A scaled-down full copy, running | Minutes | Seconds to minutes | Medium |
| Active-active multi-region | Full capacity in several regions | Seconds to none | Near zero (with conflict handling) | Highest |

Whatever the strategy: **backups are not real until restored.** Schedule **restore drills**: restore a recent backup into an isolated environment, run integrity checks, measure the time, and record the result against the RTO. Test **point-in-time recovery**, test restoring in the DR region, and keep backups in a separate account with deletion protection to survive ransomware or a compromised administrator. Document the **runbook**, practise it (game days), and update it when the architecture changes.

::: failure
**Failure modes.** Monitoring that fails together with the system it monitors (host it separately); alert floods hiding the real signal; metrics outage during the incident; logs lost when nodes die; sampling that drops the one bad request; dashboards lagging by minutes; an untested DR plan that fails in practice (missing credentials, missing capacity quota in the DR region, an undocumented dependency); a runbook stale after a re-architecture; observability costs growing faster than the business.
:::

::: misconception
- *"More dashboards and alerts mean more reliability."* Focused symptoms and clear runbooks do.
- *"Monitoring and observability are the same."* Monitoring checks known failure modes; observability helps explore unknown ones.
- *"We have backups, so we can recover."* Only restores you have rehearsed count.
- *"A 99.99% SLO is always better than 99.9%."* It costs vastly more and may not match what users need; each extra nine reduces your budget tenfold.
:::

::: interview
**Q1. How would you monitor a web service?**
RED metrics per service and endpoint, USE for resources, business metrics, structured logs with correlation ids, distributed traces, and symptom-based alerts tied to SLOs with runbooks.

**Q2. Define SLI, SLO and SLA, and error budget.**
SLI: measured quality. SLO: internal target for an SLI. SLA: contractual promise with penalties, looser than the SLO. Error budget: 100% minus SLO, the allowed unreliability that governs risk-taking.

**Q3. What do you do in the first minutes of a major incident?**
Declare it, assign roles, mitigate (roll back, shift traffic, disable features) before diagnosing, communicate, and record a timeline.

**Q4. Explain RPO and RTO and how they influence design.**
RPO is tolerable data loss, RTO tolerable downtime. Tight RPO needs synchronous or very frequent replication; tight RTO needs warm or active standby and automated failover; both raise cost.
:::

::: exercise
1. An API has an SLO of 99.95% over 30 days. How many minutes of total outage does that allow? If it sees 10 minutes of complete outage in a week, how much budget remains (assume 30-day budget, only this incident)?
2. Design a metric set (RED plus two business metrics) for the paste service.
3. A page fires at 3 a.m. because CPU is 91% on one server, and by morning users were not affected. How would you fix the alert?
4. Choose a DR strategy and RPO/RTO for (a) an internal wiki, (b) a payments system.

**Answers.**
1. 0.05% of 43,200 minutes = 21.6 minutes. After 10 minutes of full outage: 11.6 minutes remain (about 54%).
2. Rate: `pastes_created_total`, `paste_views_total`; Errors: share of 5xx responses by endpoint class; Duration: histogram of read and create latency; business: pastes created per minute, share of views served from cache (and expired pastes accessed).
3. Remove the cause-based page; alert on a user-visible symptom (error rate or p99 latency burning the SLO budget). Keep CPU as a dashboard metric and a ticket-level alert if sustained for hours.
4. (a) Backup and restore: RPO about 24 h, RTO about a day. (b) Warm standby or active-active across zones and regions: RPO near zero via synchronous replication within a region and fast asynchronous across regions; RTO minutes, automated failover, regularly drilled.
:::

::: summary
- Emit logs (structured, correlated), metrics (RED, USE, golden signals; watch cardinality) and traces (spans with propagated context).
- Alert on user-visible symptoms and burn rates, with runbooks.
- SLOs target reliability that users need; error budgets govern speed versus stability; SLAs are looser contracts.
- Run incidents with roles, mitigate first, learn through blameless postmortems with owned actions.
- RPO and RTO drive DR strategy and cost; backups count only when restored; rehearse.
:::

::: revision
- [ ] I can state RED, USE and the golden signals.
- [ ] I can compute an error budget and a burn rate.
- [ ] I can list incident roles and the first steps.
- [ ] I can match a DR strategy to RPO and RTO.
:::

::: supplement
**Further reading.** Google, *Site Reliability Engineering* and *The Site Reliability Workbook* (SLOs, alerting on burn rate, postmortems); Charity Majors et al., *Observability Engineering*; the OpenTelemetry documentation; Brendan Gregg on the USE method; Tom Wilkie on the RED method.
:::
