%derived Notebook chapter 7 (what NoSQL is, BASE, the four families, data that fits NoSQL, SQL or NoSQL tables)
%added query-first data modelling, embedding versus referencing, secondary indexes, tunable consistency, polyglot persistence, search and time-series stores
# NoSQL and Choosing a Database {#ch-nosql}

::: objectives
After this chapter you can:

- explain what "NoSQL" covers and why such stores appeared;
- describe the four main families (key-value, document, wide-column, graph) with data model, strengths and typical uses;
- model data starting from the queries rather than from entities, and decide between embedding and referencing;
- explain BASE and tunable consistency without oversimplifying SQL versus NoSQL;
- choose a database for a given workload and justify the choice.
:::

::: prereq
Chapter {ch:ch-sql} and Chapter {ch:ch-scaling-sql}; Chapter {ch:ch-ds} for LSM trees.
:::

::: terms
NoSQL
: "Not only SQL": a broad label for databases that do not use the relational table model or full SQL, usually trading some relational features for scale, flexibility or speed.

BASE
: *Basically Available, Soft state, Eventual consistency*: a design stance contrasted with ACID.

Document
: A self-contained, nested record (commonly JSON) stored and retrieved as a unit.

Wide-column store
: A store whose rows hold sparse, dynamically named columns grouped into column families, partitioned by row key.

Access pattern
: A specific query your application will make repeatedly; NoSQL modelling begins here.

Eventual consistency
: If no new writes arrive, all replicas will eventually hold the same value.
:::

## What NoSQL is, and why it appeared {#sec-nosqlwhy}

By the late 2000s, companies running very large web services hit limits of single-node relational databases: write volumes too high for one machine, data too large to join, schemas that changed weekly, and global users demanding local latency. Several systems were built to scale out first and offer fewer features: simple data models, no or limited joins, relaxed consistency, and automatic distribution across many commodity machines. "NoSQL" is the umbrella name. It is not one technology: a key-value cache, a document store and a graph database share little except that they are not relational.

The right question is never "SQL or NoSQL?" but "**what are my access patterns, my scale, my consistency needs and my team's skills?**" Many NoSQL systems now offer transactions and SQL-like languages, and many relational systems offer JSON columns and horizontal scaling, so the lines blur.

::: note
**Clarification on BASE.** The notebook summarises NoSQL as BASE: *basically available* (the system answers even during partial failure), *soft state* (data may change over time even without input, as replicas converge), *eventual consistency*. This is a useful design stance, not a rule that every NoSQL database is inconsistent: many offer strong consistency options, and some (for example single-leader document stores) are strongly consistent by default. Conversely, a replicated relational database with lagging followers also gives eventual consistency on reads. Treat "consistency model" as a property to check per system and per operation, not per category.
:::

## The four families {#sec-families}

{{fig families | The four main NoSQL families, from simplest to richest relationships: key-value, document, wide-column and graph.}}

### Key-value stores

The simplest model: a giant dictionary. Operations are `get(key)`, `put(key, value)` and `delete(key)`; the value is an opaque blob. Because the system never looks inside values, it can partition by key and replicate very simply, giving high throughput and low latency, often in memory (Redis, Memcached) or on SSD (DynamoDB in its basic mode, Riak). Typical uses: caches, sessions, shopping carts, feature flags, counters, rate limiting. Limits: no queries by value, no relationships; you must know the key.

### Document stores

A document store holds self-describing, nested records, usually JSON or similar (MongoDB, CouchDB, Firestore, DynamoDB in document mode). Each document can have a different shape. The database understands the structure, so it can index inside documents and query fields.

```json
{ "_id": "order-9131",
  "customer": {"id": 42, "name": "Asha"},
  "items": [ {"sku": "A1", "qty": 2, "price": 9.99},
             {"sku": "B7", "qty": 1, "price": 24.00} ],
  "status": "shipped" }
```

Strengths: a whole business object is read or written in one operation (locality), flexible schema, natural fit for object-oriented code, easy evolution. Limits: joins across documents are limited or manual; duplicated data must be kept consistent by the application; large unbounded documents (an ever-growing `items` list) cause problems. Uses: content management, catalogues, user profiles, event and order records.

### Wide-column stores

Rows are identified by a **row key**, which determines the partition; within a row, data is grouped into **column families**, and different rows may have different columns (Cassandra, HBase, Bigtable). Data within a partition is stored **sorted by a clustering key**, so range scans within a partition are fast. They are built on LSM trees (Chapter {ch:ch-ds}) for high write throughput.

Think of it as a *map of sorted maps*: `rowkey -> (column -> value)`, optimised for enormous volumes distributed over many nodes. Strengths: very high write rates, linear scale-out, tunable consistency, good for time-ordered data. Limits: you can efficiently query only by the partition key (and clustering order), so each query shape needs its own table; no joins; limited ad-hoc queries; careful modelling essential. Uses: time series, event logs, messaging, activity feeds, sensor data, analytics ingestion.

### Graph databases

Data is **nodes** (entities) and **edges** (relationships), each with properties (Neo4j, Amazon Neptune). The key advantage: following relationships is *cheap and does not slow down as the total dataset grows*, because the engine hops along stored edges instead of performing a join that searches an index at every hop. Questions like "friends of friends who like this film" or "shortest path" are natural; in SQL they need many self-joins whose cost multiplies with depth. Limits: harder to shard (a graph is highly connected, so cutting it across machines cuts many edges), smaller ecosystems, not suited to bulk aggregations. Uses: social networks, recommendations, fraud rings, knowledge graphs, network topology.

Table[families]: The four families compared.

| Family | Data model | Strengths | Weak spots | Examples |
|---|---|---|---|---|
| Key-value | key to opaque value | Speed, simplicity, easy sharding | No queries by value or relationships | Redis, Memcached, DynamoDB, Riak |
| Document | key to nested document | Flexible schema, object locality, field indexes | Weak cross-document joins; duplication | MongoDB, CouchDB, Firestore |
| Wide-column | row key, sorted columns | Huge write throughput, scale-out | Query-first modelling; no joins | Cassandra, HBase, Bigtable |
| Graph | nodes, edges, properties | Cheap relationship traversal | Hard to shard; niche | Neo4j, Neptune |

## Modelling for NoSQL: queries first {#sec-nosqlmodel}

Relational modelling starts from *entities and normalisation*, then queries are derived by joins. NoSQL modelling reverses the order: **list the access patterns first**, then shape the data so each is answered by one lookup in one partition.

### Embedding versus referencing

In a document store you choose whether related data lives *inside* the parent document (embedding) or in a separate document reached by id (referencing).

Table[embedref]: Embed or reference?

| Embed when | Reference when |
|---|---|
| The child is always read with the parent | The child is read or updated independently |
| The child list is small and bounded | The child list is large or unbounded |
| Children belong to one parent only | Children are shared by many parents |
| Atomic update of both is needed | The child data changes often and would require updating many copies |

::: worked
**Modelling a timeline for a wide-column store.** Access pattern: "show the 50 most recent posts from the accounts I follow". In a relational model you would join `follows` and `posts` at read time, which is slow at scale. In a wide-column model you instead **precompute** a table keyed for the read:

```text
table home_timeline
  partition key : user_id          -- one partition per reader
  clustering key: post_time DESC   -- newest first inside the partition
  columns       : post_id, author_id, snippet

read:   SELECT * FROM home_timeline WHERE user_id = 42 LIMIT 50;   -- one partition
write:  for each follower f of author a: INSERT INTO home_timeline (f, now, post_id, a, snippet)
```

Reading is one partition lookup, fast at any scale. The cost moved to *write time* (one insert per follower, called fan-out) and to **duplication** (the snippet is stored many times). This is the central NoSQL trade: *pay on write, duplicate data, so reads are trivial.* Chapter {ch:ch-twitter} develops this design.
:::

### Secondary indexes and consistency knobs

Querying by something other than the primary key (find users by email) needs a **secondary index**. In distributed stores these are costly: a **local** index (each shard indexes its own rows) requires a scatter-gather query across all shards; a **global** index (partitioned by the indexed value) makes reads cheap but writes touch two partitions and often update asynchronously, so the index can briefly lag. Many designs simply maintain a second table keyed by the alternate attribute.

Many distributed stores let you tune consistency **per operation** using **quorums**: with *N* replicas, writes wait for *W* acknowledgements and reads query *R* replicas; if **R + W > N**, every read overlaps the latest write and sees it (assuming no failures at the wrong moment). Chapter {ch:ch-distdata} explains this carefully, including why it is *not* a guarantee of linearizability.

## SQL or NoSQL? {#sec-sqlornosql}

Table[sqlnosql]: Reasons to prefer each (from the notebook, with qualifications).

| Prefer a relational database when | Prefer NoSQL when |
|---|---|
| Data is structured and relationships matter | Data is semi-structured, nested or schema changes often |
| You need ACID transactions across rows or tables | You can accept eventual consistency or single-document atomicity |
| You need flexible ad-hoc queries and joins | Access patterns are known and few |
| Scaling needs are moderate, or can be met with replicas and sharding | You need very high write throughput or global distribution |
| The team knows SQL and the ecosystem matters | Data is naturally key-based, time-ordered or graph-shaped |

Examples of data that fits NoSQL particularly well (notebook): rapid ingestion of clickstream and logs; leaderboard and scoring data; temporary data such as a shopping cart; frequently accessed "hot" tables; metadata and lookup tables. Real systems use **polyglot persistence**: several stores, each for what it does best (relational for orders and payments, key-value cache for sessions, search index for text, wide-column for the event firehose). The cost is operational: each store must be run, secured, backed up and kept in sync (often through events, Chapter {ch:ch-async}).

::: supplement
**Two more store types worth knowing.** *Search engines* (Elasticsearch, OpenSearch, Solr) build an **inverted index** (word → list of documents) for full-text search, ranking and faceting; use them as a *derived* copy of data whose source of truth lives elsewhere. *Time-series databases* (InfluxDB, TimescaleDB, Prometheus) optimise for append-only timestamped measurements with compression, downsampling and retention policies. *NewSQL* systems (for example Spanner, CockroachDB) aim to offer SQL and ACID transactions with horizontal scale, at the cost of cross-node coordination latency.
:::

::: warning
**Common mistakes.** Choosing NoSQL "because it scales" without a scale problem. Choosing a schemaless store and then never writing down the schema (it still exists, in your code, undocumented). Modelling a NoSQL store like a relational one, then discovering that queries require scans. Unbounded arrays inside documents. Using a cache or key-value store as the only copy of important data.
:::

::: failure
**Failure modes.** Hot partitions from skewed keys (one celebrity key receives most traffic); partitions that grow without bound (a time-series partition per device per forever); read repair and compaction storms degrading latency; stale reads from relaxed consistency interpreted as bugs; lost updates from last-write-wins conflict resolution; schema drift producing documents that old code cannot read; backups of eventually consistent stores that capture an inconsistent snapshot.
:::

::: misconception
- *"NoSQL is faster than SQL."* It is faster at what it was designed for, with the features it dropped; a well-indexed relational query can beat a badly modelled NoSQL scan.
- *"NoSQL has no schema."* It has an implicit schema enforced by application code; "schema-on-read" moves the discipline, it does not remove it.
- *"NoSQL means no transactions and no consistency."* Many offer tunable or strong consistency and limited transactions.
- *"You must pick one database for the whole system."* Polyglot persistence is normal.
:::

::: interview
**Q1. When would you choose a document store over a relational database?**
When the data is naturally nested and read as a unit, the schema evolves quickly, and cross-record joins and multi-record transactions are rare; also when horizontal scaling by document key is needed.

**Q2. Why is Cassandra good at writes?**
It uses an LSM-tree design: writes append to a commit log and an in-memory table and flush as sequential immutable files, avoiding random disk writes; data is partitioned by key across many nodes with no single leader.

**Q3. How do you model "recent posts of people I follow" in NoSQL?**
Precompute a per-reader timeline keyed by user and ordered by time (fan-out on write), accept duplication, and handle very popular authors by pulling their posts at read time instead.

**Q4. SQL versus NoSQL: how do you decide?**
By access patterns, scale, consistency requirements, flexibility and team skills; default to relational and move specific workloads to NoSQL when a concrete limit requires it.
:::

::: exercise
1. Model an e-commerce order as a document, and decide whether product details should be embedded in each order item or referenced. Justify your decision.
2. You need to answer "all events for device D between two times" and "latest reading for every device". Propose a wide-column table design for each query.
3. A social app needs "mutual friends of A and B" and "shortest path between A and B". Which family and why?
4. Replicas = 5. What do R and W need to be so that reads see the latest write with R + W > N, and what trade-off does choosing W = 5 bring?

**Answers.**
1. Embed a *snapshot* of product name and price at purchase time (it should not change when the catalogue changes), plus the `sku` reference for lookup: embedding the snapshot is correct because an order is a historical record read as one unit.
2. Query 1: partition key `device_id` (plus a time bucket such as the day to bound partition size), clustering key `timestamp`. Query 2: a separate table `latest_by_device` keyed by `device_id` containing one row updated on each reading.
3. A graph database: relationship traversals (common neighbours, shortest path) are natural and fast without multi-way joins.
4. For example W = 3, R = 3 (3 + 3 > 5). W = 5 makes writes wait for all replicas: reads can use R = 1, but any single replica failure blocks writes, reducing write availability.
:::

::: summary
- NoSQL is a family of scale-oriented stores with simpler models; judge each by access patterns, consistency options and operations, not by label.
- Key-value: speed and simplicity. Document: nested records and flexible schema. Wide-column: massive writes, query-first modelling. Graph: cheap relationship traversal.
- Model from the queries; embed what is read together and bounded; duplicate on write so reads are one lookup.
- Tunable consistency uses quorums (R + W > N); secondary indexes cost extra.
- Use relational by default; add specialised stores for specific needs, accepting operational cost.
:::

::: revision
- [ ] I can describe each family and give an example and a use.
- [ ] I can model a query-first table or document.
- [ ] I can explain embed versus reference.
- [ ] I can state the quorum rule R + W > N.
- [ ] I can justify SQL or NoSQL for a workload.
:::

::: supplement
**Further reading.** Kleppmann, *Designing Data-Intensive Applications*, chapters 2 and 3; the DynamoDB and Cassandra data-modelling guides from their vendors; Pat Helland, "Life beyond Distributed Transactions"; the original Bigtable (2006) and Dynamo (2007) papers.
:::
