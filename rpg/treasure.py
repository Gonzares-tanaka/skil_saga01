"""Session-only expedition treasure; only secured treasure can be spent."""
from dataclasses import dataclass


@dataclass
class Treasure:
    unbanked: int = 0
    banked: int = 0

    def secure(self):
        amount = self.unbanked
        self.banked += amount
        self.unbanked = 0
        return amount

    def lose(self):
        amount = self.unbanked
        self.unbanked = 0
        return amount
