#!/usr/bin/env python3
"""Pipeline de 3 etapas con multiprocessing y señales de fin."""
from multiprocessing import Process, Queue
import time

def etapa_multiplicar(input_q, output_q):
    while True:
        item = input_q.get() # Bloqueante si no hay datos
        if item is None:
            output_q.put(None) # Pasamos la "píldora de veneno" a la etapa 2
            break
        time.sleep(0.02) # Simulación de costo de E/S o CPU
        output_q.put(item * 2)

def etapa_sumar(input_q, output_q):
    while True:
        item = input_q.get()
        if item is None:
            output_q.put(None) # Pasamos la señal a la etapa 3
            break
        time.sleep(0.02)
        output_q.put(item + 10)

def etapa_formatear(input_q, output_q):
    while True:
        item = input_q.get()
        if item is None:
            output_q.put(None) # Indicamos al proceso padre el fin del canal
            break
        time.sleep(0.02)
        output_q.put(f"resultado_{item:03d}")

if __name__ == "__main__":
    # Creamos las colas que conectarán los eslabones de la cadena
    q1, q2, q3, q4 = Queue(), Queue(), Queue(), Queue()

    p1 = Process(target=etapa_multiplicar, args=(q1, q2))
    p2 = Process(target=etapa_sumar, args=(q2, q3))
    p3 = Process(target=etapa_formatear, args=(q3, q4))

    p1.start(); p2.start(); p3.start()

    # Alimentar el pipeline desde el proceso principal
    print("Inyectando 10 números al pipeline...")
    for i in range(10):
        q1.put(i)
    q1.put(None) # Inyección del centinela de apagado

    # Recoger y mostrar los resultados finales desde q4
    while True:
        result = q4.get()
        if result is None:
            break
        print(f"Final en proceso padre: {result}")

    p1.join(); p2.join(); p3.join()
    print("Pipeline apagado limpiamente.")