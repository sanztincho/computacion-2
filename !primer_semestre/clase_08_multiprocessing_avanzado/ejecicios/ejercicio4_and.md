# ¿En qué orden aparecen los items en la lista? ¿Por qué?

Aparecen en el orden estricto de finalización de las tareas. Cada worker duerme una cantidad de tiempo totalmente aleatoria determinada por random.uniform(0.2, 1.0). Aquel worker que tenga la fortuna de recibir el tiempo de espera más corto ejecutará la línea shared_list.append(...) primero, sin importar si su ID de creación era mayor o menor.

# ¿Manager es más rápido o más lento que Value/Array? ¿Por qué?

Es significativamente más lento. Value y Array reservan memoria directa en la RAM mediante llamadas mmap del núcleo. Manager, en cambio, levanta un proceso servidor independiente en background. Cada vez que hacemos un .append() o modificamos una clave del diccionario, tu proceso worker debe serializar el dato, mandarlo por un socket de red local al proceso del Manager, este modifica la estructura real en su propia memoria y devuelve una confirmación. Este viaje de IPC (Inter-Process Communication) penaliza fuertemente la velocidad.