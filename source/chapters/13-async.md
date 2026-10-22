%derived Notebook chapter 9 (asynchronous workflows, message queues, task queues, back pressure, the broker comparison table)
%added delivery guarantees and the limits of exactly-once, publish/subscribe and consumer groups, retries and dead-letter queues, idempotent consumers, the transactional outbox and sagas
# Asynchronous Processing {#ch-async}

::: objectives
After this chapter you can:

- decide which work belongs on the request path and which should be done later;
- explain queues, topics, consumer groups and acknowledgements, and the difference between a queue and a publish/subscribe log;
- explain at-most-once, at-least-once and "exactly-once" delivery, and why the last claim needs care;
- design retries with backoff, jitter, dead-letter queues and idempotent consumers;
- apply back pressure, the transactional outbox and sagas.
:::

::: prereq
Chapter {ch:ch-api} (idempotency keys), Chapter {ch:ch-sql} (transactions), Chapter {ch:ch-distdata} (consistency).
:::

::: terms
Message
: A small, self-contained piece of data describing work to do or an event that happened.

Producer / consumer
: The program that puts messages on a queue, and the program that takes them off and processes them.

Broker
: The server that stores messages durably and hands them to consumers (RabbitMQ, SQS, Kafka, and others).

Acknowledgement (ack)
: A consumer's signal to the broker that a message was processed and can be removed.

Dead-letter queue (DLQ)
: A holding queue for messages that repeatedly fail, so they do not block others.

Back pressure
: Slowing or refusing producers when consumers cannot keep up, instead of letting work pile up without limit.
:::

## Why work asynchronously {#sec-whyasync}

A **synchronous** operation makes the caller wait for completion. An **asynchronous** one accepts the request, promises to do it, and lets the caller continue. Asynchrony helps in three ways:

1. **Response time.** Do only what the user must see immediately; do the rest later. Posting a photo returns in 100 ms; thumbnails, notifications and indexing happen in the next seconds.
2. **Smoothing bursts.** A queue absorbs a spike so servers work at a steady pace instead of being overwhelmed (a *buffer* between producers and consumers).
3. **Decoupling and resilience.** If the email service is down, messages wait in the queue instead of failing the user's request; producers and consumers can be deployed and scaled independently.

The notebook names two flavours. **Precompute** work that can be done ahead of time (nightly aggregation, pre-rendered pages, a user's timeline); and **defer** slow work behind a queue. The price is real: results are no longer instantly visible (*eventual consistency*), the user may need to be told "we are working on it", failures happen where nobody is watching, and debugging spans several components.

{{fig async-flow | A request returns quickly after placing a message on a queue. Workers process messages later at their own pace; the user learns the result by polling, push notification or a refreshed page.}}

## Message queues {#sec-queues}

A **message queue** stores messages between a producer and a consumer. The producer sends and moves on. The broker persists the message. A consumer receives it, does the work, and **acknowledges**; only then does the broker delete it. If the consumer crashes before acknowledging, the broker makes the message available again after a **visibility timeout**, so another consumer retries it. Several consumers can read from one queue, sharing the work (**competing consumers**); that is the basis of horizontal scaling of workers.

```python
# producer (web request)
queue.send({"type": "resize_image", "photo_id": 981, "request_id": "r-77"})
return 202  # Accepted: work will happen later

# consumer (worker)
while True:
    msg = queue.receive(wait_seconds=20)       # long polling
    if msg is None: continue
    try:
        resize(msg.body["photo_id"])
        queue.ack(msg)                          # delete only after success
    except TemporaryError:
        pass                                    # no ack: it reappears later
```

**Ordering.** A single queue with one consumer processes messages in order; with several consumers it does not. When order matters per entity (all events for order 17 must stay in sequence), partition messages by a key so that all messages with one key go to one consumer.

### Delivery guarantees

Because networks and processes fail, a broker cannot always know whether a consumer finished.

- **At-most-once**: the message is delivered zero or one times. Acknowledge *before* processing; if the worker crashes, the message is lost. Fine for metrics sampling, not for payments.
- **At-least-once**: delivered one or more times. Acknowledge *after* processing; if the worker crashes after the work but before the ack, the message is redelivered and the work repeats. This is the usual default.
- **Exactly-once**: processed precisely once.

::: note
**Clarification: the limits of "exactly-once".** Exactly-once *delivery* between independent systems over an unreliable network is impossible to guarantee in general: when an acknowledgement is lost, the sender cannot tell whether the receiver acted. What products call "exactly-once" usually means **exactly-once *effect* within a bounded scope**: at-least-once delivery combined with **deduplication** or **idempotent processing**, or atomic transactions that commit a consumer's offset and its output together inside the same system (as some streaming platforms support). The guarantee stops at the system's boundary: if the consumer also sends an email or calls a payment provider, that external action can still happen twice. The practical rule: **assume at-least-once delivery and make every consumer idempotent.**
:::

## Publish/subscribe and logs {#sec-pubsub}

A queue gives each message to *one* consumer. In **publish/subscribe (pub/sub)**, a producer publishes an event to a **topic**, and **every subscriber** receives a copy. A single "order placed" event can notify billing, shipping, analytics and email independently, and the producer does not know who listens (**decoupling**).

{{fig pubsub | A queue delivers each message to one consumer in a group; pub/sub delivers each message to every subscribing group. Within a group, consumers share the work.}}

Systems such as Kafka combine both with **consumer groups** over a **partitioned, append-only log**. Messages are appended to partitions and kept for a retention period. Each consumer group tracks its own **offset** (position) per partition; consumers within a group split the partitions among themselves; a different group reads independently, and can even **replay** history by resetting its offset. Ordering is guaranteed *within a partition*, so the partition key (for instance the user id) determines ordering and parallelism.

Table[brokers]: Types of messaging systems (from the notebook, extended).

| Kind | Examples | Model | Strength | Watch out |
|---|---|---|---|---|
| Simple queue service | Amazon SQS, Redis lists | Queue, competing consumers | Easy, managed | Limited ordering; at-least-once, duplicates |
| Feature-rich broker | RabbitMQ, ActiveMQ | Queues and exchanges, routing, acks | Flexible routing, priorities | Throughput limits; operations |
| Distributed log | Kafka, Pulsar, Kinesis | Partitioned append-only log, groups, replay | High throughput, replay, ordering per partition | More concepts; partition design |
| Task queue frameworks | Celery, Sidekiq, Bull | Job queue with scheduling and retries | Developer-friendly | Built on a broker; check its guarantees |

**Task queues** (the notebook's term) are queues specialised for *jobs*: they receive a task and its data, run it, and report the result. They add scheduling (run at 03:00), priorities, retries, rate limiting and result tracking, and suit CPU-heavy or slow work such as video encoding or report generation.

## Retries, dead letters and idempotent consumers {#sec-retry}

**Failures come in two kinds.** *Transient* (a timeout, a briefly unavailable database): retrying will probably succeed. *Permanent* or **poison** messages (malformed data, a bug): retrying will never succeed and can block the queue forever. Handle both.

- **Retry with exponential backoff and jitter**: wait 1 s, then 2, 4, 8, ... up to a maximum, each multiplied by a random factor, so a thousand failed jobs do not all retry in the same instant (*retry storm*).
- **Cap the attempts** (for example 5), then move the message to a **dead-letter queue** with the error, so that engineers can inspect it, fix the bug and **redrive** it. Alert on DLQ depth: a growing DLQ means something is wrong.
- **Make consumers idempotent**, because at-least-once delivery *will* produce duplicates. Techniques: a natural idempotency (setting a field to a value, not incrementing it); a **processed-message table** with a unique key on the message id, inserted in the *same transaction* as the work; **conditional writes** (apply only if the version matches); or deduplication windows at the broker.

```python
def handle(msg):
    with db.transaction():
        if not db.insert_if_absent("processed", id=msg.id):   # unique constraint
            return                                             # duplicate: ignore
        apply_business_change(msg)                             # same transaction
    queue.ack(msg)                                             # ack last
```

Note the order: the *dedup record and the business effect commit together*, and the ack comes last. If the worker dies after commit but before ack, the redelivery finds the record and does nothing.

## Back pressure {#sec-backpressure}

If producers add work faster than consumers finish it, an unbounded queue grows until memory or disk is exhausted, and the wait in the queue grows with it: by the time work is done, nobody wants the answer. **Back pressure** pushes the problem back to the source. Bound the queue; when it is full, **refuse new work** quickly (for example HTTP `503 Service Unavailable` with `Retry-After`) and let clients retry with backoff; or slow producers down (blocking sends, credit-based protocols); or **shed** low-priority work first.

{{fig backpressure | A bounded queue with back pressure. When the queue is full the front door rejects new requests quickly, keeping the accepted ones healthy, instead of accepting everything and failing slowly.}}

::: worked
**How big a queue?** Workers complete 200 jobs per second. Users should wait no longer than 30 seconds. A queue longer than 200 × 30 = 6,000 jobs would make the *last* job wait over 30 seconds, so a bound of about 6,000 is the maximum useful size. If a burst offers 1,000 jobs per second for 20 s (20,000 jobs) while workers do 200 per second, the queue fills in 6,000 / (1,000 − 200) = 7.5 s; after that, producers get 503s. The remedies, in order: add workers (autoscale on queue age), shed low-priority jobs, or accept that some users are asked to retry. An unbounded queue would instead have grown to 16,000 and delayed everyone by 80 seconds. Use **queue age (time the oldest message has waited)** as the key metric, more telling than depth.
:::

Back pressure trades **availability for some users** for **latency and survival for the rest**. A rejected request that can be retried is usually better than an accepted one that times out.

## Consistency across services: outbox and sagas {#sec-outbox}

::: supplement
A very common bug: the service updates its database *and* publishes an event, as two separate steps. If it crashes between them, the database says "order placed" but no event goes out, or an event is published for an order that was rolled back. A database transaction cannot span the database and the broker.

**The transactional outbox pattern** fixes this. In **one local transaction** the service writes the business change *and* a row in an `outbox` table describing the event. A separate **relay** process reads unpublished outbox rows and publishes them to the broker, marking them sent. Delivery is at-least-once (the relay may publish, crash before marking, and publish again), so consumers deduplicate, as above. A variant uses **change data capture (CDC)**: tailing the database's write-ahead log to publish changes without a polling relay.

A **saga** coordinates a business workflow that spans several services without a distributed transaction. It is a sequence of local transactions, each with a **compensating action** that undoes it if a later step fails. For an order: reserve stock, charge payment, schedule shipping; if payment fails, release the stock. Sagas can be **choreographed** (each service reacts to the previous event) or **orchestrated** (a central coordinator tells each service what to do, which makes the flow easier to see and debug). Sagas give *eventual* consistency, not isolation: other users may briefly see intermediate states, so design the business process to tolerate it ("order pending"). Compensations must themselves be idempotent and retried until they succeed.
:::

{{fig outbox | Transactional outbox. The business row and the outbox row commit atomically; a relay publishes the outbox rows to the broker with at-least-once delivery.}}

{{fig saga | An orchestrated saga for an order. If charging the card fails, the orchestrator runs the compensating action for the stock reservation.}}

::: failure
**Failure modes.** A poison message blocking a queue; duplicate processing because acknowledgements were lost; lost messages because the consumer acknowledged before finishing; a growing queue (consumers slower than producers) that hides outages until the delay is hours; retry storms amplifying an outage; out-of-order processing corrupting state; a DLQ nobody watches; broker disk full or broker outage (decide whether producers buffer, fail, or fall back); a rebalance of consumers causing duplicate processing; workers that crash on startup in a loop.
:::

::: warning
**Common mistakes.** Treating a queue as a database. Acknowledging before the work is done. Assuming messages arrive once or in order. Unbounded retries or unbounded queues. Publishing events inside a database transaction without an outbox. Putting large payloads in messages (store the file in an object store and send its key).
:::

::: misconception
- *"A queue makes the system reliable."* It makes *slow or failing consumers* tolerable; it adds duplicates, ordering questions and a new component.
- *"Kafka (or any broker) gives exactly-once, so I need no idempotency."* Only within narrow boundaries; external side effects still need idempotency.
- *"Async is always faster."* Latency to *completion* is usually longer; only the user-visible response time improves.
- *"Dead-letter queues are a place to forget failures."* They are alarms; someone must own them.
:::

::: interview
**Q1. When would you use a queue?**
For work the user need not wait for, to absorb bursts, to decouple a slow or unreliable dependency, and to scale workers independently. Not when the user needs the result immediately and the work is fast.

**Q2. How do you handle duplicate messages?**
Assume at-least-once delivery; make consumers idempotent using a processed-ids table committed in the same transaction as the effect, conditional updates, or naturally idempotent operations.

**Q3. What is back pressure?**
A mechanism that refuses or slows producers when consumers cannot keep up, bounding queues and latency: 503 with Retry-After, blocking producers, or shedding low-priority work.

**Q4. How do you update the database and publish an event reliably?**
Transactional outbox (or CDC): write business data and an outbox row in one transaction, then a relay publishes it at least once; consumers deduplicate.
:::

::: exercise
1. A queue receives 500 messages/s; each worker handles 50 messages/s. How many workers keep up, and how many with 40% headroom?
2. Design the retry policy for a job that calls a flaky email API: delays, attempts, jitter, DLQ.
3. Explain precisely how a lost acknowledgement leads to a duplicate and show the dedup-table fix.
4. Sketch a saga for "book flight, book hotel, charge card" with compensations.

**Answers.**
1. 500 / 50 = 10 workers just to keep up; with 40% headroom, 10 / 0.6 ≈ 17 workers.
2. Example: up to 6 attempts with delays of about 2, 4, 8, 16, 32 s, each multiplied by a random factor between 0.5 and 1.5; classify 4xx responses as permanent (no retry); after the last attempt send to the DLQ with the error and alert; redrive after the API is fixed.
3. The worker finishes the effect and sends the ack; the ack is lost (network failure). The broker's visibility timeout expires and it redelivers the message. With a unique `processed(message_id)` row inserted in the same transaction as the effect, the second attempt's insert fails or finds the row, so the effect is skipped and the message is acknowledged.
4. Steps: book flight, book hotel, charge card. Compensations: cancel flight; cancel hotel; refund card. If the charge fails, run "cancel hotel" then "cancel flight"; each compensation is idempotent and retried until it succeeds.
:::

::: summary
- Asynchrony shortens user-visible latency, smooths bursts and decouples services, at the cost of eventual results and more moving parts.
- Queues hand each message to one consumer; pub/sub and logs deliver to every subscribing group; ordering is per partition.
- Assume at-least-once delivery; exactly-once effects come from idempotent consumers; external side effects remain a boundary.
- Retry with backoff and jitter, cap attempts, use and monitor dead-letter queues.
- Bound queues and apply back pressure; watch queue age.
- Use the outbox for atomic state-plus-event and sagas for multi-service workflows.
:::

::: revision
- [ ] I can explain at-most-once, at-least-once and the limit of exactly-once.
- [ ] I can write an idempotent consumer.
- [ ] I can compute a sensible queue bound.
- [ ] I can draw the outbox and a saga with compensations.
:::

::: supplement
**Further reading.** Kleppmann, *Designing Data-Intensive Applications*, chapters 11 and 12; Chris Richardson, *Microservices Patterns* (outbox, sagas); the Kafka documentation on delivery semantics; Marc Brooker's articles on timeouts, retries and backoff.
:::
