%added Two end-to-end design exercises that are not in the notebook, built to combine the book's patterns: a payment service (idempotency, state machine, ledger, reconciliation) and a notification system (fan-out, preferences, rate limiting, retries, provider failover)
# End-to-End Exercises: Payments and Notifications {#ch-e2e}

::: supplement
**This whole chapter is supplemental.** The notebook has no payments or notification case study. They are included because together they exercise nearly every pattern in the book: idempotency, state machines, queues, outbox, retries, rate limiting and reconciliation. Work each one yourself using the method of Chapter {ch:ch-interview} before reading the discussion.
:::

::: objectives
After this chapter you can:

- design a payment flow that never charges twice and survives timeouts and crashes;
- model money movement with a double-entry ledger and reconcile with an external provider;
- design a multi-channel notification system with preferences, rate limits and provider failover;
- apply outbox, retries, dead-letter queues and idempotency in realistic combination.
:::

::: prereq
Chapters {ch:ch-api} (idempotency keys), {ch:ch-sql} (transactions), {ch:ch-async} (outbox, sagas, DLQ), {ch:ch-resilience} and {ch:ch-security}.
:::

## Exercise 1: A payment service {#sec-e2e-pay}

**Requirements.** A merchant's checkout calls our service to **charge a card** through an external payment provider. Customers must never be charged twice and never charged without the merchant learning of it. **Scope:** card payments through one provider, refunds, webhooks; out of scope: storing raw card numbers (use the provider's tokens to stay out of the heaviest compliance scope), fraud scoring, currency conversion.

**Estimate (assumptions).** 20 million payments per month ≈ 8 per second average, peak 10 times that (80 per second). Each payment creates about 5 ledger rows and 6 events: about 40 rows and 50 events per second at peak. Tiny by throughput; the difficulty is **correctness**.

### The core problem: timeouts leave the outcome unknown

If we call the provider and the connection times out, the charge may have succeeded or not (Chapter {ch:ch-resilience}). Blind retry risks a double charge; giving up risks a lost sale. The solution is **idempotency end to end** plus a **state machine** that records intent *before* acting.

{{fig pay-flow | One payment. The intent is stored first; the provider call carries the same idempotency key; an unknown outcome is resolved by querying or by a webhook.}}

Table[pay-state]: Payment state machine.

| State | Meaning | Allowed next states |
|---|---|---|
| CREATED | Intent stored, nothing sent | PROCESSING, CANCELLED |
| PROCESSING | Request sent to provider, outcome not yet known | SUCCEEDED, FAILED, UNKNOWN |
| UNKNOWN | Timeout or ambiguous response | SUCCEEDED, FAILED (after lookup or webhook) |
| SUCCEEDED | Provider confirmed capture | REFUND_PENDING |
| FAILED | Provider declined or error confirmed | none (a new attempt is a new payment or a retry with the same key) |
| REFUND_PENDING | Refund requested | REFUNDED, SUCCEEDED (refund failed) |

### Step by step

1. The client sends `POST /v1/payments` with an `Idempotency-Key`, amount in minor units, currency and a payment-method token. The service looks up the key: if found with the same body, return the stored result; with a different body, return `409`.
2. In **one database transaction**, insert the payment as CREATED with the key (unique constraint) and an **outbox** row "charge requested".
3. A worker reads the outbox, moves the payment to PROCESSING and calls the provider **passing our payment id as the provider's idempotency key**, so a retry cannot create a second charge.
4. On a clear success or decline, write SUCCEEDED or FAILED and a ledger entry in one transaction; emit `payment.succeeded` through the outbox for the merchant's webhook.
5. On timeout, mark UNKNOWN and schedule a **lookup** by payment id with backoff; also accept the provider's **webhook**, verifying its signature. Webhooks may arrive twice or out of order: apply them only if they move the state forward, idempotently.
6. A nightly **reconciliation** job compares our ledger with the provider's settlement file; mismatches go to a human queue.

### Data model

`payments(id PK, merchant_id, idempotency_key UNIQUE per merchant, amount_minor, currency, state, provider_ref, created_at, updated_at)`; `ledger_entries(id, payment_id, account, debit_minor, credit_minor, created_at)` (append-only, double entry: every movement debits one account and credits another, so the entries always sum to zero); `outbox(id, topic, payload, published_at)`; `webhook_deliveries(id, merchant_id, event_id, attempts, next_attempt_at, status)`.

**Why a ledger?** Balances are *derived* from immutable entries, so history is auditable and errors are corrected by new entries (a reversal), never by editing rows.

### Consistency, failure and security

- **Within our database** use ACID transactions (Chapter {ch:ch-sql}). **Across the provider and us** there is no transaction: this is a **saga** (Chapter {ch:ch-async}): the steps are charge, record, notify, with compensation (refund or void) when a later step cannot complete.
- **Merchant webhooks** use at-least-once delivery with retries (exponential backoff, dead-letter after N tries), signed payloads and event ids so merchants de-duplicate.
- **Security:** never log card data; only tokens cross our boundary; TLS everywhere; secrets in a vault; per-merchant API keys with scopes; audit logs; rate limits against card-testing attacks.
- **Failure matrix:** crash after step 2 (the outbox row exists, so a worker resumes); crash after the provider call but before recording (the lookup by payment id resolves it); duplicate client request (the idempotency key returns the stored result); provider down (circuit breaker, queue payments as PENDING, tell the merchant honestly); clock skew (rely on state, not timestamps).

::: worked
**Timeout walk-through.** t0: payment P1 CREATED. t1: worker calls provider with key `P1`; the connection drops at 10 s. t2: state UNKNOWN. t3: lookup for `P1` at the provider returns "captured": state SUCCEEDED, ledger entries written (debit customer funds in transit, credit merchant payable), `payment.succeeded` emitted. If the lookup had returned "not found", it is safe to retry the charge **with the same key** because a charge for `P1` does not exist. At no point could two charges exist.
:::

## Exercise 2: A notification system {#sec-e2e-notify}

**Requirements.** Other services request notifications (order shipped, password reset, marketing) to users over **push, SMS and email**. Respect **user preferences** (channels, quiet hours, opt-outs), **rate limits**, and deliver **important messages reliably** and **promotional ones best-effort**. **Scope:** templating and delivery; out of scope: building the email or SMS carriers, analytics UI.

**Estimate (assumptions).** 50 million users, 5 notifications per user per day: 2.5×10⁸ per day ≈ 2,900 per second average. A marketing blast to 10 million users in 10 minutes needs 10⁷ / 600 s ≈ 16,700 per second at peak. Providers rate-limit us, so the **queue** absorbs the burst.

{{fig notify-arch | Notification pipeline. Requests are validated, checked against preferences and limits, rendered, and placed on per-channel priority queues; channel workers call providers with failover; delivery receipts flow back.}}

### Design

- **API:** `POST /v1/notifications` with `type`, `user_id` (or a segment), `template_id`, parameters, `priority` and an **idempotency key**. Return `202` with an id.
- **Pipeline:** validate; **resolve recipients** (a segment expands into a stream of user ids by a batch job, never inside the request); **filter** by preferences, opt-outs, quiet hours (in the user's time zone) and frequency caps; **render** a localised template; **enqueue** on the right channel queue.
- **Priority lanes:** separate queues (or priorities) for transactional (password reset: seconds) and bulk marketing, so a blast never delays a reset code. Reserve worker capacity for the high lane.
- **Channel workers** call providers with timeouts and retries; use **two providers per channel** with a circuit breaker and automatic failover. Devices tokens that a push provider reports invalid are removed.
- **Delivery tracking:** a `notifications` table with state (QUEUED, SENT, DELIVERED, FAILED, SUPPRESSED) updated by provider callbacks; keep events in a log for analytics.
- **De-duplication:** the idempotency key plus a unique `(user, template, dedupe_key)` constraint prevents sending the same alert twice when upstream retries; accept that **at-least-once** delivery can still repeat a message after a worker crash, and make messages safe to see twice.
- **Rate limits:** per user (no more than N marketing messages a day), per provider (token bucket matching the contract) and per tenant, as in Chapter {ch:ch-entry}.
- **Scheduling:** delayed and recurring notifications use a scheduler table keyed by send time, scanned by workers or a delay queue.

Table[notify-alt]: Design choices.

| Decision | Chosen | Alternative | Why |
|---|---|---|---|
| Fan-out | Batch expansion of segments to a queue | Expand inside the API call | Large audiences would time out |
| Queues | Per channel and priority | One shared queue | Isolation of urgent traffic |
| Delivery semantics | At-least-once plus de-dup keys | Exactly-once claims | Not achievable end to end |
| Providers | Two per channel with failover | Single provider | Provider outages are common |
| Preferences | Checked at send time | Checked at request time | Users change settings after requests queue |

**Failure modes.** Provider outage (failover, backlog drains later; expire stale messages such as a "your code is 123456" after minutes); retry storm to a struggling provider (backoff with jitter, circuit breaker); duplicate sends after redelivery; time-zone bugs sending marketing at 3 a.m.; spam complaints (honour opt-outs instantly; keep a suppression list); privacy (do not put sensitive details in push or SMS text).

::: worked
**Blast sizing.** 10 million emails; provider allows 3,000 per second per account and we have two accounts: 6,000 per second, so the blast takes 10⁷ / 6,000 ≈ 1,667 s ≈ 28 minutes, not 10. To meet a 10-minute target either add provider capacity (about 17,000 per second) or tell the sender the real duration. Meanwhile the transactional lane stays unaffected because it has reserved workers and its own provider quota.
:::

::: failure
**Failure modes (summary).** Payments: double charge on retry, lost outcome after timeout, webhook replay, ledger imbalance, provider mismatch. Notifications: blast starving urgent messages, duplicate sends, stale OTPs, provider outage, preference races.
:::

::: misconception
- *"A timeout means the payment failed."* The outcome is unknown until resolved.
- *"Exactly-once delivery makes retries safe."* Idempotency keys make effects safe.
- *"One queue is simpler and fine."* A single queue lets bulk traffic delay critical messages.
- *"Webhooks arrive once and in order."* Treat them as duplicated and reordered.
:::

::: interview
**Q1. How do you prevent a double charge?** Idempotency key at our API, the same key to the provider, a unique constraint, and a state machine that resolves unknown outcomes by lookup.

**Q2. Why a double-entry ledger?** Immutable, balanced entries give an audit trail; corrections are reversals.

**Q3. How do you keep urgent notifications fast during a blast?** Separate priority lanes with reserved capacity and provider quota.

**Q4. How do you handle a provider outage?** Circuit breaker, failover provider, backoff, expiry of stale messages, dead-letter queue.
:::

::: exercise
1. Payments: 25 million per month, peak factor 12. Compute average and peak payments per second and ledger rows per second at 5 rows each.
2. Draw the sequence when the provider's webhook arrives *before* our worker records the response.
3. Notifications: 40 million users, 6 per day, 15% of messages sent in a one-hour evening peak. Compute the peak per second.
4. Propose a unique constraint that stops duplicate "order shipped" emails for the same order.

**Answers.**
1. 2.5×10⁷ / 2.592×10⁶ ≈ 9.6 per second average; peak ≈ 116 per second; ledger rows ≈ 580 per second at peak.
2. Webhook handler loads the payment (PROCESSING), applies SUCCEEDED idempotently and writes the ledger; the worker then finds the state already SUCCEEDED and skips (state only moves forward). Both orders end in the same state.
3. 40×10⁶ × 6 = 2.4×10⁸ per day; 15% = 3.6×10⁷ in 3,600 s = 10,000 per second.
4. `UNIQUE(user_id, template_id, dedupe_key)` where the dedupe key is the order id; an insert conflict means "already sent or queued".
:::

::: summary
- Payments are an idempotency and state-machine problem; record intent first, pass keys end to end, resolve unknowns, reconcile.
- A double-entry ledger gives an auditable, balanced record.
- Notification systems separate priority lanes, filter by preferences, rate-limit and fail over across providers.
- Both rely on at-least-once delivery made safe by idempotency, not on exactly-once promises.
:::

::: revision
- [ ] I can draw the payment state machine and timeout recovery.
- [ ] I can explain the outbox and ledger roles.
- [ ] I can size a notification blast and design priority lanes.
:::
