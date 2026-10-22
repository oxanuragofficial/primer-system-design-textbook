%derived Notebook chapter 10 (Capacity and back-of-the-envelope: powers of two, latency numbers, turning traffic into numbers, the URL-shortener worked example) and the "numbers and formulas to remember" sheet
%added availability and cost arithmetic, bandwidth and storage planning, headroom, and sensitivity analysis
# Estimation and Capacity Planning {#ch-estimation}

::: objectives
After this chapter you can:

- produce order-of-magnitude estimates of requests per second, storage, bandwidth and memory in a few minutes;
- use powers of two and the standard latency numbers to reason about where time goes;
- convert availability percentages into allowed downtime and combine components in series and in parallel;
- state assumptions and units explicitly, and test how sensitive an answer is to them.
:::

::: prereq
Chapter {ch:ch-intro} (requests, latency, throughput). Arithmetic with powers of ten is enough.
:::

::: terms
Back-of-the-envelope estimate
: A rough calculation done quickly, accurate to within a factor of about two to ten, used to choose between designs.

RPS / QPS
: Requests (or queries) per second.

Peak factor
: How much higher the busiest moment is than the average; commonly 2 to 10 times.

Headroom
: Spare capacity kept above expected peak so bursts and failures do not cause overload.

Nines
: Shorthand for availability: "three nines" means 99.9%.
:::

## Why we estimate {#sec-whyest}

Design choices depend on scale, and scale is rarely given as the number you need. "A million users" does not tell you whether to use one database or fifty. An estimate converts a vague number into **requests per second, bytes stored and bytes moved**, and those decide whether a single machine suffices, whether caching is essential, and whether the data fits in memory.

Estimates are for *choosing between designs and spotting impossible ones*, not for predicting a bill. Aim for the right power of ten. State every assumption aloud, label every unit, and say that the numbers are assumptions, not measurements. If one assumption dominates the answer, say so: that is the number to go and measure.

## Powers of two and units {#sec-pow2}

Storage and memory sizes are powers of two. You only need a handful by heart.

Table[pow2]: Powers of two worth memorising.

| Power | Exact value | Approximate | Name |
|---|---|---|---|
| 2¹⁰ | 1,024 | one thousand | 1 KB (kilobyte) |
| 2²⁰ | 1,048,576 | one million | 1 MB (megabyte) |
| 2³⁰ | 1,073,741,824 | one billion | 1 GB (gigabyte) |
| 2⁴⁰ | 1,099,511,627,776 | one trillion | 1 TB (terabyte) |
| 2⁸ / 2¹⁶ / 2³² | 256 / 65,536 / 4,294,967,296 | | one byte / two bytes / 32-bit limit |

Each step of ten bits multiplies by about a thousand. Two rules help: **1 character is about 1 byte** in plain English text (more in some encodings), and **a day has about 86,400 seconds, roughly 10⁵**. A month has about 2.5 million seconds (2.5 × 10⁶).

## Latency numbers worth knowing {#sec-latnum}

Where does time go? The numbers below are rough orders of magnitude for typical hardware; absolute values change with every hardware generation, but the *ratios* have stayed remarkably stable and are what matter.

Table[latnum]: Approximate latencies (orders of magnitude; follow the notebook's table).

| Operation | Time | Feels like |
|---|---|---|
| L1 cache reference | 0.5 ns | one heartbeat of a CPU |
| Main-memory reference | 100 ns | 200 × L1 |
| Compress 1 KB | 10 µs | |
| Send 1 KB over 1 Gbps network | 10 µs | |
| Read 4 KB randomly from SSD | 150 µs | 1,500 × memory |
| Read 1 MB sequentially from memory | 250 µs | |
| Round trip within the same data centre | 500 µs | |
| Read 1 MB sequentially from SSD | 1 ms | 4 × memory |
| Disk seek (spinning disk) | 10 ms | 20 × data-centre round trip |
| Read 1 MB sequentially from disk | 30 ms | 120 × memory |
| Send packet California to Netherlands and back | 150 ms | |

{{fig latency-ladder | The latency ladder on a logarithmic scale. Each tick is ten times the previous one; the whole chart spans eight orders of magnitude, from a CPU cache hit to an intercontinental round trip.}}

From these numbers come the most useful rules of thumb:

- Memory is fast, disk seeks are slow: avoid random disk reads on the request path; cache hot data in RAM.
- Sequential reads are far cheaper than random ones: append-only logs and sorted files beat scattered updates (Chapter {ch:ch-ds}).
- Compress data before sending it over a long-distance link when CPU is cheaper than bandwidth.
- Network round trips dominate: a design that makes ten sequential calls across data centres costs more than 1.5 seconds of pure propagation. Prefer fewer, larger calls and keep related data close together.
- Cross-continent calls cost about 150 ms: replicate data or use a CDN to serve users locally.

## Turning traffic into numbers {#sec-traffic}

### Requests per second

Start from users and behaviour. **Daily active users (DAU)** times *actions per user per day* gives requests per day; divide by 86,400 for the average per second; then multiply by a peak factor.

::: worked
**Estimate a messaging feature.** Assume 10 million daily active users, each sending 20 messages and reading 200 per day.

- Writes per day = 10 × 10⁶ × 20 = 2 × 10⁸. Per second = 2 × 10⁸ / 10⁵ ≈ 2,000 writes per second on average.
- Reads per day = 10 × 10⁶ × 200 = 2 × 10⁹, about 20,000 reads per second on average.
- Assume peak is 5 × average: about 10,000 writes/s and 100,000 reads/s at peak.
- Read : write ratio is 10 : 1, so caching reads will help a lot.

One database node typically handles low thousands to tens of thousands of simple operations per second (depending on hardware and queries, so measure it). So 100,000 reads/s at peak needs caching and replicas, and 10,000 writes/s needs a careful look at the write path. The estimate has already told us the shape of the design.
:::

### Storage

Storage = (items per day) × (bytes per item) × (days retained), multiplied by a **replication factor** (commonly 3 copies) and a safety margin for indexes and overhead (often 1.5 to 2 times).

::: worked
**Storage for the same messages.** 2 × 10⁸ messages per day at 200 bytes each = 4 × 10¹⁰ bytes = 40 GB per day. Over five years (1,825 days) = 73 TB. Three replicas = 219 TB. Add 50% for indexes and overhead: about 330 TB. That does not fit in one machine; it implies sharding (Chapter {ch:ch-scaling-sql}) or a store built for large volumes (Chapter {ch:ch-nosql}). Also ask whether old messages can move to cheaper storage.
:::

### Bandwidth and memory

Bandwidth = requests per second × bytes per response. At 100,000 reads per second and 1 KB per response, that is 100 MB/s = 800 Mbps outbound: heavy for one network link (1 Gbps), so you need many servers or a CDN. Convert carefully between **bytes** (B) and **bits** (b); network speeds are quoted in bits per second, sizes in bytes. A useful constant: **1 Gbps ≈ 125 MB/s.**

Memory for a cache: if 20% of items serve 80% of reads (the *80/20 rule*, a heuristic, not a law), cache the hot 20%. If the data worth caching is 200 GB, that is a handful of large-memory servers, not one.

### Single-machine capacity

Rough orders for one modern server (to calibrate, then measure): a web server doing simple work handles thousands of requests per second; a database handles low thousands to tens of thousands of simple queries per second; a distributed cache node handles on the order of 100,000 operations per second; an SSD handles tens to hundreds of thousands of random reads per second. If your estimate is far below these, one machine may suffice; far above, you need a distributed design.

## Availability arithmetic {#sec-availmath}

**Availability** = uptime / (uptime + downtime). Expressed in nines, it translates into allowed downtime:

Table[nines]: Allowed downtime for each availability level.

| Availability | Down per year | Down per month | Down per week | Down per day |
|---|---|---|---|---|
| 99% (two nines) | 3.65 days | 7.3 h | 1.68 h | 14.4 min |
| 99.9% (three nines) | 8.77 h | 43.8 min | 10.1 min | 1.44 min |
| 99.99% (four nines) | 52.6 min | 4.4 min | 1.01 min | 8.6 s |
| 99.999% (five nines) | 5.26 min | 26.3 s | 6.05 s | 0.86 s |

**In series** (a request needs *all* components): multiply availabilities. Two components at 99.9% give 0.999 × 0.999 = 99.8%. Every extra dependency on the critical path lowers availability. **In parallel** (any one component suffices, independent failures): unavailability multiplies. Two replicas at 99.9% each give 1 − 0.001 × 0.001 = 99.9999%. This assumes failures are *independent*; two replicas on the same power supply or sharing one buggy deployment fail together, so the real figure is lower.

{{fig avail-series-parallel | Availability in series (all components required: multiply) and in parallel (any one suffices: multiply the failure probabilities).}}

::: warning
**Common mistakes.** Mixing bits and bytes (a factor of eight). Forgetting the peak factor and sizing for the average. Forgetting replication when estimating storage. Treating a derived "five nines" as real when the design has a single SPOF. Presenting an estimate with false precision ("218.4 TB") instead of "a few hundred TB".
:::

## Sensitivity and headroom {#sec-sens}

A good estimator asks "what if the main assumption is off by 10×?" If read volume were ten times larger, would the design survive? If writes were ten times smaller, would it be over-built? Keep a list: *assumption, value, how to measure, impact if wrong.* Then plan for **headroom**: run at no more than about 50% to 70% of peak capacity so one failed node, a traffic burst or a slow dependency does not push the system into overload (Chapter {ch:ch-intro}, latency curve).

::: supplement
**Cost estimation.** Convert capacity to money: servers or instances × price per hour × hours, plus storage per GB-month, plus network egress per GB (often the surprise). Use the cloud provider's current price calculator rather than remembering prices; they change. A rough habit: storage is cheap, data transfer out of the cloud is expensive, and managed services trade money for operational effort. Chapter {ch:ch-cloud} returns to cost and capacity planning.
:::

## Worked example: a URL shortener {#sec-urlest}

This is the notebook's own worked example, expanded. Assume 100 million new URLs per month and a 100 : 1 read-to-write ratio.

::: worked long
1. **Writes per second.** 100 × 10⁶ / (2.5 × 10⁶ seconds per month) = 40 writes per second on average. A peak factor of 10 would be about 400 per second.
2. **Reads per second.** 100 × 40 = 4,000 per second on average; peak about 10,000 (the notebook rounds peak at 10,000).
3. **Storage per URL.** Assume 500 bytes (long URL plus metadata). 100 × 10⁶ × 500 B = 50 GB per month; × 12 × 5 years = 3 TB over five years (at 3 copies, about 9 TB).
4. **Bandwidth.** Incoming: 40 writes/s × 500 B = 20 KB/s. Outgoing: 4,000 reads/s × 500 B = 2 MB/s. A trivial amount; bandwidth is not the constraint.
5. **Cache.** Hottest 20% of daily reads: 4,000 × 86,400 = 345 million reads/day; 20% × 345 million × 500 B ≈ 35 GB: fits in the memory of one or two cache servers.
6. **Conclusion.** The load is small (a few hundred writes/s, ~10,000 reads/s); the cache and a replicated database comfortably serve it. The hard questions are not scale but **unique key generation** and **durability**, so spend interview time there.
:::

::: interview
**Q1. How would you estimate the storage for a photo-sharing service?**
Photos per day × average size (after compression and multiple resolutions) × retention × replication, plus metadata. State assumptions, give an order of magnitude, and note that originals and thumbnails dominate while metadata is small.

**Q2. Convert 99.95% availability into downtime per month.**
0.05% of 43,800 minutes (about 730 hours) ≈ 21.9 minutes per month.

**Q3. Two services in series each have 99.9% availability. What is the combined availability?**
About 99.8%. Series dependencies multiply; this is why long synchronous chains reduce availability.

**Q4. Why does the interviewer care about your numbers if they are rough anyway?**
They show whether you can turn vague scale into design decisions (cache, shard, queue or single database) and whether you notice what dominates.
:::

::: exercise
1. A site has 50 million daily active users (DAU), each making 30 requests per day. Estimate average and peak RPS (peak factor 4).
2. Each request returns 20 KB. Estimate peak outbound bandwidth in Gbps.
3. A service stores 300 million records per year, 1 KB each, replicated 3 times, kept 4 years. How many terabytes?
4. A request touches three services at 99.95%, 99.9% and 99.99%. What is the combined availability and monthly downtime?
5. A user in London calls a service in California that makes four sequential calls to a database in the same data centre and two to a service in Singapore (assume 170 ms per round trip). Estimate the minimum latency.

**Answers.**
1. 50 × 10⁶ × 30 = 1.5 × 10⁹ per day; / 86,400 ≈ 17,400 RPS average; peak ≈ 70,000 RPS.
2. 70,000 × 20 KB = 1.4 GB/s = 11.2 Gbps (× 8 bits). A single 10 Gbps link would saturate; use a CDN and several servers.
3. 300 × 10⁶ × 1 KB = 300 GB per year; × 4 = 1.2 TB; × 3 = 3.6 TB (more with index overhead).
4. 0.9995 × 0.999 × 0.9999 ≈ 0.9984, i.e. 99.84%; downtime ≈ 0.16% of 730 h ≈ 1.2 hours per month.
5. London to California is about 150 ms round trip (use 150 ms), four in-data-centre calls at 0.5 ms = 2 ms, and two Singapore calls at 170 ms = 340 ms: roughly 490 ms minimum, dominated by the long-distance calls. Parallelising the Singapore calls would save 170 ms; replicating data nearer would save most of it.
:::

::: summary
- Estimate to choose designs: convert users into RPS, storage and bandwidth; state assumptions and units.
- Memorise powers of two and the latency ladder; ratios matter more than absolute values.
- Peak, replication, indexes and headroom change the answer; bits are not bytes.
- Availability multiplies in series and improves in parallel only if failures are independent.
- Test sensitivity of the dominant assumption, then go and measure it.
:::

::: revision
- [ ] 1 day ≈ 10⁵ seconds; 1 month ≈ 2.5 × 10⁶ seconds.
- [ ] RPS = DAU × actions / 86,400, then × peak factor.
- [ ] Storage = items × size × retention × replicas × overhead.
- [ ] Three nines ≈ 8.8 hours a year; four nines ≈ 53 minutes a year.
- [ ] Series multiplies availability; parallel multiplies unavailability.
:::

::: supplement
**Further reading.** Jeff Dean's talk "Numbers Everyone Should Know" and the interactive "Latency numbers every programmer should know" web pages (numbers there are updated by their authors; check the date); Google's *Site Reliability Engineering* book for availability targets.
:::
