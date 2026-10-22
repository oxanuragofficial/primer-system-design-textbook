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
