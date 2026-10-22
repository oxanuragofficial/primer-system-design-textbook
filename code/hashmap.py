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
