%derived Notebook chapter 15 (real-world architectures: the 17 systems of the primer's table, the 23 company architecture themes, and the list of engineering blogs)
%added a method for reading architecture write-ups, a pattern-to-chapter map, and reading questions for each system
# Reading Real-World Architectures {#ch-realworld}

::: objectives
After this chapter you can:

- read an architecture write-up by extracting requirements, components, patterns and trade-offs instead of memorising stacks;
- place each well-known system in the patterns taught in this book;
- choose which engineering write-ups to read for a given interview or project.
:::

::: prereq
Parts III to V of this book. Descriptions here are deliberately high-level and reflect public papers and write-ups as the notebook lists them; internals change, so check current sources before relying on a detail.
:::

## A method for reading {#sec-rw-method}

The notebook's advice is not to memorise nitty-gritty details but to find the **shared principles**, what problem each component solves, where it works and where it does not, and the lessons learned. Use this routine on any write-up:

1. **Requirements first.** What load, data size, latency and consistency did the authors need? A design is only good *for* a requirement.
2. **Draw the request path** (Chapter {ch:ch-intro}). Circle every box and write the problem it solves.
3. **Name the pattern:** cache, queue, partitioning, replication, log, consensus, batch or stream.
4. **Find the trade-off:** what did they give up (consistency, flexibility, operational simplicity, cost)?
5. **Ask what changed:** most architectures are scars from earlier failures or growth stages (compare Chapter {ch:ch-aws}).
6. **Check the date.** A 2010 post may describe a stack since replaced.

{{fig rw-skeleton | Most large-company diagrams are this skeleton with different brand names on each box.}}

## The seventeen systems in the notebook's table {#sec-rw-systems}

Table[rw-systems]: Systems, what they are, the pattern they teach and the trade-off.

| System (origin) | What it is | Pattern it teaches | Trade-off or when to use | Book chapter |
|---|---|---|---|---|
| MapReduce (Google) | Distributed batch processing: map, shuffle, reduce | Move computation to data; parallel batch | High latency; good for logs and rankings | {ch:ch-salesrank} |
| Spark | Batch processing keeping working sets in memory | Reuse data in RAM between stages | Needs memory; faster for iterative jobs | {ch:ch-salesrank} |
| Storm | Stream processing of events as they arrive | Low-latency continuous computation | More complex than batch | {ch:ch-async} |
| Bigtable (Google) | Wide-column store with sorted keys | Huge sparse tables, range scans | Weak ad-hoc querying | {ch:ch-nosql} |
| HBase | Open-source Bigtable-style store on HDFS | Same, in the Hadoop ecosystem | Operational weight | {ch:ch-nosql} |
| Cassandra (Facebook) | Wide-column, highly available, tunable consistency | Replication with quorums, AP bias | Model queries up front | {ch:ch-distdata} |
| DynamoDB (Amazon) | Managed key-value and document store | Scale without running servers | Access patterns fixed in advance | {ch:ch-nosql} |
| MongoDB | Document store | Flexible schema, rich document queries | Limited joins and cross-document transactions | {ch:ch-nosql} |
| Spanner (Google) | Globally distributed relational database | Strong consistency across regions using synchronised clocks and consensus | Cost and write latency | {ch:ch-consensus} |
| Memcached | Distributed memory cache | Cache-aside, simple and fast | No persistence; weak consistency | {ch:ch-cache} |
| Redis | Cache plus data structures plus persistence options | Sorted sets, queues, counters | Memory-bound; single-node limits | {ch:ch-cache} |
| GFS (Google) | Distributed file system | Large files as replicated chunks | Poor for tiny files and low latency | {ch:ch-distdata} |
| HDFS | Open-source GFS-style file system | Same, in Hadoop | Same | {ch:ch-distdata} |
| Chubby (Google) | Lock and coordination service | Consensus for small critical data, leader election | Becomes a critical dependency | {ch:ch-consensus} |
| Dapper (Google) | Distributed tracing | Follow one request across services | Needs instrumentation and sampling | {ch:ch-observability} |
| Kafka (LinkedIn) | Publish-subscribe message log | Durable ordered log decoupling producers and consumers | Operational complexity | {ch:ch-async} |
| ZooKeeper | Coordination, configuration, naming | Consensus for small shared state | Not a general database | {ch:ch-consensus} |

**Reading questions.** For MapReduce: what happens if one mapper is slow (straggler)? For Cassandra: what do `R + W > N` settings give you? For Spanner: why does it wait out clock uncertainty before committing? For Kafka: what is a consumer offset and why does it enable replay? For Chubby: why must clients tolerate losing a lock?

## Company architectures: what to look for {#sec-rw-companies}

The notebook links one or more write-ups per company. Instead of learning each stack, read each with a question in mind. The right column is the pattern *expected* from the notebook's title for that write-up; verify it against the article itself.

Table[rw-companies]: Company themes and the pattern to look for.

| Company (theme listed in the notebook) | Pattern to look for | Chapter |
|---|---|---|
| Amazon | Service-oriented decomposition with independent teams and APIs | {ch:ch-microservices} |
| Cinchcast (1,500 hours of audio per day) | Media pipeline with queues and workers | {ch:ch-async} |
| DataSift (120,000 tweets per second) | Stream ingest, partitioning and real-time filtering | {ch:ch-async} |
| Dropbox | Metadata versus bulk storage; sync protocol | {ch:ch-practice} |
| ESPN (100,000 events per second) | Absorbing spiky read traffic with caching and edge | {ch:ch-cache} |
| Google | Commodity clusters with a file system, batch and table store | {ch:ch-distdata} |
| Instagram | Photo storage, sharded metadata, caching | {ch:ch-scaling-sql} |
| Justin.tv (live video) | Ingest, transcode, distribute | {ch:ch-entry} |
| Facebook (caching, social graph store, photos, live video) | Cache layers over databases and a purpose-built graph store | {ch:ch-socialgraph} |
| Flickr | Sharding and caching for a photo service | {ch:ch-scaling-sql} |
| Mailbox (0 to 1 million users in 6 weeks) | Scaling under surprise growth; back pressure and elasticity | {ch:ch-aws} |
| Netflix (the whole stack; pressing play) | Microservices, resilience, CDN for video | {ch:ch-resilience} |
| Pinterest (billions of page views) | Growth stages: caching, then sharding | {ch:ch-aws} |
| Playfish (50 million monthly users) | Game back end scaling with stateless servers | {ch:ch-aws} |
| PlentyOfFish | How far a lean setup can go with caching | {ch:ch-cache} |
| Salesforce (1.3 billion transactions per day) | Multi-tenant relational architecture at scale | {ch:ch-scaling-sql} |
| Stack Overflow | Vertical scaling plus caching can go far | {ch:ch-intro} |
| TripAdvisor (30 TB, 200 million dynamic views) | Caching dynamic pages; data growth | {ch:ch-cache} |
| Tumblr (15 billion page views per month) | Fan-out of posts to follower dashboards | {ch:ch-twitter} |
| Twitter (timelines, 250 million tweets per day, firehose) | Fan-out on write, storage, big and small data | {ch:ch-twitter} |
| Uber (real-time marketplace; many services) | Real-time geo-matching; microservice sprawl lessons | {ch:ch-microservices} |
| WhatsApp | Connection-heavy messaging run by a small team | {ch:ch-practice} |
| YouTube | Video storage and serving; thumbnails and caching | {ch:ch-entry} |

The figures in parentheses are the titles the notebook gives for the linked articles; they are historical and are not claims about today's scale.

## Engineering blogs worth following {#sec-rw-blogs}

Interview questions often come from the interviewing company's own domain, so read that company's engineering blog first. The notebook lists, among others: Airbnb, Atlassian, AWS, Bitly, Box, Cloudera, Dropbox, Quora, eBay, Evernote, Etsy, Facebook, Flickr, Foursquare, GitHub, Google Research, Groupon, Heroku, HubSpot, High Scalability, Instagram, Intel Software, Jane Street, LinkedIn, Microsoft, Netflix, PayPal, Pinterest, Reddit, Salesforce, Slack, Spotify, Stripe, Twilio, Twitter, Uber, Yahoo, Yelp and Zynga, and points to a larger community list (the *engineering-blogs* repository by *kilimchoi*). The links were not re-verified for this book; search for the current blog address of each.

::: worked
**Reading exercise: Kafka.** Requirements: ingest very high volumes of events and let many consumers read them independently and replay. Request path: producers append to a partitioned log; brokers replicate partitions; consumers track an offset per partition. Pattern: durable log decoupling producers and consumers (Chapter {ch:ch-async}). Trade-off: ordering is only per partition, and consumers must handle duplicates (at-least-once). Date check: the broker's coordination layer has changed over versions, so verify against current documentation.
:::

::: misconception
- *"I must know every company's stack."* Know the patterns; stacks change.
- *"A famous architecture is the right architecture for me."* It fits their requirements and scale.
:::

::: interview
**Q1. Which real system would you cite for leader election and why?** A coordination service built on consensus (Chubby or ZooKeeper), because small critical state needs strong consistency; also state its cost as a critical dependency.

**Q2. What does Cassandra teach about consistency?** Tunable quorums: with replication factor *N*, choosing read and write counts so that *R + W > N* gives overlapping quorums; lower settings trade consistency for latency and availability.
:::

::: exercise
1. Choose one write-up from the notebook's list and fill the six steps of the reading method in one page.
2. Map three systems from Table {tab:rw-systems} to the CAP and PACELC trade-off they exemplify (use Chapter {ch:ch-distdata}).
3. Explain why Spark was created as an improvement on MapReduce for iterative jobs.

**Answers.**
1. A good page lists requirements with numbers, a labelled request path, patterns, at least one trade-off and a date check.
2. For example (hedged, per public descriptions): Cassandra leans to availability with tunable consistency; Spanner favours consistency, paying latency; DynamoDB offers a choice per read between eventual and strong consistency.
3. MapReduce writes intermediate results to disk between stages; Spark keeps working sets in memory, so iterative algorithms avoid repeated disk reads.
:::

::: summary
- Read architectures for requirements, patterns and trade-offs, not for brand names.
- The seventeen systems map onto a small set of patterns taught in this book.
- Company write-ups are dated; verify before relying on them.
:::

::: revision
- [ ] I can apply the six-step reading method.
- [ ] I can map each listed system to a pattern and a chapter.
:::
