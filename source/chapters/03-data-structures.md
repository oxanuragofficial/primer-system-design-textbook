%derived Notebook chapter 13 (hash map and LRU cache designs), chapter 12.6 (query cache) and the sharding and caching chapters, which assume these structures
%added the whole chapter: hash tables, trees, B-trees, LSM trees, heaps, bloom filters, tries, skip lists, probabilistic counting, complexity
# Data Structures and Algorithms for System Design {#ch-ds}

::: objectives
After this chapter you can:

- read Big-O notation and use it to compare operations on large data;
- explain hash tables, balanced trees, B-trees and log-structured merge (LSM) trees and say which databases use which;
- use heaps, queues, tries, bloom filters and counting sketches where they fit;
- explain how these structures reappear inside caches, indexes, queues and rankings in later chapters.
:::

::: prereq
Chapter {ch:ch-intro} and basic programming. No algorithms course is assumed.
:::

::: terms
Big-O notation
: A way of describing how the cost of an operation grows with input size *n*, ignoring constant factors. O(1) is constant, O(log *n*) grows slowly, O(*n*) is linear, O(*n* log *n*) is typical of sorting, O(*n*²) quickly becomes unusable.

Hash function
: A function turning a key of any size into a fixed-size number, intended to spread keys evenly.

Collision
: Two different keys mapped to the same hash bucket.

Index
: An extra structure that lets you find rows by a key without scanning everything.

Write amplification
: The ratio of bytes physically written to disk to bytes the application asked to write.

False positive
: A structure answering "yes, present" when the item is in fact absent. Some structures allow these in exchange for tiny memory use.
:::

## Why data structures matter in system design {#sec-dswhy}

System design diagrams show boxes: a cache, a database index, a queue, a leaderboard. Inside each box is a data structure chosen to make one operation cheap, and every choice makes some other operation expensive. Knowing the structure lets you predict behaviour you would otherwise discover during an outage: why a database slows when an index no longer fits in memory, why a cache needs a second structure to evict, why a counter of unique visitors can be 1% wrong and use 12 KB instead of gigabytes.

### Reading Big-O

Big-O describes growth, not speed. Suppose you search a list of one billion items. An O(*n*) scan examines up to 10⁹ items. An O(log *n*) search in a sorted structure examines about log₂(10⁹) ≈ 30. An O(1) hash lookup examines one bucket (on average). The *constants* matter too: reading memory is roughly 100 ns, a random disk seek on a spinning disk about 10 ms, so a 30-step search over disk can still be slower than a 1,000-step scan in memory. Therefore ask two questions: how does the cost *grow*, and *where* does each step happen (CPU cache, memory, SSD, disk, network)?

Table[bigo]: Growth of common complexities for n = 1,000,000.

| Complexity | Steps for n = 10⁶ | Typical example |
|---|---|---|
| O(1) | 1 | Hash lookup by key |
| O(log n) | about 20 | Binary search, balanced tree, B-tree level count |
| O(n) | 1,000,000 | Full scan of a table |
| O(n log n) | about 20,000,000 | Sorting |
| O(n²) | 10¹² | Comparing every pair; avoid on large data |

## Hash tables {#sec-hash}

A **hash table** stores key-value pairs in an array of *buckets*. To find a key, compute `hash(key) mod bucket_count` to pick a bucket, then look inside it. With a good hash function and enough buckets, each bucket holds about one item, so lookup, insert and delete are O(1) on average.

Collisions are unavoidable (many more possible keys than buckets). Two standard strategies:

- **Chaining**: each bucket holds a linked list (or small array) of the entries that landed there. Lookup walks the short list.
- **Open addressing**: if the bucket is taken, probe the next buckets by a fixed rule until a free one is found.

The **load factor** is items divided by buckets. As it grows, collisions multiply and operations slow, so the table is *resized* (usually doubled) when the load factor crosses a threshold such as 0.75, and every entry is *rehashed* into the new array. Resizing is expensive (O(*n*)) and happens rarely, so the *amortised* cost per insert stays O(1), but a single insert may pause. Distributed systems face the same problem at larger scale, where adding a server changes `hash mod N` for almost every key. {ch:ch-distdata} introduces *consistent hashing* to avoid that.

{{fig hash-table | A hash table with chaining. Keys "ann" and "raj" collide in bucket 2 and are kept in a short list.}}

**Strengths:** very fast point lookups. **Weaknesses:** no ordering, so range queries ("all keys between a and f") need a full scan; unpredictable resize pauses; poor hash functions create hot buckets. In practice: in-memory caches, dictionaries, deduplication sets, and the key-value family of databases ({ch:ch-nosql}).

## Ordered structures: trees, B-trees and indexes {#sec-trees}

When you need keys *in order*, for range queries and sorted results, use a tree. A **binary search tree** keeps smaller keys on the left and larger on the right; a *balanced* one (red-black, AVL) guarantees height O(log *n*) so search, insert and delete are all O(log *n*).

Databases and file systems almost never use binary trees directly, because each tree step is a separate random read, and disk reads are slow. A **B-tree** (in practice the **B+ tree** variant) fixes this by making each node *wide*: one node is sized like a disk page (commonly 4 to 16 KB) and holds hundreds of keys. The tree is therefore very shallow.

::: worked
**How deep is a B-tree?** Suppose each node holds up to 500 child pointers. Level 1 (the root) reaches 500 children; level 2 reaches 500 × 500 = 250,000; level 3 reaches 125,000,000; level 4 reaches 62.5 billion. So a table with 100 million rows can be indexed by a tree of only about **3 levels**, and finding any row costs about 3 page reads, often fewer because the upper levels stay cached in memory. (These are illustrative numbers; real fan-out depends on key size.) In a B+ tree, leaf pages are also linked in order, so a range scan walks along the leaves without going back to the top.
:::

{{fig btree | A three-level B+ tree index. The root and middle pages guide the search; leaf pages hold keys (with row pointers) in sorted order and are linked for range scans.}}

Each level narrows the search ({fig:btree}). A lookup of key 42 reads the root, follows the pointer for the range containing 42, reads the middle page, then the leaf. B-trees are the default index in most relational databases ({ch:ch-sql}). Their cost is on writes: inserting into a full page *splits* it, and updates modify pages in place, which can cause random writes and, under heavy write load, more disk work.

## Log-structured merge trees {#sec-lsm}

An **LSM tree** takes the opposite approach to writes: never update in place; **append** instead. Incoming writes go first to a **write-ahead log** on disk (for durability) and into a sorted in-memory structure (the *memtable*). When the memtable fills, it is written to disk as an immutable sorted file (an *SSTable*, sorted string table). Over time many files accumulate, so a background process called **compaction** merges them, discarding overwritten and deleted entries. To avoid checking every file on a read, each file has a **bloom filter** (below) that quickly says "definitely not here".

{{fig lsm | Write path of an LSM tree: append to a log, update the in-memory table, flush to sorted immutable files, then compact them in the background.}}

Table[btree-vs-lsm]: B-tree versus LSM tree.

| | B-tree | LSM tree |
|---|---|---|
| Write pattern | In-place page updates (random writes) | Sequential appends and batched merges |
| Write throughput | Good | Usually higher, especially on disks |
| Read cost | Few page reads, predictable | May check several files (mitigated by bloom filters) |
| Space | Some wasted space in pages | Compaction needs temporary extra space |
| Write amplification | Moderate | Can be high (data rewritten during compaction) |
| Typical users | PostgreSQL, MySQL (InnoDB), most relational databases | Cassandra, HBase, RocksDB, LevelDB; many NoSQL stores |

## Heaps, queues and ranking {#sec-heap}

A **queue** returns items in the order added (first in, first out, FIFO); a **stack** in reverse (last in, first out). A **priority queue** returns the item with the highest priority, and is usually built as a **heap**: a tree stored in an array where each parent is smaller (min-heap) than its children. Insertion and removal of the minimum cost O(log *n*); peeking at the minimum is O(1).

Heaps solve *top-k* problems elegantly. To find the 10 highest-scoring items in a stream of a billion, keep a min-heap of size 10: for each new item, if it beats the heap's minimum, replace it. Memory is O(10), time O(*n* log 10). This idea underlies leaderboards, "trending" lists, scheduling (which job runs next), and the crawler's frontier ({ch:ch-crawler}). When you need a *live* ranking you can update and query by position, as in a game leaderboard, the usual answer is a **sorted set** (a skip list or tree with scores), as offered by Redis.

## Tries {#sec-trie}

A **trie** (prefix tree) stores strings one character per edge, so all strings sharing a prefix share a path. Looking up a word of length *L* costs O(*L*), independent of how many words are stored, and "all words starting with `sys`" is simply the subtree below that path. Tries power autocomplete and spell-checkers, and routing tables for IP prefixes. Their weakness is memory use for sparse data, reduced by compressed variants (radix trees).

## Bloom filters and probabilistic structures {#sec-bloom}

Sometimes an exact answer costs too much memory and an approximate one is acceptable. A **bloom filter** answers "have I seen this item?" using a bit array and several hash functions. To add an item, set the bits at its *k* hash positions. To test an item, check those *k* bits: if any is 0, the item is **definitely absent**; if all are 1, it is **probably present**. It never gives false negatives but may give false positives; the rate falls as you spend more bits per item (about 10 bits per item gives a false-positive rate near 1%).

{{fig bloom | A bloom filter with three hash functions. "cat" and "dog" were added. Testing "emu" finds a zero bit, so it is definitely absent; testing "fox" finds all ones by coincidence, a false positive.}}

Uses: LSM trees skip files that cannot hold a key; a web crawler checks "have I already queued this URL?" without storing every URL; a cache or database avoids expensive lookups for keys that do not exist (protecting against *cache penetration*, {ch:ch-cache}). Limitations: standard bloom filters cannot delete items (counting variants can), and the size must be planned in advance.

Two related tools: **HyperLogLog** estimates the number of *distinct* items (unique visitors) with a typical error around 1% using only a few kilobytes, and a **count-min sketch** estimates how often each item occurred (frequent search terms) using a small table, never under-counting but possibly over-counting.

## Choosing the structure {#sec-choose}

Table[choose]: Which structure for which need.

| Need | Structure | Why |
|---|---|---|
| Exact lookup by key | Hash table | O(1) average |
| Range queries, sorted order | B-tree or LSM | Ordered keys |
| Heavy write rate | LSM tree | Sequential appends |
| Top-k, scheduling | Heap / priority queue | O(log n) updates |
| Prefix search | Trie | Shared prefixes |
| "Definitely not present" cheaply | Bloom filter | Tiny memory, no false negatives |
| Distinct count at scale | HyperLogLog | ~1% error, kilobytes |
| Evict least-recently-used | Hash map + doubly linked list | O(1) for both operations (see {ch:ch-oo-ds}) |

::: failure
**Failure modes.** A hash table resize pausing a latency-sensitive path; a hot bucket or hot shard from skewed keys; a B-tree index larger than memory so that every lookup becomes a disk read; compaction falling behind writes in an LSM store, so reads slow and disk fills; a bloom filter sized for 1 million items now holding 100 million, whose false-positive rate approaches 100% and makes it useless.
:::

::: misconception
- *"O(1) means fast."* It means the cost does not grow with *n*; the constant might be a network round trip.
- *"An index always speeds things up."* Each index speeds some reads and slows every write, and uses space.
- *"A bloom filter can say an item is present."* It can only say *probably* present; "absent" is the reliable answer.
:::

::: interview
**Q1. Why do databases use B-trees rather than binary trees?**
Disk and page reads dominate cost. A B-tree node holds hundreds of keys, so the tree is only a few levels deep, minimising reads; binary trees would need many more, scattered reads.

**Q2. When is an LSM tree better than a B-tree?**
For write-heavy workloads: LSM turns random writes into sequential appends. The trade-off is compaction work and reads that may touch several files.

**Q3. How would you implement an LRU cache with O(1) operations?**
A hash map from key to a node in a doubly linked list ordered by recency; on access move the node to the head; on insert beyond capacity remove the tail node and its map entry.

**Q4. How can you count unique visitors across billions of events without storing them?**
HyperLogLog: about 1% error with kilobytes of memory, and sketches from different servers can be merged.
:::

::: exercise
1. A B-tree has fan-out 200. How many levels are needed to index 8 million rows? Then 1.6 billion?
2. A bloom filter has 10 bits per item and holds 1 million items. How many bytes is the bit array? What happens if you insert 10 million items without resizing?
3. Design a data structure to return the top 5 most frequent search terms of the last hour (state your assumptions).
4. Why can a hash table not answer "all keys starting with `sys`" quickly, and what would you use?

**Answers.**
1. 200¹ = 200; 200² = 40,000; 200³ = 8,000,000, so 3 levels for 8 million; 200⁴ = 1.6 billion, so 4 levels.
2. 10 bits × 1,000,000 = 10,000,000 bits = 1.25 MB. With 10 million items the array is nearly all ones and false positives approach 100%: it must be resized or rebuilt.
3. One reasonable design: per-minute count-min sketches or exact hash maps of counts, summed over 60 buckets (drop the oldest minute each minute), plus a min-heap of size 5 over the summed counts. Exact counts are possible if the vocabulary fits in memory; otherwise use the sketch.
4. A hash destroys ordering, so keys with a shared prefix are scattered; use a trie (or an ordered structure such as a B-tree or sorted set with range scan).
:::

::: summary
- Big-O shows growth; also ask where each step runs (memory, disk, network).
- Hash tables: O(1) point lookups, no order. B-trees: shallow, ordered, read-friendly. LSM trees: sequential writes, compaction cost.
- Heaps give top-k and scheduling; tries give prefix search; bloom filters give cheap "definitely not"; HyperLogLog and count-min sketch trade exactness for tiny memory.
- Choose by the dominant operation, and remember every structure has a price.
:::

::: revision
- [ ] I can explain chaining, load factor and resizing.
- [ ] I can compute B-tree depth from fan-out.
- [ ] I can describe the LSM write path and compaction.
- [ ] I can say what a bloom filter can and cannot guarantee.
- [ ] I can build an O(1) LRU cache on paper.
:::

::: supplement
**Further reading.** Kleppmann, *Designing Data-Intensive Applications*, chapter 3 (storage engines: B-trees and LSM trees); Burton Bloom's 1970 paper on hash coding with allowable errors; Flajolet et al. on HyperLogLog (2007); Cormode and Muthukrishnan on the count-min sketch (2005).
:::
