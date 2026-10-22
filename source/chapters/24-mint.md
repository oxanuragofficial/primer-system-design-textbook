%derived Notebook chapter 12.4 (personal finance aggregator: accounts linked via an Accounts API, transaction extraction as an async job, category assignment by seller, budgets and notifications, scale table)
%added idempotent ingestion, deduplication and pending-versus-posted transactions, money as integers, credential security and aggregator tokens, category rules and overrides, budget evaluation as a stream, storage layout and partitioning, failure handling and privacy
# Case Study: A Personal Finance Aggregator {#ch-mint}

::: objectives
After this chapter you can:

- scope a finance-aggregation product and estimate its write and read load;
- design an asynchronous, idempotent transaction-ingestion pipeline;
- model money, accounts, transactions, categories and budgets correctly;
- explain category assignment, budget alerts and why a read-heavy dashboard needs summaries;
- protect credentials and sensitive financial data and plan for failure.
:::

::: prereq
Chapters {ch:ch-api} (idempotency), {ch:ch-sql}, {ch:ch-async} (queues, outbox), {ch:ch-security} and {ch:ch-interview}.
:::

## Problem and requirements {#sec-mint-req}

**The problem.** Users connect their bank and card accounts. The service pulls their **transactions**, assigns each to a **spending category** (groceries, rent, travel), and shows **spending by category and month**. Users set **budgets** per category and are **notified** when they approach or exceed them.

**Functional requirements.** Link and unlink accounts. Fetch transactions periodically and when users ask. Categorise by seller (with user overrides). Show per-category monthly summaries and transaction lists. Create budgets (a default may be suggested from history) and send alerts.

**Non-functional requirements.** *Correctness of money* matters more than speed: no lost, duplicated or altered amounts. *Security and privacy*: financial data is highly sensitive. *Availability*: the dashboard should work even if a bank is down (show last known data, clearly marked). *Freshness*: a daily update is acceptable; the notebook assumes transactions are pulled **daily** for active users. *Scalability* to tens of millions of users.

**Scope.** Out of scope: moving money (payments), investments, credit scoring, and the details of each bank's interface. We treat the connection to banks as a third-party **aggregator API** that returns transaction data through tokens (we should never store raw bank passwords if a token flow exists).

## Scale estimate {#sec-mint-scale}

Table[mint-scale]: Assumptions from the notebook, with derived quantities.

| Quantity | Assumption | Derived |
|---|---|---|
| Users | 10 million | |
| Linked accounts | 5 per user | 50 million accounts |
| Transactions | 30 per account per month | 1.5 billion per month |
| Write rate | 1.5×10⁹ / 2.5×10⁶ s | ≈ 600 transaction writes per second average |
| Reads | 10 dashboard views per user per month, a few queries each | ≈ 40 reads per second average, strongly bursty |
| Record size | ≈ 200 bytes per transaction | 1.5×10⁹ × 200 B = 300 GB per month, about 3.6 TB per year |

**What the numbers say.** The workload is **write-heavy and batch-like**: ingestion is a steady stream (600 per second average, perhaps 10 times that in daily batch windows), while reads are rare per user but need to be fast. Storage grows to tens of terabytes over several years, which is beyond one SQL server comfortably, so partition by user. Peak ingestion is set by the daily refresh window: if all 50 million accounts refresh in a 4-hour window, that is 50×10⁶ / 14,400 ≈ 3,500 account fetches per second, each returning about 1 new transaction per day on average, and far more on first link.

## Architecture overview {#sec-mint-arch}

{{fig mint-arch | Mint architecture. A scheduler enqueues refresh jobs; extraction workers call the aggregator; a transaction pipeline normalises, deduplicates, categorises and stores; a budget evaluator and notifier consume the same stream; the dashboard reads summaries.}}

In {fig:mint-arch}, the **Accounts API** receives link requests and stores account metadata (never raw credentials). A **scheduler** places a refresh job per account on a queue. **Extraction workers** call the aggregator with the stored token and publish raw transactions to a stream. The **transaction pipeline** normalises amounts and dates, deduplicates, assigns categories and writes to the transaction store; the same events update **monthly summaries** and feed the **budget evaluator**, which emits notifications. The **dashboard API** reads summaries and transaction lists.

## API contracts {#sec-mint-api}

| Method and path | Purpose | Notes |
|---|---|---|
| `POST /v1/accounts/link` | start linking an institution | returns a redirect or link token; secrets stay with the aggregator |
| `DELETE /v1/accounts/{id}` | unlink and schedule data deletion | idempotent |
| `POST /v1/accounts/{id}/refresh` | request refresh now | returns `202` with a job id; rate-limited per account |
| `GET /v1/transactions?from=&to=&category=&cursor=` | list transactions | cursor pagination (Chapter {ch:ch-api}) |
| `PUT /v1/transactions/{id}/category` | override category | optional "apply to all from this seller" |
| `GET /v1/summary?month=2026-10` | totals by category | served from precomputed summaries |
| `PUT /v1/budgets/{category}` | create or update budget | amount in minor units plus currency |

Refresh returns **202 Accepted** because the work is asynchronous: the client polls the job or receives a notification, rather than holding a connection while a bank is slow.

## Data model {#sec-mint-data}

**Money is an integer.** Store amounts as integer **minor units** (cents) with an ISO currency code. Floating point cannot represent 0.10 exactly and accumulates error; decimal types are acceptable, but integers are simplest. Never sum across currencies without conversion.

Table[mint-schema]: Core tables (partitioned by `user_id`).

| Table | Key columns | Notes |
|---|---|---|
| `accounts` | `account_id PK, user_id, institution, token_ref, status, last_sync` | `token_ref` points to a secrets store, not the secret itself |
| `transactions` | `(user_id, account_id, external_txn_id) UNIQUE`, `txn_id, posted_date, amount_minor, currency, seller_raw, seller_id, category_id, state` | `state` is pending or posted; unique key gives dedupe |
| `sellers` | `seller_id, normalised_name, default_category_id` | maps messy descriptions to a canonical seller |
| `category_overrides` | `(user_id, seller_id) PK, category_id` | user's own mapping wins |
| `monthly_summary` | `(user_id, month, category_id) PK, total_minor, count` | updated incrementally |
| `budgets` | `(user_id, category_id) PK, limit_minor, currency, alert_levels` | |

**Indexes.** `transactions(user_id, posted_date DESC)` serves "recent transactions"; `(user_id, category_id, posted_date)` serves category views. Partitioning by `user_id` keeps one user's data together so dashboard queries touch one shard.

**Relational or NoSQL?** The notebook uses a SQL database for user and account data and sketches a wider choice for the transaction volume. A reasonable answer: keep accounts, budgets and overrides in a relational database (relationships, transactions, small); keep the large, append-mostly transaction history in a sharded relational store or a wide-column store keyed by user and time (Chapter {ch:ch-nosql}), with the unique external id enforced per partition.

## Ingestion, step by step {#sec-mint-flow}

{{fig mint-flow | One refresh. The scheduler enqueues a job; the worker fetches with a cursor, publishes events, and the pipeline writes transactions idempotently and updates summaries and budgets.}}

1. The scheduler enqueues `refresh(account_id)`; the job carries an idempotency key (account and date).
2. A worker reads the account's **sync cursor** (the last position returned by the aggregator) and requests new transactions after it.
3. It publishes raw transactions to the stream and **advances the cursor only after publishing succeeds**.
4. The pipeline normalises each record (amount to minor units, date to UTC date, seller name cleaned) and upserts it using the unique key `(user, account, external id)`, so redelivery causes no duplicates (at-least-once delivery plus idempotent writes, Chapter {ch:ch-async}).
5. It assigns a category (next section) and, in the **same transaction** or through an outbox, updates `monthly_summary` and emits a `transaction.created` event.
6. The budget evaluator reads the event, adds the amount to the month's running total, and notifies when thresholds (for example 80% and 100%) are crossed, once per threshold per month.

**Pending versus posted.** Banks first report *pending* transactions, whose amount or id can change when they post. Treat `state` as part of the record: update a pending entry in place when the posted version arrives (matching by external id, or by amount, merchant and date heuristics when ids change), adjusting summaries by the **difference**, never counting both.

**Corrections and reversals.** Refunds are new negative transactions; never edit history silently. If the aggregator revises a past transaction, record the change and adjust the summary by the delta.

## Categories, summaries and budgets {#sec-mint-cat}

**Category assignment.** The notebook assigns a category by **seller** using a lookup (a `Category` abstraction with a `seller_category_map`). Pipeline: clean the raw description ("AMZN MKTP US*2K4 SEATTLE" becomes "Amazon"), look up the canonical seller, apply the user override if present, else the seller default, else "Uncategorised" and queue the item for a classifier or review. Heap-based top-k lookups for "recently used categories" and "most common seller categories" are cheap with in-memory structures (Chapter {ch:ch-ds}). Override rules should apply to *future* transactions and optionally to history (a background re-categorisation job that adjusts summaries by delta).

**Summaries.** Dashboard reads must not scan millions of transactions. Maintain `monthly_summary` incrementally on write (add the amount to its row), and recompute from source periodically as a reconciliation check. Because writes arrive at-least-once, the summary update must be **idempotent**: apply it only when the transaction insert actually created or changed a row, in the same transaction.

**Budgets.** The notebook computes a default budget from spending, for example a percentage above the average of recent months. The evaluator keeps a per-user, per-category running total and compares with limits; it must handle month boundaries (by the user's time zone), refunds (totals can drop), and late-arriving transactions (dated earlier, so affect a past month).

::: worked
**Budget alert.** Groceries budget 500.00 (50,000 cents). Posted so far this month: 38,000. A new transaction of 2,500 arrives: total 40,500 = 81%, crossing the 80% threshold: send one alert and record `alerted_80 = true` for this month. Later a refund of −1,000 lowers the total to 39,500 (79%): do not re-alert when it crosses 80% again unless the product rule says so; document whichever rule you choose.
:::

## Security, privacy and compliance {#sec-mint-sec}

- **Credentials.** Prefer OAuth-style tokens from an aggregator; never store bank passwords in plain form. Keep tokens in a secrets manager or encrypted column with a key held in a KMS, with access limited to extraction workers (Chapter {ch:ch-security}).
- **Encryption** in transit (TLS) and at rest; field-level encryption for account numbers (store only the last four digits for display).
- **Least privilege and audit**: log who accessed what; support staff see masked data.
- **Data rights**: export and delete on request; deleting an account must remove transactions and derived summaries and tokens, and revoke the token at the aggregator.
- **Regional and financial regulations** apply (for example data protection and open-banking rules); mention them and defer to specialists.
- **Fraud and abuse**: rate-limit refresh and linking per user; protect against credential stuffing on the login.

## Scaling, failures and operations {#sec-mint-ops}

**Scaling.** Ingestion scales horizontally: more workers per queue partition; throttle per institution because banks rate-limit the aggregator. Spread the daily refresh over hours with **jitter** to avoid a thundering herd. Partition transactions by `user_id`. Cache summaries for the dashboard (a short TTL is fine; invalidate on write).

**Failure handling.** *Bank or aggregator down*: retry with backoff and a circuit breaker per institution; show "last updated" and a stale marker. *Expired or revoked token*: mark the account `needs_reauth` and notify the user. *Worker crash mid-job*: the queue redelivers; idempotent upserts make repeat safe. *Poison transaction* (unparseable): send to a dead-letter queue and count it. *Pipeline lag*: back pressure and autoscaling on queue age. *Summary drift*: nightly reconciliation compares summaries with sums from the transaction store and repairs differences.

**Operations.** Track sync success rate per institution, freshness (age of last sync), queue age, duplicate rate, uncategorised percentage, budget alert latency, and reconciliation mismatches. Cost is dominated by transaction storage and aggregator fees per linked account, so stop refreshing dormant users.

## Alternatives and trade-offs {#sec-mint-alt}

Table[mint-alt]: Decisions and alternatives.

| Decision | Chosen | Alternative | Reason | Revisit if |
|---|---|---|---|---|
| Ingestion | Queue plus idempotent upsert | Synchronous fetch on dashboard open | Isolation from slow banks | Interactive refresh is the main feature |
| Summaries | Incremental table plus reconciliation | Compute on read | Fast dashboard | Small data |
| Storage | Relational for core, partitioned transactions | Single NoSQL store | Integrity for accounts | Extreme volume |
| Money type | Integer minor units | Floating point | Exactness | Never use floats |
| Category source | Seller map plus overrides | ML-only | Predictable, explainable | Many unknown sellers |

**Follow-ups.** *Multiple currencies?* Store original currency and amount; convert for display with dated rates. *Shared household accounts?* Introduce a household entity and permissions. *Real-time notifications?* Use aggregator webhooks to trigger refresh. *Recurring bills detection?* A batch job over history grouping by seller and periodic gaps.

::: failure
**Failure modes (summary).** Duplicate transactions from redelivery; pending and posted both counted; summary drift; missed alert or repeated alerts; expired tokens silently stopping sync; thundering herd at refresh time; floating-point rounding errors; credential leak; deleted users' data left in summaries.
:::

::: misconception
- *"Just store the bank password."* Use token flows and a secrets store; passwords are a liability.
- *"Floats are fine for dollars."* They are not; use integers.
- *"The dashboard can sum transactions on every view."* Maintain summaries.
- *"Retries cause no harm."* Only if writes are idempotent.
:::

::: interview
**Q1. How do you avoid duplicate transactions?**
Unique key on user, account and the bank's transaction id; upsert; cursor advanced after publish; idempotent summary updates.

**Q2. How do you handle pending transactions?**
Keep state, update in place when posted, apply summary deltas.

**Q3. How do you keep the dashboard fast?**
Incrementally maintained monthly summaries, partitioning by user, short-TTL cache.

**Q4. What if the bank is down?**
Show stale data with timestamp; retry with backoff; circuit breaker per institution.
:::

::: exercise
1. With 20 million users, 4 accounts each and 25 transactions per account per month at 250 bytes, compute transactions per second (average) and yearly storage.
2. Show how a pending 40.00 charge that posts as 42.50 changes a category total of 300.00.
3. Design the idempotency of the summary update when the same event is delivered twice.
4. A user's budget alert fired twice. List three possible causes.

**Answers.**
1. 20×10⁶ × 4 × 25 = 2×10⁹ per month; ÷ 2.5×10⁶ s = 800 per second. Storage 2×10⁹ × 250 B = 500 GB/month, 6 TB/year.
2. Pending adds 4,000 cents: total 30,000 + 4,000 = 34,000. On posting, apply the delta +250 (42.50 − 40.00 = 2.50): total 34,250 cents = 342.50. It must not add 4,250 again.
3. Insert the transaction with `ON CONFLICT DO NOTHING` (or compare version); update the summary only if a row was inserted or its amount changed, in the same database transaction; store processed event ids otherwise.
4. The alert flag was not stored atomically with the total; redelivery of the same event; refund and re-crossing with no rule; evaluator replicas without partitioning by user.
:::

::: summary
- Treat ingestion as an asynchronous, idempotent pipeline: queue, cursor, upsert, delta-based summaries.
- Money is integers; pending and posted states and reversals need explicit handling.
- Summaries and partitioning by user make a read dashboard fast on a write-heavy store.
- Protect credentials with tokens, secrets management and least privilege; support deletion.
- Plan for bank outages, token expiry, drift and thundering herds.
:::

::: revision
- [ ] I can compute write rate and storage.
- [ ] I can explain idempotent ingestion.
- [ ] I can describe the schema and indexes.
- [ ] I can explain budgets and alerts without duplicates.
:::
