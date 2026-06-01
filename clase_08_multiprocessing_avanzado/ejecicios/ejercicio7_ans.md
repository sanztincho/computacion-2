# ¿Qué pasa si una etapa es mucho más lenta que las otras?

Se produce cuello de botella (bottleneck). Si la Etapa 2 tarda 5 segundos por elemento y las demás tardan milisegundos, la cola de entrada de la Etapa 2 (q2) comenzará a inflarse exponencialmente, acumulando elementos en memoria RAM. Al mismo tiempo, la Etapa 3 sufrirá de inanición (starvation), pasando la mayor parte de su tiempo bloqueada esperando en q3.get() a que la lenta Etapa 2 procese algo.

# ¿Cómo escalarías la etapa lenta?

La ventaja de usar multiprocessing.Queue es que implementa un modelo seguro para múltiples productores y consumidores de manera interna. Para escalar la etapa lenta, podemos levantar múltiples procesos trabajadores asignados a esa misma etapa. Por ejemplo, si la Etapa 2 es el cuello de botella, podríamos lanzar 4 procesos independientes ejecutando la función etapa_sumar, todos compartiendo la misma cola de entrada q2 y de salida q3. Las lecturas de la cola se balancearán de forma nativa entre los procesos disponibles, aliviando la saturación.