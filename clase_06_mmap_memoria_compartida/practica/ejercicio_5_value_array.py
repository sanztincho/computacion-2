#!/usr/bin/env python3
"""
Ejercicio 5: Value y Array compartidos (OBLIGATORIO)
Tarea: Crear un Array('d', 100) compartido, calcular sin(i * 0.01) en 4 procesos,
y usar un Value para acumular la suma (observar race condition).
"""
import math
from multiprocessing import Process, Value, Array
import time

print("=" * 60)
print("EJERCICIO 5.1: Contador compartido - Race condition")
print("=" * 60)

def incrementar(contador, n, nombre):
    """Incrementa el contador n veces."""
    print(f"[{nombre}] Iniciando {n} incrementos...")
    for _ in range(n):
        contador.value += 1
    print(f"[{nombre}] Terminado")

# Crear valor compartido
contador = Value('i', 0)

# Lanzar 4 procesos que incrementan
N = 100000
print(f"\nCada proceso incrementará el contador {N} veces")
print(f"Total esperado: {4 * N}")

inicio = time.time()

procesos = []
for i in range(4):
    p = Process(target=incrementar, args=(contador, N, f"P{i}"))
    p.start()
    procesos.append(p)

for p in procesos:
    p.join()

duracion = time.time() - inicio

esperado = 4 * N
diferencia = esperado - contador.value

print(f"\nResultados después de {duracion:.4f}s:")
print(f"  Esperado:          {esperado}")
print(f"  Obtenido:          {contador.value}")
print(f"  Diferencia:        {diferencia} (incrementos perdidos)")
print(f"  Porcentaje perdido: {(diferencia/esperado)*100:.2f}%")

if diferencia > 0:
    print(f"\n⚠️  RACE CONDITION DETECTADA:")
    print(f"    Los procesos interfieren entre sí al acceder a contador.value")
    print(f"    Sin sincronización, múltiples procesos pueden leer el mismo valor")
    print(f"    y escribir resultados que se sobrescriben mutuamente.")

print("\n" + "=" * 60)
print("EJERCICIO 5.2: Array compartido para cálculo paralelo")
print("=" * 60)

def calcular_senos(resultado, inicio, fin):
    """Calcula sin(i * 0.01) para cada índice en el rango."""
    for i in range(inicio, fin):
        resultado[i] = math.sin(i * 0.01)

# Array compartido de 100 doubles
TAMAÑO = 100
resultado = Array('d', TAMAÑO)

# Dividir en 4 procesos
NUM_PROCESOS = 4
chunk = TAMAÑO // NUM_PROCESOS

print(f"\nConfiguración:")
print(f"  Tamaño del array: {TAMAÑO}")
print(f"  Procesos: {NUM_PROCESOS}")
print(f"  Elementos por proceso: {chunk}")
print(f"  Fórmula: sin(i * 0.01)")

inicio_t = time.time()

procesos = []
for i in range(NUM_PROCESOS):
    ini = i * chunk
    fin = (i + 1) * chunk if i < NUM_PROCESOS - 1 else TAMAÑO
    p = Process(target=calcular_senos, args=(resultado, ini, fin))
    p.start()
    procesos.append(p)

for p in procesos:
    p.join()

duracion_t = time.time() - inicio_t

# Verificar
print(f"\nCálculo completado en {duracion_t:.6f}s")
print(f"\nVerificación de resultados:")
print(f"  resultado[0]  = sin(0.00)     = {resultado[0]:8.6f} (esperado: {math.sin(0):.6f})")
print(f"  resultado[10] = sin(0.10)     = {resultado[10]:8.6f} (esperado: {math.sin(0.10):.6f})")
print(f"  resultado[50] = sin(0.50)     = {resultado[50]:8.6f} (esperado: {math.sin(0.50):.6f})")
print(f"  resultado[99] = sin(0.99)     = {resultado[99]:8.6f} (esperado: {math.sin(0.99):.6f})")

# Verificar que todos son correctos
errores = sum(1 for i in range(TAMAÑO) if abs(resultado[i] - math.sin(i * 0.01)) > 1e-10)
print(f"\n  Errores de cálculo: {errores}")

# Mostrar primeros 20 resultados
print(f"\nPrimeros 20 resultados:")
for i in range(20):
    print(f"  [{i:2d}] sin({i*0.01:5.2f}) = {resultado[i]:8.6f}", end="")
    if (i + 1) % 2 == 0:
        print()
    else:
        print(" | ", end="")
print()

print("\n" + "=" * 60)
print("EJERCICIO 5 BONUS: Acumular suma con Value (Race Condition)")
print("=" * 60)

def calcular_senos_con_suma(resultado, suma_compartida, inicio, fin, nombre):
    """Calcula sin y acumula la suma en Value compartido."""
    suma_local = 0.0
    
    for i in range(inicio, fin):
        valor = math.sin(i * 0.01)
        resultado[i] = valor
        suma_local += valor
    
    # Acceso no sincronizado al Value (RACE CONDITION)
    actual = suma_compartida.value
    suma_compartida.value = actual + suma_local
    
    print(f"[{nombre}] Sum local: {suma_local:.6f}, escribí {suma_compartida.value:.6f}")

# Crear nuevo array y Value
resultado2 = Array('d', TAMAÑO)
suma_compartida = Value('d', 0.0)

print(f"\nCalculando sin(i*0.01) y suma con {NUM_PROCESOS} procesos...")
print(f"ADVERTENCIA: Sin sincronización, la suma puede ser incorrecta")

procesos = []
for i in range(NUM_PROCESOS):
    ini = i * chunk
    fin = (i + 1) * chunk if i < NUM_PROCESOS - 1 else TAMAÑO
    p = Process(target=calcular_senos_con_suma, args=(resultado2, suma_compartida, ini, fin, f"P{i}"))
    p.start()
    procesos.append(p)

for p in procesos:
    p.join()

# Calcular suma esperada
suma_esperada = sum(math.sin(i * 0.01) for i in range(TAMAÑO))
suma_obtenida = suma_compartida.value

print(f"\nResultados:")
print(f"  Suma esperada:  {suma_esperada:.6f}")
print(f"  Suma obtenida:  {suma_obtenida:.6f}")
print(f"  Diferencia:     {abs(suma_esperada - suma_obtenida):.6f}")

if abs(suma_esperada - suma_obtenida) > 1e-5:
    print(f"\n⚠️  RACE CONDITION DETECTADA en la suma")
    print(f"    Los procesos interfieren al actualizar Value('d', ...)")
else:
    print(f"\n✓ Suma correcta (por suerte, sin race condition esta vez)")

print(f"\nNota sobre sincronización:")
print(f"  Para evitar race conditions en Value/Array, usar:")
print(f"  - from multiprocessing import Lock, Semaphore")
print(f"  - O usar funciones como sum() con computaciones locales")
