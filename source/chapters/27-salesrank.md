%derived Notebook chapter 12.7 (sales rank by category: Sales API, Analytics, Transaction logs, MapReduce jobs, results in an SQL analytics database, scale table, read cache)
%added streaming aggregation as an alternative to batch, exactly-once effects through idempotent aggregation, time windows and late data, approximate top-k with heavy hitters, ranking ties and consistency, backfills and reconciliation
# Case Study: Sales Rank by Category {#ch-salesrank}

::: objectives
After this chapter you can:

- scope a "best sellers by category" feature and estimate its volume;
- design a batch pipeline (log, MapReduce, results store) and a streaming alternative;
- handle windows, late events, duplicates and ties correctly;
- serve ranks with a read cache and decide how fresh they must be;
- discuss approximate top-k and reconciliation.
:::

::: prereq
Chapters {ch:ch-estimation}, {ch:ch-async}, {ch:ch-cache}, {ch:ch-sql} and {ch:ch-ds} (heaps).
:::

## Problem and requirements {#sec-sr-req}

**The problem.** An e-commerce site wants to show the **top products by sales in each category** over the past week, such as "Best Sellers in Books", and to let the product page show a **rank** like "#12 in Kitchen".

**Functional requirements.** Compute, for each category, the products ordered by units sold (or revenue) in the last 7 days. Show the top N per category and a product's rank. Update periodically.

**Non-functional requirements.** The read path is very read-heavy and must be fast. The numbers need not be real time: **hourly** refresh is fine for the notebook design. Counts must be accurate enough that the ranking is trustworthy (no double counting). The system must tolerate worker failures and be reprocessable.

**Scope.** Rankings are by category and by one time window; sub-categories can be handled by rolling up. Out of scope: personalised rankings, fraud detection in sales and inventory.

## Scale estimate {#sec-sr-scale}

Table[sr-scale]: Assumptions and derived quantities from the notebook's style of estimate.

| Quantity | Assumption | Derived |
|---|---|---|
| Transactions | 10 billion per month | ≈ 4,000 per second on average |
| Log record | ≈ 70 bytes (timestamp, product id, category id, seller, quantity, price) | 10¹⁰ × 70 B = 700 GB per month |
| Retention | Raw logs one year | ≈ 8.4 TB, compressed far less |
| Products | 50 million | |
| Rank reads | 40,000 per second (page views) | cached |
| Results table | (category, week, product, units) per hour | small compared with the log |

**What the numbers say.** The write rate (4,000 per second) is easy for a log. The expensive part is the **aggregation over 700 GB per month**; weekly windows touch about 160 GB each time. That is a good fit for a distributed batch job, and the output (top lists per category) is tiny, which suits caching. The mismatch between huge input and tiny output is the key insight of this chapter.

## Architecture overview {#sec-sr-arch}

{{fig sr-arch | Batch sales-rank pipeline. Sales events are appended to a durable log; MapReduce-style jobs aggregate and rank; results go to an analytics store; a cache serves reads.}}

The notebook's design: the **Sales API** records each sale in **transaction logs** (an object store or distributed log); **Analytics** jobs (MapReduce) read the logs, count units per product per category, sort, and write results to a **SQL analytics database** (the notebook notes that such a table might otherwise grow large, so prune old windows); the **Sales Rank service** reads results through a cache and serves product pages and category pages.

## Batch computation step by step {#sec-sr-batch}

The notebook describes the MapReduce job in two steps (and a third for sorting):

1. **Map**: for each log line emit `((category, product_id), quantity)`.
2. **Reduce**: sum values by key, giving units per product per category for the window: `(category, product_id) -> total_units`.
3. **Sort/rank**: a second job (or a secondary sort) orders products within each category by total units and emits `(category, rank, product_id, units)`. 

```
# job 1
def map(line):               # line: ts, product, category, qty
    emit((line.category, line.product), line.qty)
def reduce(key, quantities):
    emit(key, sum(quantities))

# job 2 (per category: partition by category, sort by -units)
def map2(((category, product), units)):
    emit(category, (units, product))
def reduce2(category, pairs):
    top = sorted(pairs, reverse=True)[:N]    # or a bounded heap of size N
    for rank, (units, product) in enumerate(top, 1):
        write(category, rank, product, units)
```

A **bounded min-heap** of size N keeps memory small for huge categories (Chapter {ch:ch-ds}): push each product and pop the smallest when the heap exceeds N; this is O(M log N) for M products. Reducers are partitioned by category, so a single category with enormous traffic can become a **skewed** reducer; mitigate with a two-level aggregation (partial top-N per shard, then merge).

{{fig sr-flow | Data flow for one hour. Logs of the past 7 days are mapped, shuffled by (category, product), summed, ranked, and published atomically.}}

**Windows.** "Last 7 days" can be computed as a **sliding window** recomputed each hour from raw logs (simple, expensive), or **incrementally**: keep hourly partial sums and add the newest hour while subtracting the hour that left the window (168 partials). Incremental aggregation reads far less data and is the practical choice at scale.

**Atomic publish.** Write results into a new versioned table or partition and swap a pointer when complete, so readers never see a half-written ranking.

## Correctness: duplicates, late data, ties {#sec-sr-correct}

- **Duplicates.** At-least-once logging can write the same sale twice. Give every sale a unique `sale_id` and de-duplicate in the job (distinct by id within the window), or make log writes idempotent. This is the same lesson as Chapter {ch:ch-async}: *exactly-once effects* come from idempotent processing, not magic delivery.
- **Late events.** A sale may reach the log hours late (a mobile client offline). Assign it to its **event time** hour and recompute affected partials; accept that last hour's numbers are provisional and settle after a lateness allowance (say 6 hours).
- **Refunds and cancellations.** Record as negative events or tombstones so units decrease; decide whether rank counts net or gross sales.
- **Ties.** Break ties deterministically (units, then revenue, then product id) so the ranking does not flicker between runs.
- **Category changes.** If a product moves category, decide whether history moves with it; record the category *as of the sale* for historical accuracy.
- **Reconciliation.** Periodically compare the pipeline's totals with the orders database (a trusted source) and alert on drift beyond a tolerance, such as 0.1%.

::: worked
**Incremental window.** Hourly partial for Kitchen, product P: hours 1..168 hold units u₁..u₁₆₈; weekly total T = Σuᵢ. When hour 169 arrives with u₁₆₉, new total = T + u₁₆₉ − u₁. Cost: two updates per product per hour instead of re-reading 168 hours of logs, a reduction of about 84 times in data read. If hour 169 later receives a late sale of 3 units, add 3 to u₁₆₉ and to T.
:::

## Streaming alternative {#sec-sr-stream}

If ranks must be fresh within seconds or minutes, replace the batch job with a **stream processor** consuming the sales log (Chapter {ch:ch-async}): it keeps per-key counters in windows, emits updated counts, and a sink maintains top-N per category (a sorted set in an in-memory store, scored by units). Event-time windows, watermarks for lateness and checkpointed state give accuracy comparable to batch. A common hybrid is the **lambda** approach: a streaming layer for fresh approximate values plus a nightly batch recomputation that is authoritative; the **kappa** variation reprocesses the same log through the same streaming code to backfill. State the cost: streaming is operationally harder than a daily batch, so choose it only when freshness is a requirement.

**Approximate top-k.** At extreme volume, use a **heavy-hitters** structure (count-min sketch plus a small heap, Chapter {ch:ch-ds}) to track the top products in bounded memory with a small, controlled error: acceptable for "popular" lists but not for revenue accounting.

## Serving ranks {#sec-sr-serve}

Reads are 40,000 per second but the data changes hourly, so a **cache** (Chapter {ch:ch-cache}) in front of the analytics store is very effective: key `rank:{category}:{window}` holds the top-N list (a few kilobytes), with a TTL near the refresh period or invalidated on publish. A product's own rank is stored as a field of its product data, or looked up from the category list (the top 100 only; beyond that show "Top 10,000" style buckets). Because publishes are atomic and versioned, readers see either the old or the new list, never a mix. Use a CDN for public category pages.

**API.** `GET /v1/categories/{id}/bestsellers?window=7d&limit=50` returns an ordered list with `rank`, `product_id`, `units` (or a rounded band), and `as_of` timestamp so users and clients know how fresh it is.

## Failure handling and operations {#sec-sr-ops}

*Job fails midway*: it is restartable; output is written to a new version and published only on success, so the previous ranking stays live. *Skewed category*: two-level aggregation. *Late or missing logs*: monitor the log's completeness per hour (event counts compared with the Sales API's counter) before publishing. *Analytics store down*: serve the cached or last published list with a stale marker. *Data privacy*: aggregated ranks reveal no individual purchase; keep buyer ids out of the analytics logs.

**Metrics.** Job duration and success, freshness (`now − as_of`), reconciliation drift, duplicate rate, late-event rate, reducer skew, cache hit ratio. **Cost.** Compute for batch jobs scales with the window size if recomputed from raw logs, which is why the incremental design matters; storage is dominated by raw logs, moved to cheaper tiers after 30 days.

## Alternatives and trade-offs {#sec-sr-alt}

Table[sr-alt]: Decisions and alternatives.

| Decision | Chosen | Alternative | Reason | Revisit if |
|---|---|---|---|---|
| Compute | Hourly incremental batch | Streaming | Simplicity, accuracy | Need minute-level freshness |
| Window | Hourly partials, add/subtract | Recompute weekly from raw | 80+ times less data | Tiny data |
| Duplicates | De-dup by sale id | Trust the log | Exactness | Idempotent log guaranteed |
| Results store | SQL analytics table (versioned) | NoSQL or sorted set | Ad-hoc queries | Very high write churn |
| Serving | Cache plus CDN | Query DB on each view | 40,000 reads per second | Low traffic |
| Top-k | Exact | Count-min plus heap | Accuracy | Extreme cardinality |

::: failure
**Failure modes (summary).** Double counting; late sales missed; reducer skew on a huge category; half-published results; rank flicker from ties; stale data presented as fresh; drift versus the orders database; unbounded growth of the results table.
:::

::: misconception
- *"Real-time is always better."* Hourly ranking is enough for most shoppers and far cheaper.
- *"Exactly-once delivery solves duplicates."* Make processing idempotent.
- *"Sort all products to get the top N."* Use a bounded heap or partial sort.
- *"A cache makes ranks wrong."* Staleness is bounded and labelled.
:::

::: interview
**Q1. How do you compute the weekly top sellers?** Log sales, aggregate per (category, product) per hour, maintain a rolling 168-hour sum, rank per category, publish atomically.

**Q2. How would you make it near real time?** Streaming windows with watermarks plus a sorted-set sink, with batch reconciliation.

**Q3. How do you avoid counting a sale twice?** Unique sale ids and idempotent aggregation.

**Q4. How do you handle one gigantic category?** Two-level aggregation and a bounded heap.
:::

::: exercise
1. With 6 billion sales per month at 80 bytes each, compute log volume per month and for a 7-day window, and the average sales per second.
2. A product sold [5, 3, 0, 4, 2, 6, 1] units on seven days; on day 8 it sells 7. Show the update to the weekly total with the add/subtract method.
3. Two products tie at 120 units. Define a deterministic tiebreak and explain why it matters.
4. Estimate memory for a bounded heap of N = 100 over 5 million products versus sorting all.

**Answers.**
1. 6×10⁹ × 80 B = 480 GB per month; 7 days ≈ 480 × 7/30 = 112 GB; 6×10⁹ / 2.592×10⁶ s ≈ 2,300 per second (30-day month).
2. Initial total = 21. Day 8: 21 + 7 − 5 (day 1 leaves) = 23.
3. Order by units desc, then revenue desc, then product id asc; without it, results flip between runs and users see rank changes that mean nothing.
4. Heap of 100 entries × 16 B = 1.6 KB; sorting all 5 million × 16 B = 80 MB (and O(M log M) time) per category-job instance.
:::

::: summary
- Huge input, tiny output: aggregate in batch, serve from a cache.
- Incremental windows (add the new hour, subtract the old) save most of the work.
- Correctness needs de-duplication by id, event-time handling, deterministic ties and reconciliation.
- Publish atomically; label freshness; consider streaming only when freshness demands it.
:::

::: revision
- [ ] I can sketch the log → MapReduce → store → cache pipeline.
- [ ] I can explain the incremental weekly window.
- [ ] I can list duplicate, late-data and tie handling.
:::
