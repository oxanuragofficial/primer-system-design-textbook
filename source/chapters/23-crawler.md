%derived Notebook chapter 12.3 (web crawler and search: the scale table, links_to_crawl and crawled_links, the crawl loop, duplicate detection by page signature, reverse index service, document service, query API)
%added the frontier with politeness queues, robots.txt, URL normalisation, spider traps, freshness scheduling, simhash near-duplicate detection, DNS caching, partitioning workers by host, failure handling and ethics
# Case Study: A Web Crawler and Search Engine {#ch-crawler}

::: objectives
After this chapter you can:

- estimate crawl rate, bandwidth and storage for a web-scale crawler;
- design the URL frontier with priority, politeness and de-duplication;
- detect exact and near-duplicate pages and avoid spider traps;
- connect crawling to indexing and query serving with a reverse (inverted) index;
- identify failure modes and ethical constraints (robots.txt, rate limits).
:::

::: prereq
Chapters {ch:ch-ds} (bloom filters, heaps, tries), {ch:ch-nosql}, {ch:ch-async} (queues), {ch:ch-distdata} (partitioning) and {ch:ch-interview}.
:::

## Problem and requirements {#sec-cr-req}

**The problem.** Design a system that **crawls the web**: starting from seed URLs, it downloads pages, extracts links, and keeps following them; it stores what it finds and builds a **search index** so users can type a query and receive a ranked list of matching pages, each with a **title and snippet**.

**Functional requirements.** Crawl pages from seed URLs, discovering new ones. Never crawl the same page repeatedly without reason (**avoid loops and duplicates**). Re-crawl pages periodically to stay fresh (more often for pages that change often). Build an index from page text. Serve queries returning a ranked list with titles and snippets.

**Non-functional requirements.** *Scalable* (billions of pages). *Polite* (do not overload sites; obey robots.txt). *Robust* (the web is full of malformed pages, traps, slow servers). *Extensible* (new content types). Search results with **low latency** (tens to hundreds of milliseconds) and high availability; the crawl itself is a throughput-oriented batch-like pipeline that can tolerate delays and restarts.

**Scope.** Out of scope: sophisticated ranking (learning to rank, link analysis in detail), personalisation, handling JavaScript-rendered pages (mention as an extension), image and video search, and legal and indexing-policy details. Assume classic components of Chapter {ch:ch-ds} and Chapter {ch:ch-nosql}.

## Scale estimate {#sec-cr-scale}

Table[cr-scale]: Assumptions and derived quantities (from the notebook; all are assumptions).

| Quantity | Assumption | Derived |
|---|---|---|
| Links | 1 billion pages, refreshed about weekly | ≈ 4 billion crawls per month |
| Crawl rate | 4×10⁹ / 2.5×10⁶ s | ≈ 1,600 page fetches per second |
| Page size | ≈ 500 KB per page | 1,600 × 500 KB = 800 MB/s ≈ 6.4 Gbps of download |
| Storage | 4×10⁹ crawls × 500 KB per month (raw, if all stored) | ≈ 2 PB per month if every crawl is stored; far less if only changed, compressed or text-only |
| Search | 100 billion queries per month | ≈ 40,000 queries per second |
| Index | Text only, compressed (assume ≈ 5% of raw) | tens of terabytes to petabytes, partitioned |

**What the numbers say.** 1,600 fetches per second is sustained work for a *fleet*, not one machine: if one crawler worker manages 20 concurrent downloads at 500 ms average, it does about 40 pages per second, so you need about 40 workers (more with headroom). The bandwidth (6.4 Gbps) and the storage (petabytes) are the real constraints, so store **compressed text**, keep **only changed pages**, and retain raw HTML only briefly. The query side (40,000 per second) is a separate scaling problem: a partitioned, cached index serving system.

## Architecture overview {#sec-cr-arch}

{{fig cr-arch | The crawl and search pipeline. The frontier feeds crawler workers; fetched pages are checked for duplicates, parsed, stored, and their links are fed back. Indexers build the inverted index from stored documents; the query path uses the index and the document store.}}

The system is a loop with a branch. In {fig:cr-arch}: the **URL frontier** hands out URLs to crawl. **Crawler workers** fetch them (respecting politeness and robots.txt), pass pages to a **content processor** that extracts text and links, computes a **signature** for duplicate detection, and stores the result in the **document store**. New links go back to the frontier (after URL normalisation and filtering). In parallel, **indexers** read new documents and update the **inverted index**; a **query service** answers searches by consulting the index and the document store.

## The URL frontier {#sec-cr-frontier}

The frontier is the heart of a crawler. It must decide **what to fetch next** while meeting three goals: **priority** (important and fast-changing pages first), **politeness** (never hammer one site), and **freshness** (revisit on a sensible schedule).

The notebook's version uses two stores: `links_to_crawl`, a ranked list ordered by priority (for instance a sorted set in an in-memory store), and `crawled_links`, a record of what has been fetched (URL and page signature) in a NoSQL store. A scalable design extends this into the classic two-layer queue structure:

{{fig cr-frontier | A two-layer frontier. Front queues order URLs by priority; a router maps each URL to a back queue per host; a scheduler releases at most one URL per host per politeness interval.}}

- **Front queues (priority)**: URLs are scored (page importance, expected change rate, depth, domain quality) and placed into several priority queues; a selector draws from higher-priority queues more often.
- **Back queues (politeness)**: each back queue contains URLs for **one host only**. A scheduler keeps a **heap** of (next-allowed-time, host) so that after fetching from host *h* it will not return to *h* until, say, 1 to 10 seconds later (or the `Crawl-delay` the site asks for). Workers are assigned **by host hash**, so one worker owns a host's rate limiting, keeps its connections alive and caches its robots.txt and DNS answers.
- **Persistence**: the frontier is far too big for memory alone; keep the hot portions in memory and the rest on disk (log-structured, Chapter {ch:ch-ds}) so crashes do not lose the queue.

**URL normalisation and filtering** before enqueueing: lower-case the host, remove default ports and fragments (`#section`), resolve relative links, sort or drop tracking query parameters, collapse `/a/../b`, and reject unwanted schemes and file types. Without this, `HTTP://Example.com:80/a` and `http://example.com/a` count as two pages.

**Seen-URL detection.** Before adding a URL, ask "have I seen it?" With billions of URLs a hash set in memory is too big; use a **bloom filter** (Chapter {ch:ch-ds}) for the fast path (definitely-new URLs skip any lookup; a false positive merely skips a rare page), backed by the `crawled_links` store for exact answers on "probably seen".

::: worked
**Memory for the seen set.** 10 billion distinct URLs discovered (more than the 1 billion we keep, because links point at pages we reject). Exact set at 16 bytes per URL hash = 160 GB: shardable but heavy. A bloom filter with 10 bits per entry needs 10¹⁰ × 10 bits = 100 Gbit = 12.5 GB at about 1% false-positive rate: it fits in memory on a few machines, shared by host-hash partition. The 1% of URLs wrongly considered seen are skipped *this round*; they are likely rediscovered through other links.
:::

## Fetching politely and robustly {#sec-cr-fetch}

- **robots.txt**: fetch and cache each host's `/robots.txt`; obey `Disallow` rules and crawl delays. Re-fetch periodically (for example daily). A crawler that ignores it risks being blocked and violates web norms.
- **Identify yourself** with a descriptive `User-Agent` and contact information, so site owners can reach you.
- **DNS caching**: DNS lookups are slow and a naive crawler spends much of its time on them (Chapter {ch:ch-network}); run a local caching resolver and prefetch.
- **Timeouts and limits**: connect and read timeouts, a maximum page size (stop after a few MB), maximum redirects, and content-type checks. A slow server must not tie up a worker (Chapter {ch:ch-resilience}).
- **Retry** transient failures a few times with backoff; mark hosts that keep failing as temporarily blocked (a per-host circuit breaker).
- **Conditional requests**: send `If-Modified-Since` or `If-None-Match` with the stored ETag; a `304 Not Modified` saves bandwidth and storage.

## Duplicates, traps and freshness {#sec-cr-dup}

**Exact duplicates.** Compute a **signature** of the page content (a hash of the normalised text). If the signature already exists in `crawled_links`, the page is a duplicate: record the URL as an alias and do not store or re-index it. The notebook also suggests detecting duplicates *in bulk* with a MapReduce job that groups URLs by signature and keeps one canonical copy.

**Near-duplicates.** Many pages differ only by a timestamp or advertisement. **SimHash** (a locality-sensitive hash) produces a short fingerprint in which similar documents have fingerprints differing in only a few bits, so near-duplicates are found by comparing fingerprints within a small Hamming distance. Alternatively compare sets of *shingles* (overlapping word sequences) using MinHash. Use these to avoid indexing thousands of nearly identical pages.

**Spider traps.** A trap generates an unbounded number of URLs (an infinite calendar, session ids in URLs, `/a/a/a/a/...`). Defences: limit **crawl depth** and **URLs per host**, limit URL length, detect repeated path segments, normalise away session parameters, and use priority scoring so low-value, deep or unusual URLs sink.

**Freshness.** Pages change at different rates; a news front page changes hourly, a manual yearly. Estimate each page's **change rate** from the history of crawls (did the signature change?) and schedule the next visit adaptively: increase the interval when unchanged, decrease it when changed, weighted by importance. A uniform weekly refresh (our estimate) wastes bandwidth on static pages and misses fast-changing ones.

## From documents to search results {#sec-cr-search}

After a page is stored, the **indexing** stage extracts terms and updates the **inverted (reverse) index**: a map from each term to the list of documents containing it (a *postings list*), usually with positions and weights. A query for "system design" fetches the postings list for each term and intersects them, ranks the candidates and returns the top results.

{{fig cr-index | A tiny inverted index. Each term points to the documents that contain it; a multi-word query intersects the lists.}}

The notebook splits the query side into services: a **Reverse Index Service** (given terms, return matching document ids ranked by a relevance score), a **Document Service** (given ids, return title and snippet), and a **Query API** (accepts the query, parses and normalises it, calls both services, and returns the results). Normalisation includes lower-casing, tokenising, removing stop words, stemming ("designing" to "design"), spelling correction and synonyms.

**Scale of the query side.** The index is far too large for one machine, so it is **partitioned** by document (each shard indexes a subset of documents) and each shard is **replicated**. A query goes to *every* shard (scatter), each returns its local top-k, and the query service merges (gather). Latency is set by the *slowest* shard, so tail latency matters (Chapter {ch:ch-intro}); hedged requests to replicas help. Cache popular queries (the head of the query distribution repeats heavily), and keep the index of the most important pages on fast storage (a tiered index). Ranking combines text relevance (term weights such as TF-IDF or BM25), link-based authority (PageRank-style computation done offline), freshness and other signals; a two-stage pipeline (cheap candidate retrieval, then costlier re-ranking of the top few hundred) keeps it fast.

::: supplement
**Computing link-based authority offline.** The web graph (pages and links) is processed in large batch jobs: PageRank starts with equal scores and repeatedly passes each page's score along its outgoing links, damped by a factor, until scores converge. At web scale this is a distributed graph computation (MapReduce or a graph engine) that runs periodically; its output is stored as a per-page score used by ranking. This also illustrates why the crawler stores *link structure* and not only text.
:::

## Scaling, failures and operations {#sec-cr-ops}

**Scaling.** Partition by **host hash**: frontier shards, crawler workers and per-host state align, so politeness stays local. Add workers to raise throughput; the limiting resources are bandwidth, DNS, and politeness (a few huge sites hold many pages, so per-host rate limits cap how fast you can crawl them regardless of fleet size). Use **batching** and **append-only logs** for storage writes (Chapter {ch:ch-ds}); store raw content compressed in an object store or distributed file system, and structured metadata in a wide-column store.

**Failure handling.** *Worker crash*: URLs it held are returned to the frontier after a lease timeout (a visibility timeout as in Chapter {ch:ch-async}); fetching is idempotent so a repeat is harmless. *Frontier lost*: rebuild from persisted logs; the crawl is restartable. *Site down or slow*: back off per host. *Poison pages* (huge, malformed, decompression bombs): size limits, sandboxed parsers. *Index shard failure*: replicas answer; degrade by omitting a shard's results rather than failing the query, and report partial results. *Clock or ordering issues*: do not rely on wall clock for dedupe.

**Security and ethics.** Parse untrusted content in sandboxes; do not execute scripts unless intentionally rendering; avoid fetching internal addresses via redirects (SSRF-style, Chapter {ch:ch-security}); respect robots.txt, rate limits and copyright and data-protection rules; honour removal requests; avoid crawling behind logins.

**Operations and cost.** Metrics: pages fetched per second, error and timeout rates, politeness violations (should be zero), frontier size and age, duplicate ratio, freshness (age of the average page), index lag (time from crawl to searchable), query p99, cache hit ratio. Cost: bandwidth and storage dominate the crawl, memory and CPU dominate serving.

## Alternatives and trade-offs {#sec-cr-alt}

Table[cr-alt]: Decisions and alternatives.

| Decision | Chosen | Alternative | Reason | Revisit if |
|---|---|---|---|---|
| Frontier | Two-layer priority + per-host queues | Single FIFO | Politeness and priority | Small crawl |
| Seen-URL check | Bloom filter + exact store | Exact set only | Memory efficiency | Need exactness |
| Duplicate detection | Content hash + SimHash | URL equality only | Mirrors and templates | Low duplication |
| Refresh | Adaptive per page | Uniform weekly | Freshness vs bandwidth | Uniform data |
| Index partition | By document, scatter-gather | By term | Balanced load, simpler updates | Very rare terms |
| Raw storage | Compressed, changed pages only | Keep everything | Cost | Compliance or research needs |

**Follow-up questions to expect.** *How do you crawl JavaScript-heavy sites?* A rendering tier with headless browsers (expensive: reserved for important pages). *How would you keep news fresh within minutes?* A separate fast-lane crawler using feeds, sitemaps and push notifications. *How do you handle a site that blocks you?* Respect it. *How do you detect and demote spam?* Link-graph analysis, content classifiers, domain reputation. *How do you make the crawl distributed across regions?* Crawl from regions near the sites to cut latency, with a global frontier coordinating hosts.

::: failure
**Failure modes (summary).** Overloading a small site (politeness bug); infinite spider traps filling the frontier; DNS bottleneck; frontier or seen-set loss; duplicate explosion bloating the index; stale index from slow re-crawl; scatter-gather tail latency; a poison page crashing parsers; bandwidth saturation; accidental violation of robots.txt.
:::

::: misconception
- *"A crawler is a loop over a list of URLs."* The frontier's priority, politeness and duplicate control are the design.
- *"More workers always crawl faster."* Per-host politeness and DNS or bandwidth limits cap throughput.
- *"Store every page forever."* It is unaffordable and mostly redundant.
- *"Hash equality finds all duplicates."* Near-duplicates need similarity hashes.
:::

::: interview
**Q1. How do you avoid crawling the same URL twice?**
Normalise URLs, check a bloom filter plus an exact store, and use page content signatures to catch duplicates under different URLs.

**Q2. How do you stay polite?**
Per-host back queues with a scheduler enforcing delays, robots.txt and crawl-delay compliance, host-aligned workers, identification in the User-Agent.

**Q3. How is the search index organised and queried?**
An inverted index partitioned by document and replicated; queries scatter to all shards, each returns top-k, results are merged; popular queries are cached; ranking in two stages.

**Q4. How do you decide how often to re-crawl a page?**
Adaptive scheduling from observed change rate and page importance; use conditional requests to save bandwidth.
:::

::: exercise
1. If the average page is 300 KB and the crawl must refresh 2 billion pages every 7 days, compute fetches per second and bandwidth in Gbps.
2. A worker handles 25 concurrent fetches, average 400 ms per fetch. How many workers sustain 2,000 fetches per second with 50% headroom?
3. Propose a signature scheme for catching near-duplicates among 10 billion pages and the approximate storage for fingerprints.
4. Design the schema of `crawled_links` and the index you need for fast "have we seen this signature?" checks.

**Answers.**
1. 2×10⁹ / (7 × 86,400) ≈ 3,300 fetches per second; 3,300 × 300 KB ≈ 1 GB/s ≈ 8 Gbps.
2. One worker: 25 / 0.4 = 62.5 fetches per second. Need 2,000 / 62.5 = 32 workers; with 50% headroom, 48.
3. A 64-bit SimHash per page, with lookups by permuted prefixes to find fingerprints within Hamming distance 3. 10¹⁰ × 8 B = 80 GB (plus index structures), shardable by prefix.
4. `crawled_links(url_hash PK, url, signature, last_crawl_time, etag, change_score, status)`; a secondary index (or separate table) keyed by `signature` to map signature to canonical URL; partition by `url_hash`.
:::

::: summary
- The frontier (priority, per-host politeness, persistence) is the core of the crawler.
- Normalise URLs, detect seen URLs with a bloom filter plus exact store, catch duplicates with content signatures and SimHash, and avoid traps.
- Schedule re-crawls adaptively; use conditional requests; store compressed text and changed pages only.
- Search uses a partitioned, replicated inverted index with scatter-gather queries, caching and two-stage ranking.
- Be polite and ethical; handle failures at every stage; measure freshness and index lag.
:::

::: revision
- [ ] I can estimate fetch rate, bandwidth and storage.
- [ ] I can draw the two-layer frontier.
- [ ] I can explain duplicate and near-duplicate detection.
- [ ] I can explain the inverted index and scatter-gather query.
:::
