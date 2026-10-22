%derived Notebook chapter 12.2 (Twitter timeline and search: the scale table, fan-out on write, the User Graph service, search service, notification push)
%added API and data model, fan-out on read and the hybrid for celebrity accounts, timeline cache sizing, media handling, ranking, failure modes, abuse, cost and alternatives
# Case Study: A Social Timeline and Search {#ch-twitter}

::: objectives
After this chapter you can:

- derive the dominant loads of a read-heavy social feed and explain why they dictate the architecture;
- compare fan-out on write, fan-out on read and the hybrid approach, and size a precomputed timeline cache;
- design the supporting services: user graph, search, notifications, media;
- identify and handle the celebrity problem, ordering, duplicate delivery and failures.
:::

::: prereq
Chapters {ch:ch-nosql} (query-first modelling), {ch:ch-cache}, {ch:ch-async} (queues, fan-out), {ch:ch-distdata} (eventual consistency, hot keys) and {ch:ch-interview}.
:::

## Problem and requirements {#sec-tw-req}

**The problem.** Design the core of a microblogging service where users post short messages ("tweets"), follow other users, see a **home timeline** of recent posts by the people they follow, view a **user timeline** (one person's posts), **search** posts by keyword, and receive **push notifications**.

**Functional requirements.** Post a tweet (text and optional media). Follow and unfollow. View the home timeline and a user timeline. Search tweets. Notifications for mentions and replies. Out of scope (stated explicitly): ranking algorithms beyond reverse-chronological, direct messages, ads, trends, the full complexity of retweets and quote tweets, moderation tooling (mentioned under abuse).

**Non-functional requirements.** **Reads vastly exceed writes**; the home timeline must load fast (p95 under 200 ms). The service must be **highly available**: the timeline should degrade rather than fail. **Eventual consistency is acceptable**: a tweet may take a few seconds to appear in followers' timelines. A user must always see their *own* tweet immediately (read-your-writes, Chapter {ch:ch-scaling-sql}). Durability: posted tweets are not lost.

## Scale estimate {#sec-tw-scale}

Table[tw-scale]: Assumptions and derived quantities (from the notebook; all are assumptions).

| Quantity | Assumption | Derived |
|---|---|---|
| Tweets | 500 million per day | 5×10⁸ / 86,400 ≈ 5,800, call it ~6,000 per second |
| Deliveries | each tweet reaches ~10 followers' timelines on average | ~60,000 fan-out writes per second |
| Timeline reads | 250 billion per month | 2.5×10¹¹ / 2.5×10⁶ ≈ 100,000 per second |
| Search | 10 billion per month | ≈ 4,000 per second |
| Storage | ≈ 10 KB per tweet including media references and metadata | 5 TB/day ≈ 150 TB/month ≈ 5.4 PB in 3 years |

**What the numbers say.** Reads (100,000/s) outnumber tweet creation (6,000/s) by about 17 to 1, and every read needs the *combined* posts of many followed accounts. Computing that at read time would be far too expensive, so we **precompute** timelines: doing more work on write (60,000 fan-out writes per second) to make reads a single cache lookup. Storage at petabyte scale rules out one database: we need sharding and an object store for media. Note that the *average* of 10 followers hides a heavy-tailed distribution: most users have few followers; a few have tens of millions. That tail drives the hardest part of the design.

## Data model and API {#sec-tw-data}

```http
POST /v1/tweets               {"text": "...", "media_ids": [..]}  -> 201 {"id": "1741...", "created_at": "..."}
GET  /v1/timeline/home?limit=50&cursor=...   -> 200 {"tweets": [..], "next_cursor": "..."}
GET  /v1/users/{id}/tweets?limit=50&cursor=... -> 200
POST /v1/users/{id}/follow    DELETE same path to unfollow
GET  /v1/search?q=keyword&limit=20&cursor=...
```

Timelines use **cursor pagination** (Chapter {ch:ch-api}): clients send the id of the last tweet seen; new tweets appearing at the top never shift pages.

**Tweet ids** must be unique and **roughly time-ordered** so a timeline can be sorted by id: use a *Snowflake-style* id generator: a 64-bit number made of a millisecond timestamp, a machine id and a per-millisecond sequence number. It needs no central coordination and sorts by creation time.

Table[tw-data]: Main data and where it lives.

| Data | Access pattern | Store | Key |
|---|---|---|---|
| Tweets | By id; by author in time order | Sharded wide-column or SQL | `(author_id, tweet_id)` for user timeline; `tweet_id` lookup |
| Follow graph | Who does X follow? Who follows X? | Sharded store with two views (follows and followers) | `(user_id) -> list` in both directions |
| Home timeline cache | Latest ~800 tweet ids per user | In-memory list store (Redis-style) | `home:{user_id}` |
| Media | Fetch by id | Object store plus CDN | `media_id` |
| Search index | Keyword to tweet ids | Search cluster (inverted index) | term |
| Notifications | Per-user inbox | Wide-column or queue-backed store | `(user_id, time)` |

## Architecture {#sec-tw-arch}

{{fig tw-arch | High-level architecture. Writes create a tweet and trigger an asynchronous fan-out job; reads fetch a precomputed timeline from the cache and hydrate tweets from the tweet store. Search, notifications and media are separate services fed by events.}}

Follow {fig:tw-arch}. The **write path** (blue in your mind): the client posts to the **API tier**; the tweet is stored durably; an event is published to a **queue**; a **fan-out service** reads the follower list from the **user graph service** and inserts the tweet id into each follower's **home timeline cache**; the **search indexer** and **notification service** consume the same event. The **read path**: the API tier reads the timeline's list of tweet ids from the cache, **hydrates** them (fetches tweet bodies and author profiles, from a tweet cache and then the store), and returns the page.

## The core decision: fan-out strategy {#sec-tw-fanout}

How does a tweet get into the timelines of everyone who should see it?

**Fan-out on write (push).** At post time, insert the tweet id into every follower's timeline list. Reads are trivial (one list lookup), at the cost of write amplification: one tweet becomes *F* writes, where *F* is the follower count.

**Fan-out on read (pull).** Store tweets only by author. At read time, fetch the list of accounts followed, get each one's recent tweets, and merge by time. Writes are cheap; reads are expensive (one lookup *per followed account*) and slow at 100,000 reads per second.

**Hybrid.** Use push for ordinary accounts and pull for **very popular accounts**. A celebrity with 50 million followers would cause 50 million writes per tweet (and delay delivery by minutes). Instead, store the celebrity's tweets by author only. At read time, the timeline service takes the precomputed list (from push) and **merges in recent tweets from the few celebrities that user follows**.

{{fig tw-fanout | Hybrid fan-out. Ordinary authors push tweet ids into followers' cached timelines at write time; celebrity tweets are not pushed and are merged in at read time from the author's own recent-tweets list.}}

Table[tw-fan]: Fan-out strategies compared.

| | Push (on write) | Pull (on read) | Hybrid |
|---|---|---|---|
| Write cost | High, proportional to followers | Low | High for normal users, low for celebrities |
| Read cost | Very low | High, proportional to follows | Low plus a small merge |
| Timeliness | Delayed for huge accounts | Immediate | Immediate for celebrities |
| Wasted work | On inactive followers | None | Limited |
| Complexity | Medium | Medium | High |

**Refinements.** Push only to **active** users (those who logged in recently); inactive users' timelines are rebuilt on demand when they return. Drop the oldest ids so each timeline is bounded (for example the latest 800). For a **brand-new follow**, backfill recent posts of the followed account into the timeline asynchronously.

::: worked
**Sizing the timeline cache.** Each timeline stores about 800 tweet ids at 8 bytes each = 6.4 KB; add overhead (list structure, keys), say 10 KB per user. If 300 million users are *active enough to cache*, that is 3 TB of memory, or about 30 cache nodes of 100 GB (plus replicas: about 60). Only caching timelines for recently active users (say 100 million) cuts it to 1 TB. The fan-out throughput: 60,000 inserts per second spread over those nodes is 1,000 to 2,000 each, easy. The cost: memory is the dominant expense; hence tight bounds, inactive-user eviction, and rebuild-on-demand.
:::

### Write flow and read flow

{{fig tw-flow | Posting and reading. The post returns once the tweet is durable and queued; the fan-out happens asynchronously. A read fetches ids from the timeline cache and hydrates them.}}

**Read-your-writes.** The poster's own client inserts the new tweet into its local view at once, and the server also writes it synchronously into the poster's own timeline cache, so the author never sees their tweet missing even if fan-out to followers is still in progress.

## Supporting services {#sec-tw-support}

**User graph service.** Stores who follows whom in two directions (`following(u)` and `followers(u)`), sharded by user id. It must answer "give me the followers of u in pages" for fan-out and "does a follow b?" for authorisation. Hot celebrity follower lists are paged and cached. The notebook calls this the *User Graph Service*; it can be backed by a sharded database or a graph-capable store.

**Search service.** Tweets are indexed into an **inverted index** (term → list of tweet ids, Chapter {ch:ch-nosql}). Indexing is asynchronous: the indexer consumes tweet events, tokenises (lower-case, strip punctuation, handle hashtags and mentions), and updates the index within seconds ("near-real-time search"). The index is **partitioned by time** (recent tweets in hot, small partitions on fast storage; older ones in larger, colder partitions) and each partition by tweet-id hash. A query is a **scatter-gather**: the query router sends the query to relevant partitions, each returns its top-k by score, and the router merges. At 4,000 queries per second, results for popular queries can be cached briefly.

**Notifications.** Mentions and replies publish an event; the notification service determines recipients, applies user preferences, stores an in-app notification, and pushes through a mobile push provider. Rate-limit and batch ("12 people liked your tweet") to avoid floods. Delivery is at-least-once, so the client deduplicates by notification id (Chapter {ch:ch-async}).

**Media.** Images and video go to an **object store** via **pre-signed upload URLs** (the client uploads directly, not through the API servers). A worker pipeline generates thumbnails and transcodes video into several resolutions; the tweet stores media ids; delivery goes through a **CDN**. Large storage drives the bulk of the 150 TB per month.

## Scaling, bottlenecks and failure handling {#sec-tw-scale2}

**Bottlenecks.** (1) *Fan-out volume and celebrity spikes*: handled by the hybrid model, queue-based buffering and worker autoscaling on queue age. (2) *Timeline cache memory*: bounded lists, active users only. (3) *Hot keys*: a celebrity's tweet is read by millions; cache the tweet object with local in-process caches and replicate hot keys (Chapter {ch:ch-distdata}). (4) *Tweet storage growth*: shard by `author_id` or tweet id, tier old data to cheaper storage. (5) *Graph reads*: cache follower pages.

**Failure handling.** *Cache lost*: rebuild timelines from the tweet store using the pull method (slow but correct), throttle rebuilds to protect the database, and serve a degraded, partial timeline rather than an error. *Fan-out worker lag*: tweets appear late, but nothing is lost since the queue is durable; alert on lag. *Duplicate fan-out* (a worker retries): inserting an id already present in a timeline list is idempotent when the list is a sorted set keyed by tweet id. *Out-of-order*: sort by Snowflake id. *Search index down*: serve cached results or a clear message; timelines unaffected. *Region failure*: replicate tweets and graph to a second region (asynchronous) and fail over reads, accepting loss of the last seconds of writes; this is a business decision about RPO.

**Security, privacy and abuse.** Authorise every call; **protected accounts** restrict who may see tweets (enforce at read time as well as fan-out time, since follow status can change); block, mute and report features; rate-limit posting, following and search (Chapter {ch:ch-entry}); detect bot networks; handle deletion (a deleted tweet must disappear from caches, timelines and search; propagate a delete event and tolerate brief lag); keep personal data out of logs. Content moderation pipelines are a large separate system.

**Operations and cost.** Metrics: tweet create latency, fan-out lag (p99 seconds from post to last follower), timeline cache hit ratio, search p99, queue age, error rates, hot-key alerts. Deploy gradually (canary) because this system is always busy. Cost is dominated by cache memory, storage (5.4 PB), egress for media (mitigated by CDN) and search index infrastructure.

## Alternatives and trade-offs {#sec-tw-alt}

Table[tw-alt]: Decisions and alternatives.

| Decision | Chosen | Alternative | Reason | Revisit if |
|---|---|---|---|---|
| Fan-out | Hybrid push/pull | Pure push or pure pull | Balances read speed and celebrity cost | Follower distribution changes |
| Timeline store | In-memory lists of ids | Precomputed in a database | Fast reads; ids are small | Memory too costly: store on SSD with a cache |
| Consistency | Eventual, read-your-writes for author | Strong | Availability and speed | Regulatory needs |
| Search | Separate inverted-index cluster | SQL full-text | Scale and relevance features | Tiny scale |
| Ids | Snowflake time-ordered | UUIDs | Sortable, compact | Clock concerns: add safeguards |
| Media | Object store + CDN | Database blobs | Cost, throughput | None |

**Follow-up questions to expect.** *How do you rank rather than sort by time?* Add a scoring service that re-ranks candidates from the timeline cache (blending recency, engagement, relationship), trading transparency for engagement. *How do retweets work?* Store a pointer to the original; fan out the retweet as an event. *How do you delete a user and all their tweets?* Delete events plus a background sweep (Chapter {ch:ch-security}). *How would you support trending topics?* Stream processing with sliding windows and count-min sketches (Chapter {ch:ch-ds}). *How do you shard tweets if one user is extremely prolific?* Key by tweet id and index by author separately.

::: failure
**Failure modes (summary).** Celebrity fan-out overwhelming workers; timeline cache eviction storm; unbounded lists; fan-out lag; stale protected-account visibility; delete not propagating; search index drift; hot-key cache node saturated; retry storms on the graph service.
:::

::: misconception
- *"Push is always better because reads are cheap."* Push breaks for accounts with huge audiences.
- *"The timeline must be perfectly consistent."* A few seconds of delay is acceptable and enables a far cheaper design.
- *"Search can use the primary database."* At 4,000 queries per second over petabytes it needs a dedicated index.
- *"The average follower count describes the load."* The tail dominates cost and risk.
:::

::: interview
**Q1. How do you build the home timeline?**
Precompute: on post, asynchronously fan out the tweet id to each follower's cached timeline list; reads fetch ids and hydrate. For celebrities skip push and merge at read time.

**Q2. What is the celebrity problem and how do you solve it?**
One tweet needing millions of writes delays delivery and overloads workers; use a hybrid model with pull for accounts above a follower threshold.

**Q3. How is search implemented?**
Asynchronous indexing into a time-partitioned inverted index; scatter-gather queries merged by score; short-lived result caching.

**Q4. How do you ensure the author sees their own tweet immediately?**
Write it synchronously to the author's own timeline and show it locally in the client; the rest of the fan-out may lag.
:::

::: exercise
1. If the average follower count rises from 10 to 50, what is the new fan-out write rate? What changes in the design?
2. Choose a follower threshold for switching to pull, given workers can do 100,000 inserts/s total and 6,000 tweets/s arrive. Argue the trade-off.
3. Estimate memory for timelines of 200 million cached users with 500 ids each at 8 bytes plus 40% overhead.
4. A tweet is deleted. List the places it must be removed and how.

**Answers.**
1. 6,000 × 50 = 300,000 inserts per second: three times the worker budget. Respond with more workers, a lower celebrity threshold, pushing only to active users, batching inserts, and relying on cache bounds.
2. If a tweet by a user with *F* followers costs *F* inserts, a threshold such as 100,000 followers bounds a single tweet's cost to 100,000 inserts (one second of the total budget); lower thresholds shift cost to reads. Pick it by measuring the follower distribution and read cost per merged celebrity (usually merges of fewer than ~10 celebrity accounts keep reads cheap).
3. 200 M × 500 × 8 B = 800 GB; with 40% overhead ≈ 1.12 TB.
4. Tweet store (tombstone or delete), tweet cache, timeline caches (lazy filtering at read time because removing from millions of lists is costly), search index (delete event), media (if unreferenced), analytics and backups (retention policy); readers filter out deleted ids during hydration.
:::

::: summary
- Reads dominate (≈17:1) and need many accounts' posts; precompute timelines at write time.
- Fan-out on write is fast to read but breaks for celebrities; the hybrid merges celebrity posts at read time.
- Timelines are bounded lists of ids in memory; tweets are hydrated from caches and stores; ids are time-ordered.
- Search is an asynchronously updated, partitioned inverted index with scatter-gather queries; media uses an object store and CDN.
- Eventual consistency is acceptable; protect the author's read-your-writes; plan for lag, hot keys, deletes and abuse.
:::

::: revision
- [ ] I can derive writes, fan-out writes and reads per second.
- [ ] I can compare push, pull and hybrid and size the timeline cache.
- [ ] I can describe the search pipeline and scatter-gather.
- [ ] I can list failure modes and degradations.
:::

::: supplement
**Further reading.** Raffi Krikorian, "Timelines at Scale" (QCon 2012) on Twitter's fan-out architecture; the Snowflake id generator announcement; Earlybird, the real-time search system described in Twitter engineering publications; Kleppmann, *Designing Data-Intensive Applications*, the Twitter example in chapter 1.
:::
