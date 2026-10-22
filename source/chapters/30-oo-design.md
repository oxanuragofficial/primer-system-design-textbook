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

```python
class HashMap:
    """Chained hash map for integer keys. Invariant: every item sits in bucket key % size."""
    def __init__(self, size=8, max_load=0.75):
        self._buckets = [[] for _ in range(size)]
        self._count = 0
        self._max_load = max_load

    def _bucket(self, key):
        return self._buckets[key % len(self._buckets)]

    def set(self, key, value):
        bucket = self._bucket(key)
        for i, (k, _) in enumerate(bucket):
            if k == key:
                bucket[i] = (key, value)       # update in place
                return
        bucket.append((key, value))
        self._count += 1
        if self._count / len(self._buckets) > self._max_load:
            self._resize(2 * len(self._buckets))

    def get(self, key):
        for k, v in self._bucket(key):
            if k == key:
                return v
        raise KeyError(key)

    def remove(self, key):
        bucket = self._bucket(key)
        for i, (k, _) in enumerate(bucket):
            if k == key:
                del bucket[i]
                self._count -= 1
                return
        raise KeyError(key)

    def _resize(self, new_size):
        items = [kv for b in self._buckets for kv in b]
        self._buckets = [[] for _ in range(new_size)]
        for k, v in items:                      # rehash every item
            self._bucket(k).append((k, v))

    def __len__(self):
        return self._count
```

**Complexity.** Average O(1) per operation for well-spread keys; O(n) worst case when all keys land in one bucket. Resizing is O(n) but amortised O(1) per insert because capacity doubles. **Tests** cover collision, update-not-duplicate, missing keys, forced resizes, and a randomised comparison with Python's `dict`. **Extensions:** string keys with a better hash, open addressing, shrinking, thread safety by lock striping.

## Design 2: LRU cache {#sec-oo-lru}

The same structure as the query cache (Chapter {ch:ch-querycache}), now seen as classes: `LRUCache` composes a dictionary and a doubly linked list of nodes.

{{fig oo-lru | LRU cache classes. The cache owns a map and the list; nodes store the key so eviction can also delete the map entry.}}

**Design note (a flaw in the skeleton we started from).** The notebook's node stores only the results. Eviction needs the evicted node's **key** (to delete it from the map) and unlinking from the middle needs a **previous pointer**. The reference node below stores both.

```python
class _Node:
    __slots__ = ("key", "value", "prev", "next")
    def __init__(self, key=None, value=None):
        self.key, self.value, self.prev, self.next = key, value, None, None

class LRUCache:
    """O(1) get/put. Invariants: len(map) <= capacity; list order == recency order."""
    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self._map = {}
        self._head, self._tail = _Node(), _Node()      # sentinels
        self._head.next, self._tail.prev = self._tail, self._head

    def _unlink(self, n):
        n.prev.next, n.next.prev = n.next, n.prev

    def _push_front(self, n):
        n.prev, n.next = self._head, self._head.next
        self._head.next.prev = n
        self._head.next = n

    def get(self, key):
        n = self._map.get(key)
        if n is None:
            return None
        self._unlink(n); self._push_front(n)
        return n.value

    def put(self, key, value):
        n = self._map.get(key)
        if n is not None:
            n.value = value
            self._unlink(n); self._push_front(n)
            return
        if len(self._map) >= self.capacity:
            lru = self._tail.prev
            self._unlink(lru)
            del self._map[lru.key]                      # evict from list AND map
        n = _Node(key, value)
        self._map[key] = n
        self._push_front(n)

    def keys_by_recency(self):
        out, n = [], self._head.next
        while n is not self._tail:
            out.append(n.key); n = n.next
        return out
```

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

```python
from collections import deque
from enum import Enum

class Rank(Enum):
    OPERATOR = 0
    SUPERVISOR = 1
    DIRECTOR = 2

class CallState(Enum):
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"

class Call:
    def __init__(self, call_id, min_rank=Rank.OPERATOR):
        self.id, self.min_rank = call_id, min_rank
        self.state, self.handler = CallState.READY, None

class Employee:
    def __init__(self, name, rank):
        self.name, self.rank, self.call = name, rank, None

    @property
    def free(self):
        return self.call is None

    def take(self, call):
        assert self.free and call.state is CallState.READY
        assert call.min_rank.value <= self.rank.value, "employee too junior"
        self.call, call.handler, call.state = call, self, CallState.IN_PROGRESS

    def complete(self):
        call, self.call = self.call, None
        call.state, call.handler = CallState.COMPLETE, None
        return call

    def escalate(self):
        """Return the call to READY at the next rank; directors cannot escalate."""
        if self.rank is Rank.DIRECTOR:
            raise ValueError("directors cannot escalate")
        call, self.call = self.call, None
        call.state, call.handler = CallState.READY, None
        call.min_rank = Rank(self.rank.value + 1)
        return call

class CallCenter:
    def __init__(self, employees):
        self.employees = list(employees)
        self.queue = deque()

    def dispatch(self, call):
        for rank in Rank:                                   # lowest rank first
            if rank.value < call.min_rank.value:
                continue
            for e in self.employees:
                if e.rank is rank and e.free:
                    e.take(call)
                    return e
        self.queue.append(call)                             # nobody free
        return None

    def finish(self, employee):
        employee.complete()
        return self._assign_next(employee)

    def escalate(self, employee):
        call = employee.escalate()
        return self.dispatch(call)

    def _assign_next(self, employee):
        for _ in range(len(self.queue)):                    # first queued call this person may take
            call = self.queue.popleft()
            if call.min_rank.value <= employee.rank.value:
                employee.take(call)
                return call
            self.queue.append(call)
        return None
```

**Flaws in the notebook skeleton, fixed here.** Its subclasses did not pass the call-center argument to the base constructor and two called `super()` with the wrong class; here ranks are an enum and there is one `Employee` class, so subclasses are unnecessary (behaviour differs only by rank data). Mention that inheritance would be justified only if ranks had different *behaviour*. **Extensions:** VIP calls with priority queues, skill routing, fairness (longest idle first), concurrency control on dispatch.

## Design 4: Deck of cards and blackjack {#sec-oo-deck}

**Assumptions.** A generic 52-card deck usable for several games; design the generic layer first then extend for blackjack (face cards count 10; an ace counts 1 or 11).

{{fig oo-deck | Generic Card, Hand and Deck, with blackjack specialisations.}}

**Responsibilities.** `Deck` owns the cards and a **deal index** (dealing never removes cards, so `remaining = 52 - deal_index`); `Hand` holds cards; `BlackJackHand` computes all possible scores and picks the best; `BlackJackCard` knows points and aces.

**Invariants.** A full deck has exactly 52 distinct cards; `0 <= deal_index <= 52`; a hand's score is the largest possible total at most 21, or the smallest total if all exceed 21.

```python
import random
from enum import Enum

class Suit(Enum):
    CLUBS, DIAMONDS, HEARTS, SPADES = range(4)

class Card:
    def __init__(self, value, suit):               # value: 1..13 (1 = ace, 11-13 = J, Q, K)
        assert 1 <= value <= 13
        self.value, self.suit = value, suit

class BlackJackCard(Card):
    def is_ace(self):
        return self.value == 1
    def is_face(self):
        return 11 <= self.value <= 13
    def points(self):
        return 10 if self.is_face() else self.value   # ace counted as 1 here

class Hand:
    def __init__(self, cards=None):
        self.cards = list(cards or [])
    def add(self, card):
        self.cards.append(card)

class BlackJackHand(Hand):
    def possible_scores(self):
        base = sum(c.points() for c in self.cards)
        aces = sum(1 for c in self.cards if c.is_ace())
        return sorted({base + 10 * k for k in range(aces + 1)})   # each ace may add 10 more
    def score(self):
        scores = self.possible_scores()
        under = [s for s in scores if s <= 21]
        return max(under) if under else min(scores)
    def is_bust(self):
        return self.score() > 21

class Deck:
    def __init__(self, card_cls=Card, rng=None):
        self.cards = [card_cls(v, s) for s in Suit for v in range(1, 14)]
        self.deal_index = 0
        self._rng = rng or random.Random()
    def remaining(self):
        return len(self.cards) - self.deal_index
    def shuffle(self):
        self._rng.shuffle(self.cards)
        self.deal_index = 0
    def deal(self):
        if self.remaining() == 0:
            raise IndexError("deck is empty")
        card = self.cards[self.deal_index]
        self.deal_index += 1
        return card
```

**Why the ace logic works.** Count every ace as 1, then each ace may add 10: with *k* aces there are *k + 1* totals, not 2ᵏ, because only the **number** of aces counted as 11 matters. Two aces give 2, 12 or 22. **Extensions:** multi-deck shoe with a cut card, split and double-down, dealer rules, secure shuffling (use a cryptographic source for real money games).

## Design 5: Parking lot {#sec-oo-lot}

**Assumptions.** Several levels, each a row of spots of size compact or large. A motorcycle fits any spot, a car fits compact or large, a bus needs **five consecutive large spots**.

{{fig oo-lot | Parking lot classes. Vehicle subclasses encode fit rules and how many spots they need.}}

**Responsibilities.** `ParkingLot` asks each `Level` to park; a `Level` searches for a window of adjacent free spots that all fit; the `Vehicle` remembers its spots so leaving frees exactly those. Polymorphism (`can_fit`, `spots_needed`) removes any `if bus ... elif car ...` chain.

**Invariants.** A spot holds at most one vehicle; a parked vehicle's `spots` are exactly the spots that reference it; a vehicle is parked at most once.

```python
from enum import Enum

class Size(Enum):
    COMPACT = 1
    LARGE = 2

class Vehicle:
    spots_needed = 1
    def __init__(self, plate):
        self.plate, self.spots = plate, []
    def can_fit(self, spot):
        raise NotImplementedError

class Motorcycle(Vehicle):
    def can_fit(self, spot): return True

class Car(Vehicle):
    def can_fit(self, spot): return True          # compact or large

class Bus(Vehicle):
    spots_needed = 5
    def can_fit(self, spot): return spot.size is Size.LARGE

class Spot:
    def __init__(self, number, size):
        self.number, self.size, self.vehicle = number, size, None
    def is_free(self):
        return self.vehicle is None

class Level:
    def __init__(self, floor, spots):
        self.floor, self.spots = floor, spots
    def available(self):
        return sum(s.is_free() for s in self.spots)
    def park(self, v):
        need = v.spots_needed
        for i in range(len(self.spots) - need + 1):           # window of `need` adjacent spots
            window = self.spots[i:i + need]
            if all(s.is_free() and v.can_fit(s) for s in window):
                for s in window:
                    s.vehicle = v
                v.spots = window
                return True
        return False

class ParkingLot:
    def __init__(self, levels):
        self.levels = levels
    def park(self, v):
        if v.spots:
            raise ValueError("already parked")
        return any(level.park(v) for level in self.levels)
    def leave(self, v):
        if not v.spots:
            raise ValueError("not parked")
        for s in v.spots:
            s.vehicle = None
        v.spots = []
```

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

```python
from enum import Enum
from itertools import count

class RequestStatus(Enum):
    UNREAD = 0
    ACCEPTED = 1
    REJECTED = 2

class Message:
    _ids = count(1)
    def __init__(self, sender_id, text):
        self.id, self.sender_id, self.text = next(Message._ids), sender_id, text

class Chat:
    _ids = count(1)
    def __init__(self, users):
        self.id, self.users, self.messages = next(Chat._ids), list(users), []
    def post(self, sender, text):
        if sender not in self.users:
            raise PermissionError("not a member")
        m = Message(sender.id, text)
        self.messages.append(m)
        return m

class PrivateChat(Chat):
    def __init__(self, a, b):
        if a is b:
            raise ValueError("a private chat needs two different users")
        super().__init__([a, b])

class GroupChat(Chat):
    def add_user(self, user):
        if user not in self.users:
            self.users.append(user)
    def remove_user(self, user):
        self.users.remove(user)

class AddRequest:
    def __init__(self, from_user, to_user):
        self.from_user, self.to_user = from_user, to_user
        self.status = RequestStatus.UNREAD

class User:
    def __init__(self, user_id, name):
        self.id, self.name = user_id, name
        self.friends, self.chats, self.incoming = {}, [], []

class UserService:
    def __init__(self):
        self.users = {}
    def add_user(self, user_id, name):
        if user_id in self.users:
            raise ValueError("duplicate id")
        self.users[user_id] = User(user_id, name)
        return self.users[user_id]
    def request_friend(self, from_id, to_id):
        a, b = self.users[from_id], self.users[to_id]
        if a is b or b.id in a.friends:
            raise ValueError("invalid request")
        req = AddRequest(a, b)
        b.incoming.append(req)
        return req
    def answer(self, req, accept):
        if req.status is not RequestStatus.UNREAD:
            raise ValueError("already answered")
        if accept:
            req.status = RequestStatus.ACCEPTED
            req.from_user.friends[req.to_user.id] = req.to_user      # friendship is symmetric
            req.to_user.friends[req.from_user.id] = req.from_user
        else:
            req.status = RequestStatus.REJECTED
    def private_chat(self, a_id, b_id):
        a, b = self.users[a_id], self.users[b_id]
        if b.id not in a.friends:
            raise PermissionError("not friends")
        chat = PrivateChat(a, b)
        a.chats.append(chat); b.chats.append(chat)
        return chat
```

**Scaling it later (not asked now).** Shard users by id, keep persistent connections for push delivery, store history in a wide-column store keyed by chat and time, and use per-user queues for offline delivery (Chapters {ch:ch-nosql} and {ch:ch-async}). The in-memory objects become rows and the invariants become constraints and idempotent operations.

## Exercise from the notebook: a circular array {#sec-oo-circ}

The original lists "design a circular array" as an open exercise. A fixed array plus a head index and a size gives a FIFO buffer with O(1) push and pop; indices wrap by modulo. The one decision to state aloud is **what happens when full**: reject (raise) or overwrite the oldest.

```python
class CircularBuffer:
    """Fixed-capacity FIFO. Invariants: 0 <= size <= cap; items are at head, head+1, ... modulo cap."""
    def __init__(self, cap, overwrite=False):
        self._a, self._cap, self._head, self._size = [None] * cap, cap, 0, 0
        self._overwrite = overwrite
    def push(self, x):
        if self._size == self._cap:
            if not self._overwrite:
                raise OverflowError("full")
            self._head = (self._head + 1) % self._cap          # drop the oldest
            self._size -= 1
        self._a[(self._head + self._size) % self._cap] = x
        self._size += 1
    def pop(self):
        if self._size == 0:
            raise IndexError("empty")
        x = self._a[self._head]
        self._a[self._head] = None
        self._head = (self._head + 1) % self._cap
        self._size -= 1
        return x
    def __len__(self):
        return self._size
```

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
