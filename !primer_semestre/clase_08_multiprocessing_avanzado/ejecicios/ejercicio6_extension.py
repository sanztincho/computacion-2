#!/usr/bin/env python3
"""Map-Reduce para conteo de palabras optimizado por chunks."""
from multiprocessing import Pool
from functools import reduce

def mapper_chunk(chunk_texto):
    """Cuenta palabras de un bloque/chunk de texto específico (Fase Map)."""
    conteo = {}
    # Limpieza básica de puntuación elemental
    for car in [",", ".", "\n", "-"]:
        chunk_texto = chunk_texto.replace(car, " ")
        
    for palabra in chunk_texto.lower().split():
        if len(palabra) > 2:  # Ignorar conectores chicos
            conteo[palabra] = conteo.get(palabra, 0) + 1
    return conteo

def reducer(dict1, dict2):
    """Combina de forma acumulativa dos diccionarios (Fase Reduce)."""
    resultado = dict1.copy()
    for palabra, count in dict2.items():
        resultado[palabra] = resultado.get(palabra, 0) + count
    return resultado

if __name__ == "__main__":
    # Simulación de un contenido de archivo muy grande
    contenido_archivo_gigante = """
    El desarrollo de software concurrente requiere entender sistemas operativos.
    El multiprocesamiento avanzado aprovecha los cores. Python es genial para esto,
    pero hay que tener cuidado con pickle y la serialización de datos.
    El patron Map-Reduce divide las tareas pesadas de procesamiento de texto.
    Los procesos corren en espacios de memoria aislados, a diferencia de los hilos.
    Sistemas operativos como Linux usan fork para duplicar la memoria eficientemente.
    """ * 1000  # Multiplicamos el texto para simular un archivo de miles de líneas
    
    # --- EXTENSIÓN: División del archivo en chunks ---
    # Cortamos el texto cada 500 caracteres
    TAMANIO_CHUNK = 500
    chunks = [contenido_archivo_gigante[i:i + TAMANIO_CHUNK] 
              for i in range(0, len(contenido_archivo_gigante), TAMANIO_CHUNK)]
    
    print(f"Archivo dividido de forma exitosa en {len(chunks)} chunks.")

    # 1. Fase Map: Enviamos los chunks en paralelo a los workers del Pool
    with Pool(4) as pool:
        conteos_parciales = pool.map(mapper_chunk, chunks)

    # 2. Fase Reduce: Consolidamos secuencialmente los diccionarios mapeados
    print("Consolidando los conteos parciales mediante functools.reduce...")
    conteo_total = reduce(reducer, conteos_parciales)

    # Ordenar resultados para mostrar las palabras más frecuentes
    palabras_ordenadas = sorted(conteo_total.items(), key=lambda x: -x[1])

    print("\nTop 5 palabras más frecuentes en el archivo:")
    for palabra, count in palabras_ordenadas[:5]:
        print(f"  {palabra:15s} : {count} veces")