import time
from contextlib import contextmanager
from typing import Optional


class Timer:
    """Context manager that measures elapsed wall-clock time.

    - name: Optional text label printed on exit
    - elapsed: seconds since enter (during and after with-block)

    Usage:
        with Timer('My task') as t:
            do_work()
        # prints automatic report
        print(t.elapsed)
    """

    def __init__(self, name: Optional[str] = None):
        self.name = name
        self._start = None
        self._end = None

    def __enter__(self):
        self._start = time.monotonic()
        self._end = None
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._end = time.monotonic()
        if self.name:
            print(f"[Timer] {self.name}: {self.elapsed:.3f}s")
        # Do not suppress exceptions
        return False

    @property
    def elapsed(self) -> float:
        if self._start is None:
            raise RuntimeError("Timer has not been started")
        if self._end is None:
            return time.monotonic() - self._start
        return self._end - self._start


@contextmanager
def timer(name: Optional[str] = None):
    """Context manager function using contextlib.

    Returns an object with an .elapsed property that updates inside the block.
    """
    t = Timer(name=None)  # no auto-print inside this inner object
    t.__enter__()
    try:
        yield t
    finally:
        t.__exit__(None, None, None)
        if name:
            print(f"[Timer] {name}: {t.elapsed:.3f}s")


if __name__ == "__main__":
    # Quick manual checks
    print("Class-based Timer with name")
    with Timer("Procesamiento de datos") as t:
        datos = [x**2 for x in range(1000000)]

    print("Class-based Timer without name, elapsed after block")
    with Timer() as t:
        time.sleep(0.5)
    print(f"El bloque tardó {t.elapsed:.3f} segundos")

    print("Class-based Timer elapsed during block")
    with Timer() as t:
        time.sleep(0.2)
        print(f"Después del paso 1: {t.elapsed:.3f}s")
        time.sleep(0.2)
        print(f"Después del paso 2: {t.elapsed:.3f}s")

    print("contextlib@contextmanager Timer with name")
    with timer("Trabajando con contextlib") as t:
        time.sleep(0.25)
        print(f"Dentro: {t.elapsed:.3f}s")

    print("contextlib@contextmanager Timer without name")
    with timer() as t:
        time.sleep(0.3)
    print(f"Final: {t.elapsed:.3f}s")
