%part Part III | Data | How data is stored, indexed, scaled, partitioned and kept consistent.
%derived Notebook chapter 6 (RDBMS and ACID, SQL tuning) and the "SQL or NoSQL" comparison
%added joins and normalisation, composite and covering indexes, query plans, isolation levels and anomalies, MVCC, and safe schema migrations
# Relational Databases and SQL {#ch-sql}

::: objectives
After this chapter you can:

- model data as tables with keys and relationships, and explain normalisation;
- write basic SQL (select, join, group, update) and read what it asks the database to do;
- explain how indexes work, design single and composite indexes, and read a query plan;
- explain the four ACID properties, the isolation levels and the anomalies each prevents;
- change a live schema without downtime using the expand-and-contract pattern.
:::

::: prereq
Chapter {ch:ch-ds} (hash tables, B-trees) and Chapter {ch:ch-concurrency} (race conditions, locking).
:::

::: terms
Relational database (RDBMS)
: A database that stores data in tables of rows and columns and is queried with SQL (for example PostgreSQL, MySQL, Oracle, SQL Server).

Primary key
: A column (or set) that uniquely identifies each row.

Foreign key
: A column that refers to the primary key of another table, expressing a relationship.

Transaction
: A group of operations that the database treats as one unit: all succeed or none do.

Index
: A separate structure, usually a B-tree, that speeds up lookups on chosen columns.

Query plan
: The steps the database chooses to execute a query (which index, which join method).
:::

## The relational model {#sec-relmodel}

A **relational database** stores data in **tables**. Each table has typed **columns** and holds many **rows**. Rows in different tables are connected by **keys**, not by physical pointers. The language for asking questions is **SQL** (Structured Query Language), which is *declarative*: you say *what* you want, and the database decides *how* to get it.

```sql
CREATE TABLE users (
  id          BIGINT PRIMARY KEY,
  email       VARCHAR(255) NOT NULL UNIQUE,
  created_at  TIMESTAMP    NOT NULL
);

CREATE TABLE pastes (
  id          BIGINT PRIMARY KEY,
  user_id     BIGINT REFERENCES users(id),     -- foreign key
  short_code  CHAR(7)  NOT NULL UNIQUE,
  content_key VARCHAR(255) NOT NULL,           -- where the text is stored
  created_at  TIMESTAMP NOT NULL,
  expires_at  TIMESTAMP
);
```

{{fig er-paste | An entity-relationship sketch. One user owns many pastes (the foreign key lives on the "many" side); each paste has many views.}}

Why do relational databases remain the default choice? Because they offer **a flexible query language** (new questions without new code), **integrity constraints** (a paste cannot point to a missing user), **transactions**, and decades of tooling. Their traditional limit is *scaling writes beyond one machine*, discussed in Chapter {ch:ch-scaling-sql}.

### Joins, grouping and normalisation

A **join** combines rows from two tables by matching keys.

```sql
-- How many pastes does each user have?
SELECT u.email, COUNT(*) AS paste_count
FROM users u
JOIN pastes p ON p.user_id = u.id
WHERE p.created_at >= '2026-01-01'
GROUP BY u.email
ORDER BY paste_count DESC
LIMIT 10;
```

**Normalisation** means organising tables so each fact is stored once. If every paste row stored the owner's email, changing an email would need many updates, and a missed row would create contradictory data. Putting the email in `users` and referencing it by key removes the duplication (the "update anomaly"). Normalisation gives integrity and smaller writes, at the cost of **joins** on reads. Later (Chapter {ch:ch-scaling-sql}) we meet **denormalisation**: deliberately duplicating data to make reads fast when joins become the bottleneck.

## Indexes {#sec-index}

Without an index, finding `WHERE email = 'a@x.com'` means a **full table scan**: reading every row. An **index** is a separate structure, usually a B+ tree (Chapter {ch:ch-ds}), that maps column values to row locations. With it, the database finds the row in a handful of page reads.

```sql
CREATE INDEX idx_pastes_user_created ON pastes (user_id, created_at);
```

Indexes are not free: every insert, update and delete must also update each index (slower writes), and indexes consume disk and memory. The craft is to index what queries actually need.

**Composite indexes** cover several columns and obey the **leftmost-prefix rule**. An index on `(user_id, created_at)` serves queries filtering by `user_id`, or by `user_id` and `created_at` (and sorted output by `created_at` for one user), but *not* a query filtering by `created_at` alone, just as a phone book sorted by (surname, first name) cannot find everyone named "Asha" quickly. Put equality-tested columns first, then range or sort columns.

A **covering index** contains every column a query needs, so the database answers from the index alone without visiting the table. **Selectivity** matters: an index on a column with two values (a boolean) rarely helps, because it narrows nothing; an index on a nearly unique column narrows to one row.

::: warning
**Common mistakes.** Indexing every column "just in case" (writes slow, memory fills). Wrapping an indexed column in a function (`WHERE LOWER(email) = ...` or `WHERE created_at + 1 > ...`), which prevents index use unless an expression index exists. Using a leading wildcard (`LIKE '%abc'`), which cannot use a normal B-tree. Missing the index on a foreign-key column, making joins and cascading deletes scan whole tables.
:::

### Reading a query plan

Databases expose their chosen strategy with `EXPLAIN`. Learn to read three things: **how rows are accessed** (sequential scan or index scan), **how tables are joined** (nested loop, hash join, merge join), and **estimated versus actual row counts** (wild differences mean stale statistics).

::: worked
**Before and after an index.** Table `pastes` holds 50 million rows.

```text
EXPLAIN SELECT * FROM pastes WHERE user_id = 42 ORDER BY created_at DESC LIMIT 20;

-- no suitable index:
Limit
  -> Sort  (cost=...  rows=48000)
       -> Seq Scan on pastes  Filter: (user_id = 42)   -- reads all 50,000,000 rows

-- after CREATE INDEX idx_pastes_user_created ON pastes (user_id, created_at):
Limit
  -> Index Scan Backward using idx_pastes_user_created
       Index Cond: (user_id = 42)                      -- reads about 20 index entries
```

The first plan reads every row and sorts the matches; the second walks the index backwards from the newest entry for user 42 and stops after 20, because the index is already in the order requested. Time falls from seconds to about a millisecond. The lesson is to design the index to match *both* the filter and the order.
:::

## Transactions and ACID {#sec-acid}

A **transaction** groups operations into one unit. The classic example: transferring 100 from account A to account B is two updates; the system must never apply only one.

```sql
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 'A' AND balance >= 100;
UPDATE accounts SET balance = balance + 100 WHERE id = 'B';
COMMIT;   -- or ROLLBACK to undo everything since BEGIN
```

**ACID** names four properties:

- **Atomicity**: all operations take effect or none do. A crash mid-transfer leaves no half-applied change.
- **Consistency**: a transaction moves the database from one valid state to another, respecting constraints (balances never negative, foreign keys valid). Note: here "consistency" means *integrity rules*, a different notion from the "consistency" of replicas in the CAP theorem (Chapter {ch:ch-distdata}).
- **Isolation**: concurrent transactions do not see each other's partial work; the result is as if they ran one after another (to a degree set by the isolation level).
- **Durability**: once committed, the data survives crashes. Databases achieve this by writing to a **write-ahead log (WAL)** on disk *before* confirming the commit; after a crash the log is replayed.

### Isolation levels and anomalies

Perfect isolation (**serializable**) is expensive, so databases offer weaker levels that allow certain *anomalies*.

{{fig nonrepeatable | A non-repeatable read. Transaction T1 reads a balance twice; transaction T2 commits a change in between, so T1 sees two different values within one transaction.}}

Table[isolation]: Isolation levels (SQL standard names) and which anomalies each permits. "Possible" means the anomaly can occur.

| Level | Dirty read | Non-repeatable read | Phantom read | Notes |
|---|---|---|---|---|
| Read uncommitted | Possible | Possible | Possible | Rarely used |
| Read committed | Prevented | Possible | Possible | Default in PostgreSQL and many others |
| Repeatable read | Prevented | Prevented | Possible (prevented in some engines, e.g. MySQL InnoDB, PostgreSQL) | Default in MySQL InnoDB |
| Serializable | Prevented | Prevented | Prevented | Strongest; may abort transactions that conflict |

Definitions: a **dirty read** sees another transaction's *uncommitted* change; a **non-repeatable read** sees a row change between two reads in the same transaction; a **phantom** sees new rows appear in a repeated range query. There is a further anomaly the standard's table does not show: **write skew**, where two transactions each read overlapping data, make decisions based on it, and write *different* rows, jointly breaking an invariant (two doctors both go off call because each saw the other still on call). Snapshot-based "repeatable read" allows write skew; only serializable isolation or explicit locking prevents it.

Most databases implement isolation with **MVCC** (multi-version concurrency control): each write creates a new *version* of a row, and a transaction reads a consistent **snapshot** as of its start, so readers do not block writers and writers do not block readers. Old versions are cleaned up later (vacuum or purge), which is a maintenance task whose neglect causes bloat.

For correctness at the application level: use the **strongest isolation you can afford** for money and inventory; use `SELECT ... FOR UPDATE` to lock rows you intend to modify; use **conditional updates** (`... WHERE balance >= 100`) and check the affected-row count; and keep transactions **short** because long ones hold locks and block cleanup. As in Chapter {ch:ch-concurrency}, databases can deadlock; they detect cycles and abort one transaction, so your code must be ready to **retry** on a deadlock or serialization failure.

::: note
**Clarification: a database transaction is not a business workflow.** A transaction is atomic only *inside one database*. If a workflow spans a payment provider, an email service and your database, no single `COMMIT` covers it. Chapter {ch:ch-async} covers how to coordinate such workflows (outbox, sagas) and why "exactly once" claims need care.
:::

## Changing a live schema safely {#sec-migrate}

Schema changes are among the riskiest operations: a change that locks a large table can stop the application, and code and schema are never deployed at the same instant. The safe approach is **expand and contract** (also called parallel change), done in small reversible steps.

{{fig expand-contract | Expand and contract. The schema is widened first, data is copied, readers and writers are switched step by step, and only then is the old column removed. At every stage both old and new application versions work.}}

::: worked
**Renaming a column `content_key` to `blob_key` without downtime.**
1. *Expand:* add the new nullable column `blob_key` (a quick change). Deploy code that writes **both** columns.
2. *Backfill:* copy old values in small batches (for example 10,000 rows at a time with pauses) so you never hold long locks or saturate the database.
3. *Switch reads:* deploy code that reads `blob_key`, falling back to `content_key` if null; verify with metrics that no fallback occurs.
4. *Contract:* stop writing `content_key`, wait one release, then drop the column.
Each step can be rolled back by deploying the previous code. A "one-step rename" would have broken every server still running old code.
:::

General rules: add columns as nullable (or with cheap defaults) first; create indexes **concurrently** where the database supports it; never combine a risky schema change with a risky code change; test migrations on a copy of production-sized data; and keep every migration backward-compatible with the *previous* application version. **Backups** are your final safety net, but a backup you have never *restored* is only a hope, so restoration is drilled and timed ({ch:ch-observability}).

## Alternatives and trade-offs {#sec-sqltrade}

Table[sqlprosandcons]: Relational databases: when they fit.

| Strength | Weakness |
|---|---|
| Flexible queries and joins | Scaling writes across machines is hard |
| ACID transactions and constraints | Schema changes need care |
| Mature tooling, strong ecosystem | Joins across large tables can be slow |
| Strong consistency on one node | Replicas lag; sharding breaks cross-shard transactions |

A relational database is the **right default**: begin there unless a requirement (enormous write volume, flexible documents, graph traversal, extreme latency) clearly rules it out, as discussed in Chapter {ch:ch-nosql}.

::: failure
**Failure modes.** A missing index turning a fast query into a table scan as data grows (the system worked in testing and collapses in production); a long transaction blocking vacuum and bloating tables; lock contention on a hot row (a global counter updated by every request); connection exhaustion (each connection costs memory, so applications use a **connection pool** and the database a limit); replication lag after a failover causing lost recent commits; a migration locking a table; disk full stopping all writes; an accidental `DELETE` without a `WHERE` (mitigated by point-in-time recovery, which replays the log to a chosen moment).
:::

::: misconception
- *"ACID consistency is the same as CAP consistency."* No: ACID consistency is about integrity constraints within a database; CAP consistency is about all replicas returning the latest write.
- *"More indexes are always faster."* They speed reads and slow writes.
- *"Transactions make my whole workflow atomic."* Only operations inside one database transaction.
- *"SQL databases cannot scale."* They scale far (read replicas, careful design, sharding); the difficulty is scaling *writes* and cross-shard transactions.
:::

::: interview
**Q1. Explain ACID.**
Atomicity (all or nothing), Consistency (valid state to valid state under constraints), Isolation (concurrent transactions do not interfere, to a configurable degree), Durability (committed data survives crashes via write-ahead logging).

**Q2. A query on a 100-million-row table became slow. How do you investigate?**
Run `EXPLAIN`, look for sequential scans and bad row estimates; check indexes against the filter and sort columns; check statistics are current; look at lock waits and I/O; consider a composite or covering index; verify the fix on realistic data.

**Q3. What is a phantom read, and what prevents it?**
New rows matching a range query appear between two executions in the same transaction; serializable isolation (or range locks / predicate locking) prevents it.

**Q4. How do you rename a column with zero downtime?**
Expand and contract: add new column, dual-write, backfill in batches, switch reads, stop old writes, then drop the old column.
:::

::: exercise
1. Table `orders(id, customer_id, status, created_at)` has 20 million rows. Design indexes for (a) "latest 10 orders of a customer" and (b) "all orders with status = 'pending' created in the last hour".
2. Transaction T1 runs `SELECT SUM(balance)` twice; between the reads T2 deposits 50 into one account and commits. At which isolation levels can T1 see two different totals?
3. Two doctors each check that at least two are on call and then each marks themselves off call. Explain write skew and give two ways to prevent it.
4. Write the SQL to sell the last unit of an item so two buyers cannot both succeed.

**Answers.**
1. (a) `(customer_id, created_at DESC)`; (b) `(status, created_at)` (status first for equality, then the time range). A partial index only on pending rows is even smaller if the database supports it.
2. At read uncommitted and read committed: the second read sees T2's committed deposit (a non-repeatable read, and for a sum over rows a phantom-style effect). At repeatable read and serializable, T1 keeps reading from its snapshot and sees the same total both times.
3. Each transaction reads the other doctor's state from its snapshot, sees "two on call", and writes only its own row, so the invariant "at least one on call" breaks. Prevent by serializable isolation, by locking the rows read (`SELECT ... FOR UPDATE`), or by a constraint enforced in a single row or table.
4. `UPDATE items SET stock = stock - 1 WHERE id = ? AND stock > 0;` then check the affected-row count is 1; only that buyer succeeds.
:::

::: summary
- Relational databases store tables of rows linked by keys, queried with declarative SQL; normalisation keeps facts in one place at the cost of joins.
- Indexes (B+ trees) trade write cost and space for read speed; composite indexes follow the leftmost-prefix rule; read plans with EXPLAIN.
- ACID: atomicity, consistency (integrity), isolation (levels and anomalies, MVCC), durability (write-ahead log).
- Use strong isolation or explicit locks for money and stock; retry on deadlock or serialization failure.
- Change schemas with expand and contract; always keep backward compatibility; drill restores.
:::

::: revision
- [ ] I can write a join and group query.
- [ ] I can design a composite index and explain the leftmost prefix.
- [ ] I can list the isolation levels and anomalies.
- [ ] I can explain write-ahead logging and MVCC in two sentences each.
- [ ] I can run an expand-and-contract migration step by step.
:::

::: supplement
**Further reading.** The PostgreSQL documentation chapters on indexes, EXPLAIN and transaction isolation; Markus Winand, *Use the Index, Luke* (free online); Kleppmann, *Designing Data-Intensive Applications*, chapter 7 (transactions).
:::
