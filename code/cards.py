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
