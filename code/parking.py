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
