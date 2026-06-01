#!/usr/bin/env python3
"""Procesador de imágenes paralelo utilizando Pool.map."""
from multiprocessing import Pool
import time
import random

def crear_imagen(size):
    return [[random.randint(0, 255) for _ in range(size)] for _ in range(size)]

def aplicar_filtro(imagen):
    """Aplica un filtro blur 3x3 (CPU-intensive)."""
    size = len(imagen)
    resultado = [[0] * size for _ in range(size)]

    for i in range(1, size - 1):
        for j in range(1, size - 1):
            suma = 0
            for di in [-1, 0, 1]:
                for dj in [-1, 0, 1]:
                    suma += imagen[i + di][j + dj]
            resultado[i][j] = suma // 9
    return resultado

def procesar_imagen(args):
    """Procesa una imagen y devuelve métricas."""
    idx, imagen = args
    inicio = time.time()
    resultado = aplicar_filtro(imagen)
    duracion = time.time() - inicio
    return idx, duracion, sum(sum(row) for row in resultado)

if __name__ == "__main__":
    NUM_IMAGENES = 8
    SIZE = 150  # Subimos un poco el tamaño para apreciar el speedup

    print(f"Creando {NUM_IMAGENES} imágenes de {SIZE}x{SIZE}...")
    # Creamos tuplas (id, imagen) ya que map pasa un único argumento
    imagenes = [(i, crear_imagen(SIZE)) for i in range(NUM_IMAGENES)]

    # --- EJECUCIÓN SECUENCIAL ---
    print("\nProcesamiento secuencial:")
    inicio_seq = time.time()
    for img in imagenes:
        procesar_imagen(img)
    tiempo_secuencial = time.time() - inicio_seq
    print(f"Tiempo total secuencial: {tiempo_secuencial:.2f}s")

    # --- EJECUCIÓN PARALELA ---
    print("\nProcesamiento paralelo (4 workers):")
    inicio_par = time.time()
    with Pool(4) as pool:
        # pool.map distribuye la lista de tuplas entre los 4 workers
        resultados = pool.map(procesar_imagen, imagenes)
    tiempo_paralelo = time.time() - inicio_par

    for idx, duracion, checksum in resultados:
        print(f"  Imagen {idx}: procesada en {duracion:.3f}s (Checksum: {checksum})")

    print(f"Tiempo total paralelo: {tiempo_paralelo:.2f}s")
    print(f"Speedup alcanzado: {tiempo_secuencial / tiempo_paralelo:.2f}x")