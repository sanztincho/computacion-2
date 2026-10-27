import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def tarea(n):
    time.sleep(n)  
    return n * n

if __name__ == "__main__":                   # necesario para ProcessPoolExecutor
    with ThreadPoolExecutor(4) as pool:
        futuros = [pool.submit(tarea, n) for n in [1, 5, 2, 4]]
        for futuro in as_completed(futuros):
            print(futuro.result())


