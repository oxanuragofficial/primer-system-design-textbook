%derived Notebook chapter 1 (scaling out, stateless servers) and the object-oriented chapter's LRU and hash-map exercises, which rely on these ideas
%added the whole chapter: processes, threads, concurrency, race conditions, locking and deadlocks
# Processes, Threads and Concurrency {#ch-concurrency}

::: objectives
After this chapter you can:

- explain the difference between a program, a process and a thread, and why threads are cheaper but riskier;
- distinguish concurrency from parallelism, and I/O-bound from CPU-bound work;
- recognise a race condition (check-then-act, lost update) and fix it with a lock, an atomic operation or optimistic concurrency;
- list the four conditions for deadlock and name practical ways to avoid it;
- explain why these problems come back, in harder form, when the "threads" are separate machines.
:::

::: prereq
Chapter {ch:ch-intro}. A little programming experience (variables, functions, a loop) is enough; the code samples are short Python.
:::

::: terms
Process
: A running program with its own private memory and resources, isolated from other processes by the operating system (OS).

Thread
: A path of execution inside a process. Threads of one process share its memory.

Context switch
: The OS pausing one thread and resuming another on a CPU core; it costs time because state must be saved and restored.

Concurrency
: Making progress on several tasks during overlapping time periods, possibly on one core by interleaving.

Parallelism
: Literally executing several tasks at the same instant on different cores or machines.

Race condition
: A bug whose outcome depends on the unpredictable timing of two or more threads.

Critical section
: A piece of code that must not be executed by two threads at once.

Mutex (lock)
: A mechanism allowing only one thread at a time into a critical section.

Deadlock
: Two or more threads each waiting for something another holds, so none can proceed.
:::

## Programs, processes and threads {#sec-proc}

A **program** is a file of instructions. When the OS runs it, it creates a **process**: a private address space (its own memory), open files and network connections, and at least one **thread** of execution. Because processes do not share memory, one process crashing normally does not corrupt another. That isolation is valuable and expensive: starting a process takes noticeable time and memory, and processes must talk to each other through explicit channels such as sockets or pipes.

A process may start more **threads**. All threads of a process see the same memory, so they can cooperate cheaply, for example by updating a shared in-memory cache. The price is that they can also corrupt each other's data. A bug in one thread can crash the whole process.

Table[procthread]: Processes versus threads.

| | Process | Thread |
|---|---|---|
| Memory | Private | Shared with sibling threads |
| Creation cost | Higher | Lower |
| Communication | Sockets, pipes, files (explicit) | Shared variables (implicit, dangerous) |
| Failure isolation | Strong | Weak: one thread can take down all |
| Typical use | Separate services, worker pools | Handling many requests inside one server |

A CPU core executes one thread at a time. With more threads than cores, the OS rapidly switches between them (a **context switch**), giving the *illusion* of simultaneity. Each switch costs microseconds and disturbs CPU caches, so thousands of busy threads can spend more time switching than working. This is one reason web servers use thread pools of bounded size rather than one thread per connection without limit.

## Concurrency and parallelism {#sec-conc}

Concurrency is about *structure*: dealing with many things at once. Parallelism is about *execution*: doing many things at once. A single-core machine can be concurrent (interleaving) but not parallel. A server answering a thousand clients is concurrent; whether it is also parallel depends on how many cores or machines it has.

Choose the technique by what the work waits for.

- **I/O-bound** work spends most time waiting for something external: a disk, a network call, a database. While one request waits, the CPU is idle and can serve another. Concurrency gives big gains here, often with a single thread using an **event loop** (the thread starts an operation, registers a callback, and handles other events until it completes; used by Node.js, Python's `asyncio`, and many proxies).
- **CPU-bound** work (image resizing, encryption, compression) keeps a core busy. Only more cores, i.e. real parallelism, speed it up. More threads than cores just add switching cost.

::: worked
**How many threads?** A server handles requests that each spend 5 ms computing and 45 ms waiting for a database. One thread can finish 20 requests per second (each takes 50 ms). If the machine has 4 cores, how many threads keep them busy? During the 50 ms a thread is blocked for 45 ms and runs for 5 ms, so one core can interleave about 50 / 5 = 10 threads before saturating. With 4 cores, roughly 40 threads fully use the CPU, giving about 4 × 200 = 800 requests per second (each core can compute 1000 / 5 = 200 requests per second). Beyond about 40 threads you gain nothing; you only queue longer. The rule of thumb: threads ≈ cores × (1 + wait time / compute time). These are illustrative numbers; real systems are measured, not computed.
:::

## Race conditions {#sec-race}

A **race condition** appears when the result depends on the order in which threads happen to run. The classic example is two threads incrementing a shared counter. The statement `count = count + 1` looks atomic (indivisible) but is really three steps: read the value, add one, write it back.

{{fig lost-update | A lost update. Both threads read 10, both compute 11, both write 11. Two increments happened, but the counter rose by only one.}}

In {fig:lost-update}, thread A and thread B each read 10 before either writes. Both compute 11 and write 11. One update is **lost**, with no error message and no crash. Races like this are rare in testing (the timing window is tiny) and appear under production load, which makes them especially nasty.

The second common shape is **check-then-act**: you check a condition and then act on it, but the condition changes in between.

```python
# BROKEN: two requests can both pass the check
def withdraw(account, amount):
    if account.balance >= amount:       # check
        account.balance -= amount       # act (balance may have changed!)
        return True
    return False
```

If the balance is 100 and two threads each withdraw 80, both can pass the check before either subtracts, leaving a balance of -60. The same shape appears in "if the username is free, create it", "if stock > 0, sell one", and "if the cache is empty, load it" (the last causes the *cache stampede* in {ch:ch-cache}).

## Locks and other remedies {#sec-lock}

There are three families of fix.

**1. Mutual exclusion (locks).** Wrap the critical section so only one thread at a time enters it.

```python
import threading
lock = threading.Lock()

def withdraw(account, amount):
    with lock:                      # only one thread inside at a time
        if account.balance >= amount:
            account.balance -= amount
            return True
        return False
```

Locks are correct but have costs: threads wait (lower throughput), the lock can become the serial bottleneck (recall Amdahl's law, Chapter {ch:ch-intro}), and misuse causes deadlock. Keep critical sections *short*, and never perform slow I/O while holding a lock. A **read-write lock** allows many simultaneous readers but only one writer, which suits read-heavy data.

**2. Atomic operations.** Modern CPUs offer indivisible instructions such as *compare-and-swap* (CAS): "set this variable to *new* only if it currently equals *expected*; tell me whether it worked."

```python
# pseudocode: lock-free increment using compare-and-swap
def increment(counter):
    while True:
        old = counter.load()
        if counter.compare_and_swap(old, old + 1):   # succeeds only if unchanged
            return                                   # otherwise retry
```

**3. Optimistic concurrency.** Assume conflicts are rare; do the work without locking, and at the end check that nothing changed, retrying if it did. Databases use this with a **version column**: `UPDATE accounts SET balance = ?, version = version + 1 WHERE id = ? AND version = ?`. If zero rows are updated, someone else got there first; re-read and retry. **Pessimistic** locking (lock first) wins when conflicts are frequent; optimistic wins when they are rare, because nobody waits.

::: warning
**Common mistakes.** (1) Locking only the *write* and not the *check*, which leaves the check-then-act gap. (2) Using a lock that protects *one process* to protect data shared across *several servers*; it does nothing there. (3) Holding a lock while calling a remote service that may hang. (4) Assuming that "it passed my tests" means "it has no race".
:::

## Deadlock, livelock and starvation {#sec-deadlock}

A **deadlock** occurs when threads wait for each other forever. Suppose thread 1 holds lock A and wants lock B, while thread 2 holds lock B and wants lock A. Neither can proceed ({fig:deadlock}).

{{fig deadlock | A circular wait. Thread 1 holds lock A and waits for lock B; thread 2 holds B and waits for A.}}

Deadlock needs all four **Coffman conditions** at once: (1) *mutual exclusion*: a resource is held by at most one thread; (2) *hold and wait*: threads hold resources while waiting for others; (3) *no preemption*: resources cannot be forcibly taken; (4) *circular wait*: a cycle of waiting threads exists. Break any one and deadlock is impossible. The most practical way is to break circular wait by imposing a **global lock order**: every thread acquires locks in the same order (say alphabetically by name), so no cycle can form. Other defences are *lock timeouts* (give up and retry, with random delay), acquiring all needed locks at once, and detecting cycles and aborting one victim, which databases do automatically.

Two relatives: **livelock**, where threads keep reacting to each other and make no progress (two people in a corridor stepping aside in the same direction forever), and **starvation**, where a thread never gets the resource because others always go first.

## When the threads are machines {#sec-distributed-view}

::: supplement
Everything above assumed shared memory on one computer. A web application on ten servers has the same problems, but a process-local lock is useless between machines, and a "pause" can last seconds and may not be noticed. The distributed equivalents are: **database transactions and row locks** ({ch:ch-sql}), **optimistic version checks** (as above), **idempotency keys** so retries do not duplicate work ({ch:ch-async}), and **distributed locks and leases** coordinated through a consensus system ({ch:ch-consensus}). Distributed locks are subtle: a lock holder can pause (a long garbage-collection pause, a stalled network) and still believe it holds a lock that has expired, so well-designed systems also use *fencing tokens*, increasing numbers that the protected resource uses to reject stale holders.
:::

::: failure
**Failure modes.** *Lost update* and *double spend* from check-then-act; *deadlock* freezing a service until restart; *thread-pool exhaustion* when all threads are blocked on a slow dependency (new requests queue and time out); *priority inversion*, where a low-priority thread holding a lock delays a high-priority one; *memory visibility* bugs, where one thread does not see another's write without proper synchronisation. Recovery usually means timeouts on every wait, bounded thread pools and queues, and metrics showing lock wait time and pool utilisation ({ch:ch-observability}).
:::

::: misconception
- *"Python code is safe because of the global interpreter lock."* The GIL protects the interpreter's internals, not your multi-step logic; `count += 1` can still lose updates across threads.
- *"More threads means faster."* Only until cores or the shared resource saturate.
- *"A race is a rare bug I can ignore."* Rare per request becomes frequent at millions of requests per day.
:::

::: interview
**Q1. What is a race condition? Give an example and a fix.**
A bug whose result depends on timing. Two concurrent withdrawals both pass a balance check and overdraw. Fix by making check and update atomic: a lock, a database transaction with a row lock, or a conditional update (`WHERE balance >= amount`).

**Q2. Threads versus processes?**
Threads share memory (cheap, fast communication, risky); processes are isolated (safer, heavier). Services often use processes for fault isolation and threads or event loops inside each for request concurrency.

**Q3. How do you prevent deadlock?**
Acquire locks in a fixed global order, hold as few locks as possible for as short as possible, use timeouts with retry and jitter, or let the database detect and abort a victim.

**Q4. When would you choose optimistic over pessimistic locking?**
When conflicts are rare and retrying is cheap, such as editing different records. Pessimistic locking suits high-conflict hot rows, where repeated retries would waste work.
:::

::: exercise
1. A thread-pool server has 8 cores; each request computes for 2 ms and waits 18 ms on I/O. Estimate the thread count that saturates the CPU and the resulting request rate.
2. Rewrite `if stock > 0: stock -= 1` so that two buyers cannot both buy the last item, first with a lock, then with a single SQL statement.
3. Two services each lock a customer row and an order row, but in opposite orders. Explain how a deadlock arises and fix it.
4. Why does a `threading.Lock` not protect a counter shared by two web servers?

**Answers.**
1. Threads ≈ 8 × (1 + 18/2) = 80. Each core computes 500 requests/second (1000 ms / 2 ms), so about 8 × 500 = 4,000 requests per second at saturation (illustrative).
2. With a lock: `with lock: if stock > 0: stock -= 1`. In SQL: `UPDATE items SET stock = stock - 1 WHERE id = ? AND stock > 0;` then check that one row changed.
3. Service A holds the customer lock and waits for the order lock; B holds the order lock and waits for the customer lock: a cycle. Fix by always locking customer before order.
4. The lock exists only in one process's memory; the other server has its own lock object, so both can enter the critical section. Use a database row lock, a conditional update, or a distributed lock with fencing.
:::

::: summary
- Processes are isolated; threads share memory and are cheaper but riskier.
- Concurrency is structure, parallelism is simultaneous execution; I/O-bound work benefits from concurrency, CPU-bound work from more cores.
- Race conditions (lost update, check-then-act) are timing bugs fixed by atomicity: locks, atomic instructions or optimistic version checks.
- Deadlock needs four conditions; a global lock order breaks circular wait.
- Across machines the same problems return; use database transactions, version checks, idempotency and fenced distributed locks.
:::

::: revision
- [ ] I can explain a lost update with a timeline.
- [ ] I can fix a check-then-act bug three ways.
- [ ] I can list the four deadlock conditions and one prevention.
- [ ] I can say why a local lock fails across servers.
:::

::: supplement
**Further reading.** Maurice Herlihy and Nir Shavit, *The Art of Multiprocessor Programming*; Brian Goetz et al., *Java Concurrency in Practice* (concepts apply widely); Martin Kleppmann, "How to do distributed locking" (2016) on fencing tokens.
:::
