import random

# Definizione semi e ranghi
SUITS = ['hearts', 'diamonds', 'clubs', 'spades']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'jack', 'queen', 'king', 'ace']
VALUES = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 'jack': 10, 'queen': 10, 'king': 10, 'ace': 11}

class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit
        self.value = VALUES[rank]
        self.color = 'red' if suit in ['hearts', 'diamonds'] else 'black'

    def to_dict(self):
        return {"rank": self.rank, "suit": self.suit}

class Deck:
    def __init__(self, num_decks=4):
        self.cards = [Card(r, s) for _ in range(num_decks) for s in SUITS for r in RANKS]
        random.shuffle(self.cards)

    def draw(self):
        if len(self.cards) < 15: self.__init__()
        return self.cards.pop()

class Hand:
    def __init__(self, bet=0):
        self.cards = []
        self.bet = bet
        self.is_standing = False
        self.insurance_bet = 0

    def add_card(self, card):
        self.cards.append(card)

    def get_value(self):
        val = sum(c.value for c in self.cards)
        aces = sum(1 for c in self.cards if c.rank == 'ace')
        while val > 21 and aces > 0:
            val -= 10
            aces -= 1
        return val

    def is_bust(self):
        return self.get_value() > 21

    def check_perfect_pair(self):
        """Valuta la side bet sulle prime due carte"""
        if len(self.cards) != 2: return 0
        c1, c2 = self.cards[0], self.cards[1]
        if c1.rank == c2.rank:
            if c1.suit == c2.suit: return 25 # Perfect Pair
            if c1.color == c2.color: return 12 # Colored Pair
            return 6 # Mixed Pair
        return 0

    def to_dict(self):
        return {
            "cards": [c.to_dict() for c in self.cards],
            "value": self.get_value(),
            "bet": self.bet,
            "is_bust": self.is_bust(),
            "is_standing": self.is_standing,
            "insurance": self.insurance_bet
        }
