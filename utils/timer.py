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

    def __int__(self):
        return round(self.time)

    def __float__(self):
        return self.time

    def __str__(self):
        return str(self.__float__())

    @property
    def time(self):
        return self._end - self._start

    def __repr__(self):
        return f"<Timer time={self.time}, ms={self.ms}>"

    @property
    def ms(self):
        return self.time * 1000
