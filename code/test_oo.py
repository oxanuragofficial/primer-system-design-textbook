import random, pytest
from hashmap import HashMap
from lru import LRUCache
from callcenter import *
from cards import *
from parking import *
from chat import *
from circular import CircularBuffer

def test_hashmap_basic_collision_resize_missing():
    h = HashMap(size=5)
    for k, v in [(11, "a"), (18, "b"), (23, "c")]: h.set(k, v)   # 18 and 23 collide (mod 5 = 3)
    assert (h.get(18), h.get(23), len(h)) == ("b", "c", 3)
    h.set(18, "B"); assert h.get(18) == "B" and len(h) == 3        # update, not duplicate
    h.remove(18)
    with pytest.raises(KeyError): h.get(18)
    with pytest.raises(KeyError): h.remove(99)
    for k in range(100): h.set(k, k)                               # forces several resizes
    assert all(h.get(k) == k for k in range(100))
    assert len(h) == 100

def test_hashmap_random_vs_dict():
    rng, h, d = random.Random(1), HashMap(), {}
    for _ in range(3000):
        k = rng.randrange(200)
        if rng.random() < .6: h.set(k, k * 2); d[k] = k * 2
        elif k in d: h.remove(k); del d[k]
    assert len(h) == len(d) and all(h.get(k) == v for k, v in d.items())

def test_lru_eviction_order():
    c = LRUCache(3)
    c.put("A", 1); c.put("B", 2); c.put("C", 3)
    c.get("A"); c.put("D", 4)                  # evicts B
    assert c.get("B") is None
    c.put("E", 5)                              # evicts C
    assert c.keys_by_recency() == ["E", "D", "A"]

def test_lru_update_and_capacity_one():
    c = LRUCache(2); c.put("a", 1); c.put("a", 2)
    assert c.get("a") == 2 and c.keys_by_recency() == ["a"]
    d = LRUCache(1); d.put("x", 1); d.put("y", 2)
    assert d.get("x") is None and d.get("y") == 2
    with pytest.raises(ValueError): LRUCache(0)

def test_lru_random_vs_reference():
    from collections import OrderedDict
    rng, c, ref = random.Random(2), LRUCache(5), OrderedDict()
    for _ in range(5000):
        k = rng.randrange(12)
        if rng.random() < .5:
            c.put(k, k); ref[k] = k; ref.move_to_end(k)
            if len(ref) > 5: ref.popitem(last=False)
        else:
            got = c.get(k)
            assert got == ref.get(k)
            if k in ref: ref.move_to_end(k)
    assert c.keys_by_recency() == list(reversed(ref.keys()))

def test_callcenter_dispatch_escalate_queue():
    op, sup, dr = Employee("o", Rank.OPERATOR), Employee("s", Rank.SUPERVISOR), Employee("d", Rank.DIRECTOR)
    cc = CallCenter([op, sup, dr])
    c1, c2, c3, c4 = Call(1), Call(2), Call(3), Call(4)
    assert cc.dispatch(c1) is op and c1.state is CallState.IN_PROGRESS
    assert cc.dispatch(c2) is sup                       # operator busy -> supervisor
    assert cc.escalate(op) is dr and c1.min_rank is Rank.SUPERVISOR
    assert op.free and c1.handler is not None
    assert cc.dispatch(c3) is op                        # freed operator takes next call
    assert cc.dispatch(c4) is None and list(cc.queue) == [c4]
    nxt = cc.finish(sup)                                # supervisor frees -> takes queued call
    assert nxt is c4 and c2.state is CallState.COMPLETE
    with pytest.raises(ValueError): dr.escalate()

def test_callcenter_junior_cannot_take_senior_call():
    op = Employee("o", Rank.OPERATOR)
    with pytest.raises(AssertionError): op.take(Call(1, Rank.SUPERVISOR))

def test_blackjack_scores():
    S = Suit.SPADES
    h = BlackJackHand([BlackJackCard(1, S), BlackJackCard(13, S)])
    assert h.possible_scores() == [11, 21] and h.score() == 21
    h.add(BlackJackCard(5, S)); assert h.score() == 16            # ace now counts 1
    h.add(BlackJackCard(12, S)); assert h.score() == 26 and h.is_bust()
    two_aces = BlackJackHand([BlackJackCard(1, S), BlackJackCard(1, S)])
    assert two_aces.possible_scores() == [2, 12, 22] and two_aces.score() == 12

def test_deck():
    d = Deck(BlackJackCard, random.Random(3)); d.shuffle()
    seen = [d.deal() for _ in range(52)]
    assert len({(c.value, c.suit) for c in seen}) == 52 and d.remaining() == 0
    with pytest.raises(IndexError): d.deal()

def lot(n_spots=8, large_from=3):
    spots = [Spot(i, Size.LARGE if i >= large_from else Size.COMPACT) for i in range(n_spots)]
    return ParkingLot([Level(0, spots)]), spots

def test_parking_car_bus_and_leave():
    pl, spots = lot()
    car, bus = Car("C1"), Bus("B1")
    assert pl.park(car) and spots[0].vehicle is car
    assert pl.park(bus)                                          # needs 5 consecutive LARGE: spots 3..7
    assert [s.number for s in bus.spots] == [3, 4, 5, 6, 7]
    assert not pl.park(Bus("B2"))                                # no second run
    pl.leave(bus); assert all(s.is_free() for s in spots[3:])
    assert pl.park(Bus("B3"))
    with pytest.raises(ValueError): pl.leave(Car("never parked"))

def test_parking_bus_needs_contiguous_large():
    spots = [Spot(i, Size.LARGE) for i in range(6)]
    pl = ParkingLot([Level(0, spots)])
    pl.park(Motorcycle("M"))                                     # takes spot 0
    spots[2].vehicle = object()                                  # block the middle
    assert not pl.park(Bus("B"))

def test_chat_friend_flow_and_membership():
    us = UserService(); a, b, c = us.add_user(1, "a"), us.add_user(2, "b"), us.add_user(3, "c")
    with pytest.raises(PermissionError): us.private_chat(1, 2)   # not friends yet
    req = us.request_friend(1, 2); us.answer(req, True)
    assert 2 in a.friends and 1 in b.friends
    with pytest.raises(ValueError): us.answer(req, True)         # already answered
    chat = us.private_chat(1, 2); chat.post(a, "hi")
    with pytest.raises(PermissionError): chat.post(c, "intruder")
    assert chat.messages[0].text == "hi" and chat in b.chats
    with pytest.raises(ValueError): PrivateChat(a, a)
    g = GroupChat([a, b]); g.add_user(c); g.add_user(c)
    assert len(g.users) == 3

def test_circular_buffer():
    cb = CircularBuffer(3)
    for i in range(3): cb.push(i)
    with pytest.raises(OverflowError): cb.push(9)
    assert [cb.pop(), cb.pop()] == [0, 1]
    cb.push(3); cb.push(4)                                       # wraps around
    assert [cb.pop(), cb.pop(), cb.pop()] == [2, 3, 4]
    with pytest.raises(IndexError): cb.pop()
    ow = CircularBuffer(2, overwrite=True)
    for i in range(5): ow.push(i)
    assert [ow.pop(), ow.pop()] == [3, 4]
