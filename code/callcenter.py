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
