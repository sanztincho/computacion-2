#!/usr/bin/env python3
"""Usar Manager para compartir estructuras complejas."""
from multiprocessing import Process, Manager
import time
import random

def worker(shared_dict, shared_list, id):
    # Simular trabajo de duración variable
    duracion = random.uniform(0.2, 1.0)
    time.sleep(duracion)

    # Modificar diccionario compartido
    shared_dict[f"worker_{id}"] = {
        "status": "done",
        "result": id ** 2,
        "duracion": round(duracion, 2)
    }

    # Agregar a lista compartida
    shared_list.append(f"Worker {id} completó en {duracion:.2f}s")

if __name__ == "__main__":
    with Manager() as manager:
        d = manager.dict()
        l = manager.list()

        procs = [Process(target=worker, args=(d, l, i)) for i in range(5)]

        for p in procs:
            p.start()
        for p in procs:
            p.join()

        print("Diccionario compartido:")
        for k, v in d.items():
            print(f"  {k}: {v}")

        print("\nLista compartida (orden de finalización):")
        for item in l:
            print(f"  {item}")