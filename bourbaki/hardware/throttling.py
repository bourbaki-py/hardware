# coding:utf-8
from typing import Iterable, Iterator, Callable, Generic, TypeVar

from bisect import bisect_left
from collections import deque
from functools import update_wrapper
from time import time, sleep

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)


def throttled(it: Iterable[T], n: int, t: float = 1.0) -> Iterator[T]:
    q = deque()
    for i in it:
        if len(q) >= n:
            first, last, now = q[0], q[-1], time()
            for _ in range(min(bisect_left(q, now - t), len(q))):
                q.popleft()
            sleeptime = t - (time() - first)
            if sleeptime > 0:
                sleep(sleeptime)
        q.append(time())
        yield i


class sleepy(Generic[T_contra, T_co]):
    def __init__(self, f: Callable[[T_contra], T_co], rand: Callable[[], float]):
        self.f = f
        update_wrapper(self, f)
        self.rand = rand

    def __call__(self, *args, **kwargs) -> T_co:
        sleep(self.rand())
        return self.f(*args, **kwargs)
