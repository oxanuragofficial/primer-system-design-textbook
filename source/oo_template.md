%part Part VIII | Object-Oriented Design | Turning requirements into classes, state machines and tested code.
%derived Notebook chapter 13 (object-oriented design: method, then hash map, LRU cache, call center, deck of cards and blackjack, parking lot, online chat, and the open circular-array exercise)
%added explicit responsibilities, invariants, state transitions, runnable reference code and unit tests for every design; resize in the hash map; corrections to the skeleton code in the original exercises
# Object-Oriented Design Exercises {#ch-oo-ds}

::: objectives
After this chapter you can:

- follow a repeatable method from vague requirement to classes, relationships and behaviour;
- state each class's responsibility and the invariants it protects;
- model state with enums and transitions instead of flags;
- implement six classic designs and the circular buffer, and test them;
- spot common design flaws such as missing back-pointers, wrong super calls and hidden state.
:::

::: prereq
Chapter {ch:ch-ds} (hash tables, linked lists, queues) and Chapter {ch:ch-concurrency} for the thread-safety remarks.
:::

## Method {#sec-oo-method}

1. **Clarify** scope, valid inputs and constraints (fits in memory? thread safety? scale?). Write assumptions down.
2. **Find nouns and verbs.** Nouns become candidate classes, verbs become methods. Decide *is-a* (inheritance) versus *has-a* (composition); prefer composition unless subtypes truly behave differently.
3. **Assign responsibilities.** Each class has one reason to change and protects its own **invariants** (facts that must always be true).
4. **Model state explicitly** with enums and a transition table, rather than booleans scattered around.
5. **Choose data structures** that make the key operation cheap.
6. **Walk through scenarios**, including edge cases, then **test**: one test per invariant and per transition, plus a randomised comparison against a trusted reference where one exists.

All code in this chapter is Python 3, was run, and passes its 13 tests (the test file is shipped with the book sources). Code is a reference for the interview whiteboard: it favours clarity over production hardening, and thread safety is discussed rather than implemented unless stated.

## Design 1: Hash map {#sec-oo-hash}

**Assumptions.** Integer keys, collisions resolved by **chaining**, resize when the load factor passes 0.75, valid input, all in memory.

{{fig oo-hash | Hash map with chaining: key mod size selects a bucket; colliding keys share a chain.}}

**Responsibilities.** `HashMap` owns the bucket array and the item count. `set` updates or inserts; `get` and `remove` scan one bucket and raise `KeyError` if absent; `_resize` rehashes everything.

**Invariants.** (1) every item is in bucket `key % size`; (2) no key appears twice; (3) `count` equals the total number of items; (4) load factor stays at or below the limit after `set`.

@@hashmap.py@@

**Complexity.** Average O(1) per operation for well-spread keys; O(n) worst case when all keys land in one bucket. Resizing is O(n) but amortised O(1) per insert because capacity doubles. **Tests** cover collision, update-not-duplicate, missing keys, forced resizes, and a randomised comparison with Python's `dict`. **Extensions:** string keys with a better hash, open addressing, shrinking, thread safety by lock striping.

## Design 2: LRU cache {#sec-oo-lru}

The same structure as the query cache (Chapter {ch:ch-querycache}), now seen as classes: `LRUCache` composes a dictionary and a doubly linked list of nodes.

{{fig oo-lru | LRU cache classes. The cache owns a map and the list; nodes store the key so eviction can also delete the map entry.}}

**Design note (a flaw in the skeleton we started from).** The notebook's node stores only the results. Eviction needs the evicted node's **key** (to delete it from the map) and unlinking from the middle needs a **previous pointer**. The reference node below stores both.

@@lru.py@@

**Invariants.** `len(map) <= capacity`; every list node is in the map under its own key; list order equals recency order (head newest). **State transition** per operation: hit moves the node to the front; insert at capacity removes the tail first. **Thread safety:** wrap each public method in a lock (even `get` mutates the list), or shard keys over several caches.

## Design 3: Call center {#sec-oo-call}

**Assumptions.** Three ranks (operator, supervisor, director). A call goes to a free operator first; if none is free it goes to a supervisor, then a director. An employee may **escalate** a call, which raises the call's minimum rank and re-dispatches it. If nobody eligible is free the call is **queued** and assigned when someone frees up. Directors cannot escalate.

{{fig oo-call | Call center classes and call state machine (READY, IN_PROGRESS, COMPLETE).}}

Table[oo-call-state]: Call state transitions.

| From | Event | To | Guard |
|---|---|---|---|
| READY | employee takes call | IN_PROGRESS | employee free and rank at least `min_rank` |
| IN_PROGRESS | employee completes | COMPLETE | none |
| IN_PROGRESS | employee escalates | READY (rank raised) | handler is not a director |
| READY | no eligible employee free | READY (queued) | none |

**Invariants.** An employee has at most one call; a call has at most one handler; `IN_PROGRESS` implies a handler, other states imply none; an employee never holds a call above their rank.

@@callcenter.py@@

**Flaws in the notebook skeleton, fixed here.** Its subclasses did not pass the call-center argument to the base constructor and two called `super()` with the wrong class; here ranks are an enum and there is one `Employee` class, so subclasses are unnecessary (behaviour differs only by rank data). Mention that inheritance would be justified only if ranks had different *behaviour*. **Extensions:** VIP calls with priority queues, skill routing, fairness (longest idle first), concurrency control on dispatch.

## Design 4: Deck of cards and blackjack {#sec-oo-deck}

**Assumptions.** A generic 52-card deck usable for several games; design the generic layer first then extend for blackjack (face cards count 10; an ace counts 1 or 11).

{{fig oo-deck | Generic Card, Hand and Deck, with blackjack specialisations.}}

**Responsibilities.** `Deck` owns the cards and a **deal index** (dealing never removes cards, so `remaining = 52 - deal_index`); `Hand` holds cards; `BlackJackHand` computes all possible scores and picks the best; `BlackJackCard` knows points and aces.

**Invariants.** A full deck has exactly 52 distinct cards; `0 <= deal_index <= 52`; a hand's score is the largest possible total at most 21, or the smallest total if all exceed 21.

@@cards.py@@

**Why the ace logic works.** Count every ace as 1, then each ace may add 10: with *k* aces there are *k + 1* totals, not 2ᵏ, because only the **number** of aces counted as 11 matters. Two aces give 2, 12 or 22. **Extensions:** multi-deck shoe with a cut card, split and double-down, dealer rules, secure shuffling (use a cryptographic source for real money games).

## Design 5: Parking lot {#sec-oo-lot}

**Assumptions.** Several levels, each a row of spots of size compact or large. A motorcycle fits any spot, a car fits compact or large, a bus needs **five consecutive large spots**.

{{fig oo-lot | Parking lot classes. Vehicle subclasses encode fit rules and how many spots they need.}}

**Responsibilities.** `ParkingLot` asks each `Level` to park; a `Level` searches for a window of adjacent free spots that all fit; the `Vehicle` remembers its spots so leaving frees exactly those. Polymorphism (`can_fit`, `spots_needed`) removes any `if bus ... elif car ...` chain.

**Invariants.** A spot holds at most one vehicle; a parked vehicle's `spots` are exactly the spots that reference it; a vehicle is parked at most once.

@@parking.py@@

**Complexity.** Parking scans each level in O(spots × window). A per-level free counter lets full levels be skipped; for large lots keep free spots indexed by size. **Extensions:** pricing and tickets, nearest-to-entrance search, reservations and electric-vehicle spots, concurrency (two cars choosing the same spot), a state machine for a spot (FREE, RESERVED, OCCUPIED, OUT_OF_SERVICE).

## Design 6: Online chat {#sec-oo-chat}

**Scope.** Text only. Users can be added, send and answer **friend requests**, create private chats with friends, and group chats. No scaling concerns yet.

{{fig oo-chat | Chat classes: UserService as entry point; abstract Chat with PrivateChat and GroupChat; requests have a status.}}

Table[oo-chat-state]: Friend request status transitions.

| From | Event | To |
|---|---|---|
| UNREAD | recipient accepts | ACCEPTED (friendship added to both users) |
| UNREAD | recipient rejects | REJECTED |
| ACCEPTED or REJECTED | any answer | error: already answered |

**Invariants.** Friendship is symmetric; a private chat has exactly two distinct users who are friends; only members can post; a request is answered at most once.

@@chat.py@@

**Scaling it later (not asked now).** Shard users by id, keep persistent connections for push delivery, store history in a wide-column store keyed by chat and time, and use per-user queues for offline delivery (Chapters {ch:ch-nosql} and {ch:ch-async}). The in-memory objects become rows and the invariants become constraints and idempotent operations.

## Exercise from the notebook: a circular array {#sec-oo-circ}

The original lists "design a circular array" as an open exercise. A fixed array plus a head index and a size gives a FIFO buffer with O(1) push and pop; indices wrap by modulo. The one decision to state aloud is **what happens when full**: reject (raise) or overwrite the oldest.

@@circular.py@@

## Tests and what they prove {#sec-oo-tests}

The test file contains 13 tests: hash map (basic, collision, update, resize, randomised against `dict`), LRU (eviction order, update, capacity one, randomised against an ordered-dictionary reference), call center (dispatch, escalation, queue, junior restriction), blackjack (ace totals, bust, two aces), deck (52 distinct cards, exhaustion), parking (car, bus, leave, contiguity), chat (friend flow, membership, group) and the circular buffer (wrap-around, full, overwrite). **Honest scope:** the tests exercise single-threaded behaviour; none tests concurrency, and the randomised tests use fixed seeds.

::: misconception
- *"More classes means better design."* Create a class when it owns a responsibility or invariant.
- *"Inheritance models every difference."* Use data (an enum) when behaviour is the same.
- *"Working code means correct design."* Check invariants and edge cases.
:::

::: interview
**Q1. How do you start an OO design question?** Clarify, list nouns and verbs, assign responsibilities, state invariants, choose data structures, walk through scenarios.

**Q2. Inheritance or composition?** Composition by default; inheritance when subtypes have different behaviour behind one interface (vehicles' fit rules).

**Q3. How would you make the call center thread-safe?** One lock around dispatch and state changes (or per-employee locks with ordered acquisition) so a call is never assigned twice.

**Q4. Why does the LRU node store its key?** So eviction can remove the map entry.
:::

::: exercise
1. Add `resize` shrinking to `HashMap` when the load factor falls below 0.2. State the invariant you must preserve.
2. A bus parks, then a car leaves a compact spot in the middle of the lot. Does the bus's allocation change? Explain.
3. Write the transition table for a parking `Spot` with states FREE, RESERVED, OCCUPIED, OUT_OF_SERVICE.
4. Two operators finish at the same moment while one call is queued. What can go wrong without a lock, and what is the fix?

**Answers.**
1. Shrink by rebuilding with half the buckets when `count / size < 0.2` and size above a minimum; the invariant is that every item stays in bucket `key % new_size`, achieved by rehashing all items.
2. No: the bus's `spots` are the five spots it was given; freeing a different spot touches only the car's allocation.
3. FREE → RESERVED (reserve); RESERVED → OCCUPIED (arrive), RESERVED → FREE (cancel or timeout); OCCUPIED → FREE (leave); any → OUT_OF_SERVICE (maintenance); OUT_OF_SERVICE → FREE (repaired).
4. Both could pop the same queued call and both take it, violating one handler per call; guard dequeue and assignment with a lock (or use an atomic queue pop that returns a call to only one caller).
:::

::: summary
- Method: clarify, nouns and verbs, responsibilities, invariants, state enums, data structures, scenarios, tests.
- Hash map, LRU, call center, deck, parking lot, chat and circular buffer are small designs with clear invariants.
- Fix the flaws in skeletons: LRU nodes need key and previous pointer; avoid needless subclasses.
- Tests per invariant and transition, plus randomised comparisons, give real confidence.
:::

::: revision
- [ ] I can write the LRU cache and the hash map from memory.
- [ ] I can state invariants for each design.
- [ ] I can draw the call and request state transitions.
- [ ] I can explain when to use inheritance versus data.
:::
