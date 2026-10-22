%derived Notebook chapter 12.1 (Pastebin and URL shortener: requirements, the scale table, Base62 and MD5 key generation, SQL schema, read and write flows, analytics and expiry)
%added API contract, key-generation comparison with collision mathematics, object-store split, abuse and security, failure handling, cost, alternatives, follow-up questions
# Case Study: Pastebin and URL Shortener {#ch-pastebin}

::: objectives
After this chapter you can:

- scope a design problem and derive its scale from stated assumptions;
- design an API, data model and key-generation scheme for short links, comparing hashing, counters and pre-generated keys;
- trace write and read paths and apply caching, expiry and cleanup;
- find the bottlenecks and failure modes of the design and explain what you would change as traffic grows.
:::

::: prereq
Chapters {ch:ch-estimation}, {ch:ch-api}, {ch:ch-sql}, {ch:ch-cache} and {ch:ch-interview}.
:::

## Problem and requirements {#sec-pb-req}

**The problem.** Design a service where a user pastes text (or submits a long URL) and receives a short link; anyone with the link can view the content (or be redirected). This is the classic first design problem because the idea is simple while the interesting decisions (unique keys, read-heavy traffic, expiry, abuse) are real.

**Functional requirements.** Create a paste and get a short URL. Open a short URL and see the text. Optionally set an **expiration** (default: never, or a bounded default). Optional: private pastes. Basic **analytics** (monthly visit counts per link).

**Non-functional requirements.** **High availability** for reads: a broken link is a visible failure. **Low latency** for reads (target p95 under 200 ms). **Durability**: acknowledged pastes must not be lost. Links should be **hard to guess** for private content. Reads are far more frequent than writes.

**Scope and assumptions.** Out of scope: accounts, editing, syntax highlighting, full search. The service is **read-heavy** with a **10 : 1 read-to-write ratio**. Text pastes are small (about 1 KB on average, with an upper limit such as 512 KB).

## Scale estimate {#sec-pb-scale}

Table[pb-scale]: Scale assumptions and derived quantities (from the notebook; all are assumptions, not measurements).

| Quantity | Assumption | Derived |
|---|---|---|
| Writes | 10 million pastes per month | 10⁷ / 2.5×10⁶ s ≈ 4 per second (peak ~10×: ~40/s) |
| Reads | 100 million views per month (10 : 1) | ≈ 40 per second (peak ~400/s) |
| Size per paste | 1 KB text + ≈ 270 B metadata | ≈ 1.27 KB |
| Storage growth | 10 M × 1.27 KB | ≈ 12.7 GB per month; ≈ 450 GB in 3 years |
| Number of links | 10 M per month for 36 months | 360 million links |
| Key space needed | 360 M links, with margin | 7 Base62 characters = 62⁷ ≈ 3.5 trillion |

**What the numbers say.** 40 reads per second is *tiny*: a single database server and one application server could handle it. The scale is not the challenge. The interesting problems are (1) **generating unique, compact keys**, (2) **durable, cheap storage of content**, (3) **cleaning up expired data**, and (4) **abuse**. Conveying this early ("this is a small-scale problem; the care goes into keys and operations") shows judgement. We still design for growth: ten times and a hundred times these numbers (400 and 4,000 reads per second) remain modest, so the design should scale by adding standard components, not by re-architecting.

## API {#sec-pb-api}

```http
POST /v1/pastes
{"content": "hello world", "expires_in_seconds": 86400, "visibility": "unlisted"}
-> 201 Created   Location: /v1/pastes/7Hq2Zx
   {"id": "7Hq2Zx", "url": "https://paste.example/7Hq2Zx", "expires_at": "2026-10-13T09:30:00Z"}

GET /{id}               -> 200 text/plain  (or 302 redirect for a URL shortener)
                           404 Not Found | 410 Gone (expired)
DELETE /v1/pastes/{id}  -> 204   (owner token required)
GET /v1/pastes/{id}/stats -> 200 {"month": "2026-10", "views": 1832}
```

Design notes: creation accepts an `Idempotency-Key` header so a retried create does not make two pastes (Chapter {ch:ch-api}); the **delete token** is returned at creation, so anonymous users can still delete their own pastes; limit content size and enforce it on the server; return **410 Gone** for expired links to distinguish them from never-existed ones; for a URL shortener `GET /{id}` responds with a `301` or `302` redirect (a **301** is permanent and cached by browsers, so analytics miss repeat visits and later changes are ignored; a **302** keeps every click visible to the service).

## Data model {#sec-pb-data}

Separate **metadata** (small, queried, indexed) from **content** (larger, opaque, only fetched by key).

```sql
CREATE TABLE pastes (
  short_code   CHAR(7)      PRIMARY KEY,         -- the Base62 key
  content_key  VARCHAR(255) NOT NULL,            -- object-store key for the text
  owner_id     BIGINT       NULL,
  visibility   SMALLINT     NOT NULL DEFAULT 0,
  created_at   TIMESTAMP    NOT NULL,
  expires_at   TIMESTAMP    NULL,
  delete_token_hash CHAR(64) NOT NULL
);
CREATE INDEX idx_pastes_expires ON pastes (expires_at) WHERE expires_at IS NOT NULL;
```

Why this split? Pastes are up to hundreds of KB; storing them in database rows makes the database large and slows backups and replication. An **object store** is cheaper per gigabyte, durable, and scales effortlessly, and the database row stays small and cache-friendly. For pastes under a few KB, storing the text *inline* in the row is also a reasonable simplification; decide with the size distribution. **Primary key on `short_code`** makes the dominant lookup (by code) a single index seek. The index on `expires_at` supports the cleanup job. If the data outgrows one database, shard by `short_code` (hash), which is present in every read.

**SQL or NoSQL?** At 360 million small rows (about 100 GB of metadata) a relational database is comfortable, and its transactions help with uniqueness. A key-value or document store also fits (access is by key only) and scales further with less effort; choose on team skill and operational preference. The point to state is the *access pattern*: lookup by key, no joins.

## Generating keys {#sec-pb-keys}

The short code must be **unique**, **compact** (seven characters), and, for private pastes, **unguessable**. Three approaches:

**1. Hash and truncate.** Compute `MD5(content + timestamp + random)`, encode in Base62 (characters `a-z A-Z 0-9`), and take the first seven characters. Stateless and simple, but **collisions are possible** after truncation, so insert with a unique constraint and *retry with a new salt* on conflict. With *n* existing keys in a space of size *N* = 62⁷ ≈ 3.5 × 10¹², the chance a new random key collides is about *n* / *N*. At *n* = 360 million: 3.6 × 10⁸ / 3.5 × 10¹² ≈ 1 in 10,000. So roughly one in ten thousand creates retries once; the second attempt almost always succeeds. That is cheap, but the *check* requires a database round trip anyway.

**2. Counter plus Base62.** Keep a global counter, give each new paste the next integer, and Base62-encode it (counter 1,000,000 becomes `4c92`). **No collisions**, minimal length (seven characters last until 3.5 trillion). Costs: a central counter is a **bottleneck and a single point of failure** (mitigated by handing each application server a **block of ids** at a time, say 10,000), and sequential codes are **guessable and enumerable**, which leaks private pastes and lets competitors scrape. Fix by passing the number through a reversible scrambling step (a format-preserving permutation) so codes look random.

**3. Pre-generated key service.** A background job generates many random unused keys into a "key database" with two tables (*unused*, *used*). Application servers fetch a batch of keys into memory and hand them out; keys are moved to *used* when taken. Creation never hits collisions and never computes anything on the hot path, and the codes are unguessable. Costs: another component; keys fetched but unused when a server crashes are simply lost (acceptable in a 3.5-trillion space); the key database must be replicated.

Table[pb-keys]: Key-generation approaches.

| Approach | Collisions | Guessable | Hot-path cost | Failure risk | Best when |
|---|---|---|---|---|---|
| Hash + retry | Rare, handled by retry | No | One unique-insert, maybe a retry | Low | Small systems; stateless |
| Counter + Base62 | None | Yes (unless scrambled) | Minimal with id blocks | Counter service | Public links, simplicity |
| Pre-generated keys | None | No | Fetch from in-memory batch | Key service | Large scale, private links |

::: worked
**How long must the code be?** For 360 million links, can we use 6 characters? 62⁶ ≈ 56.8 billion. The *fill ratio* is 360 M / 56.8 B ≈ 0.63%, so a random 6-character code collides about 1 in 160 times: workable but with more retries and less margin for growth. With 7 characters the key space is 3.5 trillion (fill ratio 0.01%), giving a collision rate of about 1 in 10,000 and headroom for a hundred times growth. Seven characters it is. If custom aliases are allowed ("paste.example/my-notes"), reserve a separate namespace and always check availability.
:::

## Architecture {#sec-pb-arch}

{{fig pb-arch | High-level architecture. A CDN and cache absorb most reads; a small application tier handles API calls; metadata lives in a replicated SQL database and text in an object store; a background job cleans up expired pastes and a log pipeline computes analytics.}}

Walk through {fig:pb-arch}. **Clients** reach the service via **DNS** and a **CDN**. Because pastes are immutable once created, they are excellent candidates for caching, even at the CDN, with a TTL no longer than their remaining lifetime. Requests that miss go through a **load balancer** to **stateless application servers**. A **distributed cache** holds hot `short_code → (content or metadata)` entries. On a miss, the server reads **metadata from the SQL database** (a primary with read replicas) and **content from the object store**. A **key service** supplies codes on writes. A **cleanup worker** removes expired pastes. **Access logs** feed an **analytics job**.

### Write flow

{{fig pb-write | Creating a paste. The server obtains a key, stores the text in the object store, inserts the metadata row, and returns the link. Content is written first so a metadata row never points at missing content.}}

Ordering matters. The server writes the **content first**, then the **metadata row**. If it crashes between the two, the result is an orphaned object (harmless garbage collected later), never a metadata row pointing to nothing. The create call is made **idempotent** with the client's idempotency key stored beside the row.

### Read flow

{{fig pb-read | Reading a paste. The cache answers most requests. On a miss the server reads metadata and content, fills the cache with a TTL not exceeding the expiry, and returns the text. Expired pastes return 410.}}

## Caching, expiry and cleanup {#sec-pb-expiry}

**Caching.** Reads are 10× writes, and popularity is skewed (a paste shared on social media gets thousands of views). Use **cache-aside** (Chapter {ch:ch-cache}): key `paste:{code}`, value metadata plus content for small pastes, TTL = min(1 hour, time until expiry). Pastes are **immutable**, so staleness is a non-issue except for deletion and expiry, which are handled by explicit invalidation and by checking `expires_at` on the cached object. At 40 reads per second the cache is a convenience; at 4,000 it is essential. A **CDN** in front can take most traffic if responses carry `Cache-Control`.

**Expiry.** Two mechanisms together. **Lazy expiry**: on each read, check `expires_at`; if past, return 410 and (optionally) enqueue a delete. **Batch cleanup**: a scheduled job scans the `expires_at` index for rows older than now, deletes the object-store content and the row, in small batches to avoid long locks. Lazy expiry gives correctness; the batch job reclaims space. Retention of deleted data for privacy deadlines (Chapter {ch:ch-security}) must also cover backups and caches.

**Analytics (monthly visits per link).** Do not update a counter on every read (a hot row that would serialise writers). Instead, **log each hit** (short code, timestamp) to a stream, and aggregate with a batch or streaming job (a MapReduce-style job in the notebook): *map* each log line to `(code, 1)`, *reduce* by summing per code and month, then write results to an analytics table. Reads of the stats endpoint come from that table. The cost is that stats lag by minutes to hours, which is acceptable.

```python
# map: emit one count per hit    reduce: sum per (code, month)
def map_line(line):
    ts, code = parse(line)
    yield ((code, month_of(ts)), 1)
def reduce_key(key, counts):
    yield (key, sum(counts))
```

## Scaling and bottlenecks {#sec-pb-scale2}

At ten times the numbers (400 reads per second, 40 writes) almost nothing changes: add application servers and cache nodes. At a hundred times (4,000 reads, 400 writes per second):

1. **Database reads**: handled by the cache (a 95% hit ratio leaves 200 reads per second) and read replicas.
2. **Database writes**: 400 per second is within one primary's capacity; if it is not, shard by `short_code` hash. The **key service** is sharded the same way.
3. **Storage**: 450 GB grows to 45 TB over three years at 100×, which belongs in an object store with lifecycle rules (move old pastes to cheaper tiers).
4. **Hot pastes**: a viral link is served from the CDN and cache; popular keys can also be replicated across cache nodes.
5. **Multi-region**: replicate the read path (CDN, cache, read replicas) near users; keep writes in one region unless latency demands otherwise.

## Failure handling, security and operations {#sec-pb-ops}

**Failure handling.** Cache down: reads fall through to the database (protect it with rate limiting and request coalescing). Database primary fails: promote a replica; reads continue from the cache and replicas meanwhile, so *reads degrade less than writes*. Object store unavailable: serve cached content, return 503 for the rest. Key service unavailable: application servers have a batch in memory; also fall back to the hash-and-retry method. Duplicate create due to retries: idempotency key.

**Security and abuse.** Pastebin-style sites are heavily abused: spam, phishing links hidden behind shorteners, malware distribution, leaked credentials, illegal content. Controls: **rate limit** creates per IP and per account (Chapter {ch:ch-entry}); size limits; **scan** content and destination URLs against reputation services, and allow takedown by report; **preview pages** for suspicious redirects; **long, random codes** for private pastes (never sequential); **authorisation** for private pastes and deletion; do not execute or render user content as HTML (serve as `text/plain` with `X-Content-Type-Options: nosniff` and a restrictive Content Security Policy to prevent cross-site scripting); and log access for audit.

**Monitoring and cost.** Track create and read rates, error rates, cache hit ratio, p95 latency, expiry backlog, key-service reserve, storage growth, and the abuse reports. Cost at 100×: object storage dominates (45 TB × about $0.02 per GB-month ≈ $900 per month), then egress, then a small database and cache fleet; a CDN lowers egress cost. Alert on key pool running low and on the ratio of 5xx errors.

## Alternatives and trade-offs {#sec-pb-alt}

Table[pb-alt]: Alternatives considered.

| Decision | Chosen | Alternative | Why chosen | When to switch |
|---|---|---|---|---|
| Metadata store | SQL with a primary key on the code | Key-value or document store | Simple, familiar, transactions | Very high scale or low operational budget |
| Key generation | Pre-generated random keys | Hash + retry; counter + Base62 | Unguessable, no hot-path collisions | Small system: hash + retry |
| Content storage | Object store | Inline in the database | Cheap, scalable, small rows | Tiny pastes: inline |
| Analytics | Log and batch aggregate | Per-read counter | No hot row | Need real-time counts: streaming aggregation |
| Redirect code | 302 | 301 | Counts every click | Static links where SEO and caching matter |

**Follow-up questions to expect.** *Custom aliases?* Separate namespace with a uniqueness check. *Delete a link permanently, including from caches and CDN?* Purge calls plus short TTL for private pastes. *User accounts and history?* Add a `users` table and an index by `(owner_id, created_at)`. *Multi-region active-active writes?* Region-prefixed keys avoid collisions; handle deletes with a region-aware protocol. *What if reads are 1,000× writes?* Lean entirely on the CDN. *Reduce guessability of public links?* Longer codes (8+ characters) or scrambling.

::: failure
**Failure modes (summary).** Hash collisions causing silent overwrites if the unique constraint is missing; key service outage; hot paste overloading one cache node; expiry job running behind and filling storage; orphaned objects after partial failures; abuse flooding creates; redirect to a malicious destination; cached content outliving a takedown.
:::

::: misconception
- *"The hard part is scale."* Here the load is small; the hard parts are keys, expiry, abuse and operations.
- *"MD5 is fine for the key because it is a hash."* Truncation makes collisions certain at scale; MD5 is also not for security uses.
- *"A 301 is always better because it is cacheable."* It hides repeat visits from analytics and cannot be changed once cached.
- *"Store everything in the database for simplicity."* Large blobs bloat the database; split content out when sizes grow.
:::

::: interview
**Q1. How do you generate unique short codes?**
Compare hashing with retry, counter plus Base62 (with id blocks and scrambling), and pre-generated keys; justify by collisions, guessability, hot-path cost and failure risk; give the key-space arithmetic.

**Q2. How would you handle expired pastes?**
Lazy check on read plus a batch cleanup job over an index on expiry; return 410; remove content from the object store and caches; mind backups for privacy.

**Q3. How do you count visits without a hot row?**
Log hits to a stream and aggregate in batch or streaming jobs; serve statistics from the aggregate table.

**Q4. What breaks first at 100× scale?**
Not the database (cache and replicas), but operations: storage lifecycle, abuse control and the key service, then global latency; add a CDN and sharding as needed.
:::

::: exercise
1. Recompute the key-space needed if the service must hold 5 billion links with a collision probability under 1 in 100,000 per new key. How many Base62 characters are required?
2. Describe what happens if the application server crashes after writing content but before the metadata row, and after the metadata row but before returning the response.
3. Design the cleanup job: query, batch size, and how you avoid overloading the database.
4. A paste goes viral: 20,000 requests per second for one code. List the layers that absorb it and what could still fail.

**Answers.**
1. Collision probability ≈ n / N < 10⁻⁵ with n = 5 × 10⁹ requires N > 5 × 10¹⁴. 62⁸ ≈ 2.18 × 10¹⁴ is just short; 62⁹ ≈ 1.35 × 10¹⁶ suffices, so 9 characters (or use pre-generated keys that never collide, where 8 characters would still do).
2. After content but before metadata: an orphaned object, collected later by a sweeper that compares keys. After metadata but before the response: the paste exists; the client times out and retries with the same idempotency key, receiving the existing link.
3. `SELECT short_code, content_key FROM pastes WHERE expires_at < now() ORDER BY expires_at LIMIT 500;` delete objects then rows, commit, sleep briefly, repeat; run off-peak, throttle on database load, and make deletes idempotent so reruns are safe.
4. The CDN (cached, immutable), then the distributed cache, then in-process caches; the hot key could still saturate one cache node, so replicate or add a local cache; the object store handles reads on misses but at a cost; protect the origin with request coalescing.
:::

::: summary
- Scale here is small; the interesting design is in key generation, storage separation, expiry, analytics and abuse.
- Separate metadata (SQL, key = short code) from content (object store); write content first.
- Choose among hash-and-retry, counter, and pre-generated keys by collision rate, guessability and failure modes.
- Cache aggressively (immutable data), expire lazily and in batches, aggregate analytics from logs.
- Plan for abuse, failure and growth, and state the trade-offs.
:::

::: revision
- [ ] I can derive writes per second, storage and key length from the assumptions.
- [ ] I can compare three key-generation methods.
- [ ] I can trace create and read paths and the failure of each step.
- [ ] I can explain expiry, analytics and abuse controls.
:::

::: supplement
**Further reading.** The original System Design Primer's solution for this problem; Alex Xu, *System Design Interview*, chapter on URL shorteners; engineering write-ups on key generation services (for example, Twitter's Snowflake id scheme for time-ordered unique ids).
:::
