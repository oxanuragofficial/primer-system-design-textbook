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
