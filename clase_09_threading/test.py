import threading
import time
import random

# Barrera para 4 threads
barrera = threading.Barrier(4)

def fase(id):
    # Fase 1
    print(f"[{id}] Fase 1: trabajando...")
    time.sleep(random.uniform(0.5, 1.5))
    print(f"[{id}] Fase 1: completada, esperando en barrera...")
    barrera.wait()  # espera a que los 4 lleguen

    # Fase 2
    print(f"[{id}] Fase 2: trabajando...")
    time.sleep(random.uniform(0.5, 1.5))
    print(f"[{id}] Fase 2: completada, esperando en barrera...")
    barrera.wait()  # espera a que los 4 lleguen

    print(f"[{id}] Todas las fases completadas")


hilos = [threading.Thread(target=fase, args=(i,)) for i in range(5)]
for t in hilos: t.start()
for t in hilos: t.join()