import time


class Timer:
    def __init__(self):
        self._start = None
        self._end = None

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self._end = time.perf_counter()
        self.elapsed = self._end - self._start
        self.ms = self.elapsed * 1000

    def __int__(self):
        return round(self.elapsed)

    def __float__(self):
        return self.elapsed

    def __str__(self):
        return str(self.__float__())

    def __repr__(self):
        return f"<Timer elapsed={self.elapsed}, ms={self.ms}>"

