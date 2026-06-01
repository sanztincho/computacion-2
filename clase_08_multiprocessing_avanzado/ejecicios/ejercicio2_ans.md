# Resultados
Secuencial:  0.40s
Pool(1):    0.34s  (speedup: 1.17x)
Pool(2):    0.20s  (speedup: 1.96x)
Pool(4):    0.15s  (speedup: 2.69x)
Pool(8):    0.10s  (speedup: 3.82x)

Secuencial:  0.37s
Pool(1):    0.35s  (speedup: 1.03x)
Pool(2):    0.18s  (speedup: 1.98x)
Pool(4):    0.13s  (speedup: 2.87x)
Pool(8):    0.11s  (speedup: 3.32x)
Pool(32):    0.13s  (speedup: 2.81x)

**Análisis del fenómeno:**
* Pool(1): Es ligeramente más lento que el secuencial debido al overhead de tener que serializar la tarea con pickle y enviarla a través de un canal IPC.
* Pool(2) y Pool(4): Muestran un escalado casi lineal (el tiempo se reduce a la mitad y a la cuarta parte). Cada proceso corre verdaderamente en paralelo en un núcleo de CPU distinto.
* Pool(8): Si tu CPU tiene 4 núcleos físicos y 8 lógicos, verás una mejora, pero el speedup ya no será lineal (no llegará a 8x) porque los núcleos lógicos comparten unidades de ejecución flotante dentro del silicio. al momento de poner Pool(32), el tiempo se estanca o empeora por la competencia extrema de recursos (context switching).