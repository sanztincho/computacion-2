# TP N.º 2 — Plataforma de Tareas Distribuidas: Monitor de sitios

**Computación II — Universidad de Mendoza — Martin Sanz — 2026**

Un servicio HTTP al que se le encargan trabajos, que los ejecuta de forma
concurrente en un solo hilo con `asyncio` y permite consultar su estado y
resultado. La temática es un **monitor de sitios**: chequear si un conjunto de
URLs está vivo (código de estado, tamaño y tiempo de respuesta) y cuántos días
le quedan al certificado TLS de cada host. Una página servida por la misma API
muestra las tareas en vivo por WebSocket.

```
docker compose up --build
# API + página en vivo:  http://localhost:8000
# Documentación OpenAPI: http://localhost:8000/docs
```

---

## Índice

0. [Cómo correrlo](#0-cómo-correrlo)
1. [Descripción y uso](#1-descripción-y-uso)
2. [Arquitectura](#2-arquitectura)
3. [Decisiones de diseño](#3-decisiones-de-diseño)
4. [Mediciones](#4-mediciones)
5. [Conceptos del curso aplicados](#5-conceptos-del-curso-aplicados)
6. [Las preguntas de la corrección](#6-las-preguntas-de-la-corrección)
7. [Limitaciones conocidas](#7-limitaciones-conocidas)
8. [Extensiones (bonus) y tests](#8-extensiones-bonus-y-tests)
9. [Lo que aprendí](#9-lo-que-aprendí)

---

## 0. Cómo correrlo

### Requisitos

- **Docker** con **Docker Compose v2** (el comando es `docker compose`, con
  espacio). En Windows y macOS alcanza con Docker Desktop.
- **git**, para clonar el repositorio.
- Los puertos **8000** (API) y **8001** (sitios de prueba) libres en el host.

No hace falta tener Python instalado: todo corre dentro de los contenedores.

### 1. Clonar y levantar

```bash
git clone https://github.com/sanztincho/computacion-2.git
cd computacion-2/trabajos_practicos/TP2_tareas
docker compose up --build
```

La primera vez tarda un par de minutos (baja la imagen de Python e instala las
dependencias); las siguientes usa la caché. Se levantan dos contenedores:

| Servicio | Contenedor | Puerto | Qué es |
|----------|------------|--------|--------|
| `api` | `tp2_api` | 8000 | La plataforma de tareas (el TP) |
| `sitios` | `tp2_sitios` | 8001 | Sitios de prueba con latencia controlada, para demos y mediciones |

Está listo cuando el log de `api` muestra:

```
tp2_api  | 12:04:25 INFO    app.pool: pool iniciado: 8 workers, cola de 10000, N procesos para CPU
tp2_api  | 12:04:25 INFO    tp2: escuchando en http://0.0.0.0:8000  (UI en /, docs en /docs)
tp2_api  | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Para dejarlo corriendo en segundo plano: `docker compose up --build -d`, y los
logs con `docker compose logs -f api`.

### 2. Verificar que anda

| Qué | Dónde |
|-----|-------|
| Página de monitoreo en vivo | <http://localhost:8000> |
| Documentación interactiva (se pueden probar los endpoints desde ahí) | <http://localhost:8000/docs> |
| Estadísticas | `curl localhost:8000/estadisticas` |

En la página, arriba a la derecha tiene que decir **"en vivo"** (el WebSocket
está conectado). Elegí una pestaña, completá los datos y apretá **Encolar**.

### 3. Prueba rápida desde la terminal

```bash
# 1) Chequear URLs: una lenta, una que da 503, una caída
curl -s -X POST localhost:8000/tareas -H 'Content-Type: application/json' -d '{
  "tipo": "descargar",
  "params": {"urls": ["http://sitios:8001/demora/800", "http://sitios:8001/estado/503",
                      "http://sitios:8001/redirigir", "https://no-existe.invalid"]}}'
# Responde al instante con {"id": "...", "estado": "pendiente", ...}

# 2) Ver el resultado (reemplazar <id> por el que devolvió el POST)
curl -s localhost:8000/tareas/<id> | python3 -m json.tool

# 3) Una tarea larga, y cancelarla mientras corre
curl -s -X POST localhost:8000/tareas -H 'Content-Type: application/json' \
  -d '{"tipo": "esperar", "params": {"segundos": 60}}'
curl -s -X DELETE localhost:8000/tareas/<id>          # -> "estado": "cancelada"

# 4) Timeout: 30 s de trabajo con 2 s de límite -> "fallida"
curl -s -X POST localhost:8000/tareas -H 'Content-Type: application/json' \
  -d '{"tipo": "esperar", "params": {"segundos": 30}, "timeout": 2}'

# 5) CPU-bound (va al pool de procesos) y certificados TLS
curl -s -X POST localhost:8000/tareas -H 'Content-Type: application/json' \
  -d '{"tipo": "hashear", "params": {"texto": "hola", "iteraciones": 20000000}}'
curl -s -X POST localhost:8000/tareas -H 'Content-Type: application/json' \
  -d '{"tipo": "chequear_ssl", "params": {"hosts": ["github.com", "expired.badssl.com"]}}'

# 6) Listar y filtrar
curl -s 'localhost:8000/tareas?estado=completada&limite=5' | python3 -m json.tool
```

> **Por qué `sitios:8001` y no `localhost:8001`:** las URLs no las pide `curl`
> sino el contenedor de la API. Dentro de él, `localhost` es el propio
> contenedor; el servicio de prueba se alcanza por su nombre en la red de
> Compose, `sitios`. Desde el navegador del host, en cambio, sí es
> <http://localhost:8001>.

### 4. Correr los tests

```bash
docker compose run --rm api pytest -v
```

Son 31 tests y tardan unos 12 segundos. No necesitan internet: los sitios y los
servidores TLS se simulan.

### 5. Correr las mediciones

Con el compose levantado:

```bash
# Medición 1: 20 chequeos secuenciales contra 20 concurrentes
docker compose exec api python mediciones/medir_io.py

# Medición 2: necesita habilitar el modo que bloquea el loop
docker compose down
PERMITIR_MODO_BLOQUEANTE=1 docker compose up --build -d
docker compose exec api python mediciones/medir_bloqueo.py

# Medición 3: techo del pool (tarda alrededor de un minuto)
docker compose down && docker compose up -d
docker compose exec api python mediciones/medir_techo.py

# Variante de la medición 3, para ver el techo del event loop con muchos workers
docker compose down
WORKERS=20000 MAX_COLA=50000 docker compose up -d
docker compose exec api python mediciones/medir_techo.py --partes a --ns 1000,5000,10000,20000 --segundos 10
```

Cada corrida imprime una tabla y guarda el detalle en
`mediciones/resultados/` dentro del contenedor.

### 6. Apagar

```bash
docker compose stop        # manda SIGTERM: apagado ordenado
docker compose down        # además borra los contenedores
```

(o `Ctrl+C` si estaba en primer plano, que manda SIGINT).

Al apagar, el log muestra el apagado ordenado y el volcado del estado:

```
tp2_api  | 12:05:03 INFO    tp2: apagado ordenado iniciado por SIGTERM
tp2_api  | 12:05:03 INFO    app.pool: apagado: esperando hasta 10s a 2 tareas en ejecución
tp2_api  | 12:05:05 INFO    app.pool: pool detenido (quedaron 0 tareas pendientes sin ejecutar)
tp2_api  | 12:05:05 INFO    tp2: estado volcado en /app/volcados/estado_20261027_120513.json (17 tareas)
```

El archivo queda en la carpeta `volcados/` del host (es un volumen). Al volver
a levantar, el log informa que encontró el volcado previo.

### 7. Cambiar la configuración

Las variables de la tabla de la sección 1 se pasan delante del comando:

```bash
WORKERS=16 PROCESOS=4 MAX_COLA=500 docker compose up --build
```

Si el puerto 8000 está ocupado, cambiá el lado izquierdo del mapeo en
`docker-compose.yml` (por ejemplo `"8080:8000"`) y entrá por
<http://localhost:8080>.

### 8. Sin Docker (opcional, para desarrollar)

Con Python 3.11 o más nuevo:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Terminal 1: sitios de prueba
uvicorn sitios_prueba.servidor:app --port 8001

# Terminal 2: la API (los volcados quedan en ./volcados)
python -m app

# Terminal 3: tests y mediciones
pytest -v
SITIOS=http://localhost:8001 python mediciones/medir_io.py
```

Fuera de Docker no existe el nombre `sitios`: en los ejemplos de `curl` hay que
usar `http://localhost:8001` en las URLs. Y para que la medición 3 lea la
memoria del servidor, pasale su PID: `PID_SERVIDOR=$(pgrep -f "python -m app") python mediciones/medir_techo.py`.

### Problemas comunes

| Síntoma | Causa y solución |
|---------|------------------|
| `port is already allocated` | Hay algo en el 8000 o el 8001: apagalo o cambiá el mapeo (punto 7). |
| Las URLs `http://sitios:8001/...` dan `ConnectError` | Estás corriendo sin Docker: usá `localhost:8001`. |
| `hashear` con `ejecutor: "loop"` responde 400 | Es intencional: solo se habilita con `PERMITIR_MODO_BLOQUEANTE=1` (medición 2). |
| `POST /tareas` responde 503 | La cola está llena (`MAX_COLA`) o el servidor se está apagando. Reintentá en unos segundos. |
| No se pueden borrar los archivos de `volcados/` | Los escribe el contenedor como root: `sudo rm volcados/*.json`. |
| La página dice "reconectando…" | La API está caída o reiniciándose; se reconecta sola cuando vuelve. |

---

## 1. Descripción y uso

### Tipos de tarea

| Tipo | Naturaleza | Qué hace | Qué ejercita |
|------|-----------|----------|--------------|
| `descargar` | I/O-bound | Chequea una lista de URLs: código, tamaño, tiempo de respuesta | Concurrencia asíncrona real (`TaskGroup` + `Semaphore`) |
| `hashear` | CPU-bound | SHA-256 aplicado N veces sobre un texto | Que asyncio **no** sirve para calcular: `run_in_executor` |
| `esperar` | I/O simulado | Duerme N segundos | Cancelación, timeouts, estado en vivo |
| `chequear_ssl` | I/O (tarea propia) | Handshake TLS con `asyncio.open_connection`; días hasta que vence el certificado | Sockets de la clase 13, sin bloquear |

Estados posibles: `pendiente` → `ejecutando` → `completada` | `fallida` | `cancelada`.

### Endpoints

| Método | Ruta | Qué hace |
|--------|------|----------|
| `POST` | `/tareas` | Encola una tarea. Responde **202** al instante con `id` y estado `pendiente` |
| `GET` | `/tareas?estado=&tipo=&limite=` | Lista las tareas (las más nuevas primero) |
| `GET` | `/tareas/{id}` | Estado, progreso y resultado |
| `DELETE` | `/tareas/{id}` | Cancela una tarea pendiente **o en ejecución**; 409 si ya terminó |
| `GET` | `/estadisticas` | Totales por estado, tiempos promedio, workers ocupados, cola |
| `GET` | `/metricas` | Lo mismo en formato Prometheus (bonus) |
| `WS` | `/eventos` | Cambios de estado y progreso en tiempo real (bonus) |
| `GET` | `/` | Página de monitoreo en vivo |

Errores: `422` si el cuerpo no valida (Pydantic), `503` si la cola está llena
o el servidor se está apagando, `404` si la tarea no existe.

### Ejemplos con `curl`

El compose levanta dos servicios: `api` (el TP) y `sitios`, un servidor de
prueba con latencia y códigos de estado controlados. **Ojo con los nombres**:
las URLs las pide el contenedor de la API, así que el servicio de prueba se
llama `http://sitios:8001`, no `localhost`.

```bash
# Chequear URLs (concurrente por defecto)
curl -s -X POST localhost:8000/tareas -H 'Content-Type: application/json' -d '{
  "tipo": "descargar",
  "params": {"urls": ["https://www.um.edu.ar", "http://sitios:8001/demora/800",
                      "http://sitios:8001/estado/503", "https://no-existe.invalid"]}
}'
# -> {"id":"3f9c1a2b7d10","tipo":"descargar","estado":"pendiente","timeout":60.0,...}

curl -s localhost:8000/tareas/3f9c1a2b7d10 | python3 -m json.tool

# Certificados TLS: días hasta el vencimiento (acepta host, host:puerto o una URL)
curl -s -X POST localhost:8000/tareas -H 'Content-Type: application/json' -d '{
  "tipo": "chequear_ssl", "params": {"hosts": ["github.com", "expired.badssl.com"]}}'

# CPU-bound: va al ProcessPoolExecutor
curl -s -X POST localhost:8000/tareas -H 'Content-Type: application/json' -d '{
  "tipo": "hashear", "params": {"texto": "hola", "iteraciones": 20000000}}'

# Timeout: duerme 30 s pero tiene 2 s -> pasa a "fallida" con el motivo
curl -s -X POST localhost:8000/tareas -H 'Content-Type: application/json' -d '{
  "tipo": "esperar", "params": {"segundos": 30}, "timeout": 2}'

# Cancelar una tarea en ejecución
curl -s -X DELETE localhost:8000/tareas/<id>

# Filtrar y ver estadísticas
curl -s 'localhost:8000/tareas?estado=fallida&limite=10'
curl -s localhost:8000/estadisticas

# Apagado ordenado: SIGTERM -> espera las tareas en curso -> volcados/estado_<timestamp>.json
docker compose stop api && ls volcados/
```

### Configuración

Todo por variables de entorno (ver `app/config.py`), por ejemplo
`WORKERS=16 docker compose up`:

| Variable | Default | Para qué |
|----------|---------|----------|
| `WORKERS` | 8 | Corrutinas que consumen la cola |
| `PROCESOS` | cantidad de cores | Procesos del `ProcessPoolExecutor` |
| `MAX_COLA` | 10000 | `maxsize` de la `asyncio.Queue` (backpressure → 503) |
| `TIMEOUT_DEFECTO` | 60 | Timeout de una tarea si el pedido no trae uno |
| `ESPERA_APAGADO` | 10 | Cuánto se espera a las tareas en curso al apagar |
| `BLOQUE_HASH` | 100000 | Iteraciones por viaje al executor (granularidad de la cancelación) |
| `PERMITIR_MODO_BLOQUEANTE` | 0 | Habilita `hashear` con `ejecutor: "loop"`, solo para la medición 2 |

### Tests

```bash
docker compose run --rm api pytest -v
```

---

## 2. Arquitectura

### Componentes

```
                         un solo proceso, un solo hilo, un solo event loop (uvicorn)
 ┌────────────────────────────────────────────────────────────────────────────────────┐
 │                                                                                    │
 │  Cliente HTTP ──> FastAPI ──── encolar() ───> asyncio.Queue(maxsize) ──┐           │
 │   (curl, página)   │           (sin await,     [id, id, id, ...]       │ get()     │
 │                    │            responde 202)                          v           │
 │                    │                                     ┌──────────────────────┐  │
 │   GET /tareas ─────┼──> Almacen (dict id -> Tarea) <─────│ worker 0 ... worker N│  │
 │   GET /estadist. ──┤     + contadores                    │   (corrutinas)       │  │
 │   DELETE ──────────┼──> cancelar() ───── task.cancel() ─>│  cada una lanza una  │  │
 │                    │          │                          │  Task HIJA por tarea │  │
 │   WS /eventos <────┴── BusDeEventos <── transicion() ────│                      │  │
 │                         (1 Queue por cliente)            └──┬────────────┬──────┘  │
 │                                                             │ I/O        │ CPU     │
 │                                                             v            v         │
 │                                           httpx.AsyncClient /    run_in_executor   │
 │                                           open_connection(TLS)        │            │
 └───────────────────────────────────────────────────┬──────────────────┼─────────────┘
                                                     │                  │ pickle
                                       sockets (epoll, clase 17)        v
                                                     │      ┌──────────────────────────┐
                                                     v      │ ProcessPoolExecutor      │
                                                 internet / │ PROCESOS procesos (spawn)│
                                                 sitios:8001│ hash_iterado(dato, n)    │
                                                            └──────────────────────────┘
```

### Flujo de una tarea

```
POST /tareas
  │  Pydantic valida el cuerpo (unión discriminada por "tipo")
  │  encolar(): crea la Tarea (pendiente), put_nowait(id) ── cola llena? ──> 503
  │  responde 202 {id, estado: pendiente}            <── en microsegundos
  v
asyncio.Queue
  │  un worker libre hace `await cola.get()` y recibe el id
  │  ¿la cancelaron mientras esperaba? ──> se saltea (task_done) y sigue
  v
worker._correr()
  │  transición -> ejecutando  (evento por WebSocket)
  │  hija = create_task(_ejecutar(tarea))
  │  await asyncio.wait([hija])     <── el worker espera, no recibe excepciones
  v
_ejecutar()  dentro de  `async with asyncio.timeout(tarea.timeout)`
  │  descargar / chequear_ssl / esperar: await directo (I/O, cede el loop)
  │  hashear: bucle de bloques -> await loop.run_in_executor(procesos, ...)
  v
worker._registrar_final(hija)
     hija.cancelled()          -> cancelada (por DELETE o por apagado)
     excepción _Vencida        -> fallida  "timeout: no terminó en Xs"
     otra excepción            -> fallida  "TipoDeError: mensaje" (+ traceback al log)
     resultado                 -> completada
  finally: cola.task_done(), y el worker vuelve a `await cola.get()`
```

### Estructura del código

```
app/
├── __main__.py        arranque de uvicorn + enganche de SIGTERM/SIGINT
├── main.py            FastAPI: rutas, WebSocket, lifespan (arranque y apagado)
├── pool.py            PoolDeWorkers: cola, workers, cancelación, timeouts, supervisor
├── almacen.py         estado en memoria + contadores de estadísticas
├── eventos.py         bus de eventos para el WebSocket
├── persistencia.py    volcado atómico a JSON y lectura del volcado previo
├── modelos.py         Tarea, Estado y los modelos Pydantic de la API
├── config.py          configuración por variables de entorno
├── tareas/            un módulo por tipo: descargar, hashear, esperar, chequear_ssl
└── static/index.html  la página de monitoreo (JS sin dependencias)
sitios_prueba/         servidor HTTP con latencias controladas (servicio `sitios`)
mediciones/            los tres scripts de medición
tests/                 31 tests con pytest-asyncio
```

---

## 3. Decisiones de diseño

### 3.1 ¿Por qué `asyncio.Queue` y no `queue.Queue`?

Porque `queue.Queue.get()` **bloquea el hilo**. Es una cola para threads: cuando
está vacía, el thread que llama se duerme en un `Condition` hasta que alguien
haga `put()`. En nuestro sistema todos los workers son corrutinas del mismo
hilo; si uno llamara a `queue.Queue.get()` con la cola vacía, dormiría al único
hilo que existe, y con él al event loop, a uvicorn y a todos los demás workers.
Nadie podría hacer el `put()` que lo despierte: un deadlock con un solo
participante.

`asyncio.Queue.get()` es una corrutina: si la cola está vacía, **suspende a ese
worker** (`await`) y le devuelve el control al loop, que sigue atendiendo pedidos
HTTP y al resto de los workers. Cuando un POST hace `put_nowait()`, el loop
despierta a uno de los workers suspendidos. Es el productor-consumidor de la
clase 11, pero la espera es cooperativa en vez de un bloqueo del sistema
operativo.

La otra razón es que `asyncio.Queue` **no es thread-safe, y no necesita serlo**:
todo el que la toca corre en el hilo del loop. `queue.Queue` paga un lock en
cada operación para protegerse de algo que acá no puede pasar.

Detalles de cómo la uso:

- **`maxsize` es backpressure** (clase 21). Si la cola está llena, `encolar()`
  usa `put_nowait` y responde **503 con `Retry-After`** en vez de `await put()`:
  prefiero rechazar en el acto a dejar un pedido HTTP colgado esperando lugar.
- **`task_done()` va en un `finally`**: si algo falla, el contador interno de la
  cola igual baja.
- **Cancelar una tarea pendiente** no la saca de la cola (una `Queue` no permite
  sacar un elemento del medio): se marca `cancelada` y el worker que la saque la
  saltea. Es "borrado perezoso", O(1).

### 3.2 ¿Cómo evito que una tarea CPU-bound congele la API?

Un cálculo dentro de una corrutina no tiene ningún `await`: nunca le devuelve
el control al loop. Mientras dura, uvicorn no acepta conexiones, ningún endpoint
responde, ningún timeout vence y ni siquiera se puede cancelar la tarea (el
`CancelledError` se inyecta en el *próximo* `await`, que no llega). La
medición 2 lo muestra: un `GET /tareas` tardó **3,4 segundos** en vez de 2 ms.

La solución es **sacar el cálculo del hilo del loop**:

```python
# tareas/hashear.py
dato = await loop.run_in_executor(ctx.pool_procesos, hash_iterado, dato, n)
```

`run_in_executor` le pasa la función a un `ProcessPoolExecutor` y devuelve un
future de asyncio. El worker hace `await` sobre ese future, así que se suspende
como si fuera I/O; el loop sigue libre mientras otro **proceso** calcula.

**¿Por qué procesos y no threads (`asyncio.to_thread`)?** Por el GIL (clase 9).
Un thread que calcula en Python tiene el GIL casi todo el tiempo; el hilo del
loop lo recupera cada ~5 ms (el *switch interval*) para atender algo y lo
vuelve a soltar. Medido (sección 4.2): con `to_thread` la API respondía en
**13,7 ms** de mediana; con procesos, en **3,8 ms**. Y con varios cálculos a la
vez la diferencia es mayor: 4 hashes simultáneos tardaron **8,3 s con threads
contra 4,0 s con procesos**, porque los threads se turnan el GIL y los procesos
corren de verdad en paralelo. El modo `hilo` quedó disponible para poder
comparar.

**Decisiones del pool de procesos:**

- Se crea **una vez** en el `lifespan` y se reutiliza (clase 22: crear un pool
  por pedido es el antipatrón). Al arrancar se "calienta" con un trabajo trivial
  por proceso, así la primera tarea no paga el arranque del intérprete.
- Usa el método de arranque **`spawn` y no `fork`**: hacer `fork()` (clase 3) de
  un proceso que ya tiene un event loop, threads y sockets abiertos copia todo
  ese estado al hijo, y los locks copiados en mitad de uso son una fuente
  clásica de deadlocks. Con `spawn` cada proceso arranca un intérprete limpio.
- `hash_iterado` es una **función pura a nivel de módulo**, porque viaja
  pickleada al otro proceso (una lambda o una función anidada no se pueden
  picklear, clase 22). Lo que viaja es poco: 32 bytes de digest y un entero.

**El cálculo va en bloques.** En vez de mandar 50 millones de iteraciones de
una vez, `hashear` manda bloques de `BLOQUE_HASH` (100.000) y hace `await`
entre bloque y bloque. Esto existe por la cancelación (3.3): un trabajo que ya
arrancó en un executor no se puede interrumpir.

### 3.3 ¿Cómo implementé la cancelación, y qué pasa con los recursos a medio usar?

Cada worker ejecuta cada tarea en una **`asyncio.Task` hija**, y guarda la
referencia en `_en_curso[id]`. `DELETE /tareas/{id}` hace:

- **Si está pendiente**: la marca `cancelada` y listo (el worker la va a saltear).
- **Si está ejecutando**: `hija.cancel()`, y espera con `asyncio.wait([hija],
  timeout=5)` a que la cancelación termine, para poder devolver el estado final
  en la misma respuesta.

`cancel()` no mata nada: **inyecta un `CancelledError` en el próximo `await`** de
la hija (clase 20). Esa excepción sube por la pila de llamadas y en el camino
ejecuta todos los `finally` y los `__aexit__` de los `async with`. La limpieza
de recursos está escrita para aprovechar exactamente eso:

| Tarea | Dónde estaba al cancelarse | Qué se libera y cómo |
|-------|---------------------------|----------------------|
| `descargar` | en `await` de red, a mitad de leer el cuerpo | `async with cliente.stream(...)`: al salir por la excepción httpx cierra la respuesta y devuelve o descarta la conexión del pool. El `TaskGroup` cancela **todas** las descargas hermanas y espera a que terminen antes de propagar: no quedan corrutinas huérfanas. Lo verifica `test_cancelar_a_mitad_de_descarga_cierra_la_respuesta`. |
| `chequear_ssl` | en el handshake TLS | `writer.close()` en un `finally` (como el "siempre cerrar" de la clase 13), con un `wait_closed()` acotado a 2 s. |
| `esperar` | en `asyncio.sleep` | nada que liberar. |
| `hashear` | esperando el bloque que corre en otro proceso | El bloque en curso **no se puede cancelar**: `Future.cancel()` solo funciona si el trabajo no empezó (clase 22). Ese bloque termina en su proceso y su resultado se descarta. Por eso se calcula en bloques: lo desperdiciado es como mucho un bloque (~0,1 s) y el proceso queda libre enseguida. Medido: el DELETE de un hash de 50 millones de iteraciones respondió en 35 ms. |

**Worker y tarea están separados a propósito.** El worker no hace `await hija`
sino `await asyncio.wait([hija])`, que espera a que termine **sin propagar** su
excepción ni su cancelación. Así el worker distingue dos casos que con un
`await` directo serían el mismo `CancelledError`:

- **Cancelaron la tarea** (DELETE): `hija.cancelled()` es `True` y el worker
  sigue vivo para la próxima.
- **Cancelaron al worker** (apagado forzado): el `CancelledError` llega al
  propio worker. Entonces cancela también a la hija, la espera (para no dejarla
  huérfana), la registra como cancelada y **relanza** el `CancelledError`: tragarse
  esa excepción sería mentirle a quien pidió la cancelación (clase 20).

El **timeout** es el mismo mecanismo: `asyncio.timeout()` cancela la corrutina
al vencer y convierte el `CancelledError` en `TimeoutError` al salir del bloque.
Uso `limite.expired()` para distinguir "venció *mi* timeout" de un
`TimeoutError` que venga de adentro, y en ese caso la tarea pasa a `fallida`
con el motivo `timeout: no terminó en Xs`.

### 3.4 ¿Qué pasa si un worker lanza una excepción no capturada?

Hay dos niveles:

**La tarea lanza una excepción** (lo esperable: un bug en un tipo de tarea, un
dato raro). La excepción queda guardada dentro de la Task hija; el worker la lee
con `hija.exception()`, escribe el traceback completo en el log, marca la tarea
como `fallida` con `"TipoDeError: mensaje"` y sigue con la próxima. Nada se
pierde y el pool no se achica. Las fallas *esperables* ni siquiera llegan acá:
un sitio caído o un DNS que no resuelve no es un error de la tarea, es el dato
que el monitor vino a buscar, y se informa dentro del resultado.

**El worker mismo muere** (un bug en el código del pool). Sin protección, esto
sería el "bug silencioso" de la clase 22: la Task del worker termina con una
excepción que nadie lee, el pool pasa de 8 a 7 workers y nadie se entera. Para
eso cada worker tiene un `add_done_callback(_vigilar_worker)`: si un worker
termina con excepción y no estamos apagando, se loguea el error y **se lanza un
reemplazo** con el mismo número. El contador `workers.reiniciados` de
`/estadisticas` lo deja a la vista. Los dos casos tienen test
(`test_excepcion_en_tarea_no_mata_al_worker`, `test_worker_que_muere_es_reemplazado`).

Detalle: las referencias a las Tasks se guardan en un diccionario. El loop solo
guarda referencias débiles a las tasks, y una task sin referencia fuerte puede
ser recolectada a mitad de ejecución.

### 3.5 ¿Por qué el pool no necesita un `Lock`?

Porque en asyncio **el cambio de contexto solo ocurre en un `await`** (clase 20).
Entre dos `await` consecutivos, mi código corre sin que nadie lo interrumpa.

El estado compartido es el diccionario del `Almacen`, sus contadores y
`_en_curso`. Toda modificación pasa por `Almacen.transicion()`, que lee el
estado viejo, valida, actualiza campos y contadores y publica el evento **sin
ningún `await` en el medio**: para el resto del programa es atómica. Lo mismo
`encolar()` (que es una función común, no corrutina) y el `hechas += 1` de
`descargar`.

Con threads, `contador += 1` no es atómico (leer, sumar, guardar) y el scheduler
puede interrumpir en el medio: es la race condition de la clase 11. Acá eso no
puede pasar, y se verifica *leyendo el código*: los puntos de interrupción
están marcados con `await`. Si alguna vez una sección crítica necesitara un
`await` adentro, ahí sí haría falta un `asyncio.Lock`.

¿Y los procesos y threads del executor? **Nunca tocan el estado**: reciben datos,
calculan y devuelven un resultado. Quien lo escribe en el almacén es la
corrutina que hizo el `await`, de nuevo en el hilo del loop.

### 3.6 ¿Por qué httpx y no aiohttp?

Las dos son asíncronas; `requests` no es opción porque bloquearía el loop. Elegí
**httpx** porque:

- Es la que usamos en la clase 20, y su API es la de `requests`
  (`cliente.get(url)`, `respuesta.status_code`).
- Tiene **timeouts por fase** (conexión, lectura, escritura, pool) con un valor
  por defecto obligatorio: sin timeout, una URL que no responde dejaría una
  tarea colgada para siempre.
- `cliente.stream()` como `async with` me da lectura **con tope** de bytes y
  una cancelación limpia (3.3).
- Trae `MockTransport`, con el que los tests simulan sitios lentos, caídos o
  que mandan el cuerpo de a poco, sin red.

El costo: aiohttp es más rápido. Lo comprobé sin buscarlo en la medición 3: con
diez mil POSTs, el proceso **cliente** con httpx se fue al 100% de CPU mientras
el servidor estaba al 20% (sección 4.3). Para un monitor que chequea decenas de
URLs no importa; para el generador de carga sí, y lo reemplacé por un cliente
HTTP escrito a mano.

El cliente `httpx.AsyncClient` se crea **una vez** en el lifespan y lo
comparten todas las tareas, con su pool de conexiones (máximo 200) y
keep-alive (clases 19 y 20). Ese límite de conexiones funciona además como un
semáforo global; dentro de cada tarea hay otro `Semaphore(max_concurrencia)`.

### 3.7 Apagado ordenado y volcado

```
SIGTERM / SIGINT
  └─> Servidor.handle_exit()        (app/__main__.py)
        aceptando = False           -> desde ya, POST /tareas da 503
        uvicorn.should_exit = True
  └─> uvicorn cierra el socket de escucha (no entran conexiones nuevas)
      y espera hasta 5 s a los pedidos HTTP en vuelo
  └─> lifespan, bloque finally      (app/main.py)
        1. pool.detener(ESPERA_APAGADO): espera a las tareas en ejecución;
           las que no terminan a tiempo se cancelan ("apagado del servidor")
        2. se cancelan los workers ociosos (bloqueados en cola.get())
        3. se cierran el cliente HTTP, los WebSockets y el pool de procesos
        4. volcado a volcados/estado_<timestamp>.json
```

El handler de la señal **no hace casi nada**: asigna dos atributos. Corre en
el hilo principal en un momento arbitrario, así que no debe loguear, ni hacer
I/O, ni tocar el loop: es la regla de las funciones *async-signal-safe* de la
clase 5. El trabajo pesado lo hace el lifespan, ya dentro del loop. uvicorn
instala sus handlers con `signal.signal`; yo heredo su `Server` y extiendo
`handle_exit` en vez de pisarlos.

Las tareas que quedan `pendiente` en la cola **no se ejecutan**: quedan así en
el volcado. Al arrancar, si existe un volcado previo, se informa en el log:

```
INFO app.persistencia: volcado previo encontrado: estado_20261027_120513.json (del 2026-10-27T12:05:13): 17 tareas — 10 cancelada, 4 completada, 2 pendiente, 1 fallida
INFO app.persistencia:   2 de esas tareas no llegaron a terminar; no se re-encolan automáticamente
```

El volcado se escribe con `asyncio.to_thread` (escribir un archivo es I/O
bloqueante) y de forma **atómica**: primero a un `.tmp`, `fsync`, y después
`os.replace`, que es un `rename(2)`. Si el proceso muere a mitad, no queda un
JSON cortado.

En Docker, el `CMD` está en forma *exec* (`["python", "-m", "app"]`) para que
Python sea el PID 1 y reciba el SIGTERM de `docker stop` directamente; con la
forma *shell*, el PID 1 sería `/bin/sh`, que no reenvía la señal, y Docker
terminaría matando con SIGKILL. `stop_grace_period: 30s` le da tiempo al
apagado ordenado antes de ese SIGKILL.

### 3.8 La tarea propia: `chequear_ssl`

Abre una conexión TLS a cada host con `asyncio.open_connection(host, 443,
ssl=contexto, server_hostname=host)`, que es el `socket()` + `connect()` del
cliente de la clase 13 sin bloquear, más el handshake TLS. No manda nada: el
certificado viene en el handshake. Lee `notAfter` con `getpeercert()` y calcula
los días restantes.

Si el certificado **no valida** (vencido, autofirmado, nombre equivocado), se
informa el motivo y se hace un segundo handshake *sin verificar* para leer la
fecha igual: un certificado vencido es justamente lo que más interesa reportar.
Como la stdlib no parsea un certificado no verificado, ese caso usa
`cryptography`. El test levanta dos servidores TLS locales con una CA propia
(uno válido por 30 días y otro vencido hace 3) y comprueba ambos casos.

---

## 4. Mediciones

**Entorno:** Linux 6.18, 2 vCPU, Python 3.11.  Servidor y scripts en la misma
máquina; el servicio `sitios` también.

Los scripts están en `mediciones/` y guardan cada corrida en
`mediciones/resultados/`. Se corren dentro del contenedor:

```bash
docker compose exec api python mediciones/medir_io.py
PERMITIR_MODO_BLOQUEANTE=1 docker compose up -d --build     # para la medición 2
docker compose exec api python mediciones/medir_bloqueo.py
docker compose exec api python mediciones/medir_techo.py
```

### 4.1 Concurrencia I/O: 20 chequeos secuenciales contra 20 concurrentes

Una tarea `descargar` con 20 URLs del servicio `sitios`, cada una con una
demora fija entre 200 y 1000 ms (sorteadas con semilla, así cada corrida usa
las mismas). Se encola dos veces: con `concurrente: false` (un `for` con
`await` adentro) y con `concurrente: true` (`TaskGroup`). Cinco repeticiones.

| Vuelta | Secuencial | Concurrente | Suma de los 20 tiempos | La más lenta | Speedup |
|-------:|-----------:|------------:|-----------------------:|-------------:|--------:|
| 1 | 15 017 ms | 1 060 ms | 15 015 ms | 1 048 ms | 14,2× |
| 2 | 15 002 ms | 1 062 ms | 15 000 ms | 1 050 ms | 14,1× |
| 3 | 15 004 ms | 1 058 ms | 15 002 ms | 1 046 ms | 14,2× |
| 4 | 14 996 ms | 1 059 ms | 14 994 ms | 1 047 ms | 14,2× |
| 5 | 15 000 ms | 1 060 ms | 14 999 ms | 1 047 ms | 14,2× |
| **Mediana** | **14 948 ms** | **1 026 ms** | | **1 022 ms** | **14,6×** |

**Interpretación.** El secuencial tarda exactamente **la suma** (14 948 contra
14 946 ms) y el concurrente tarda **lo que la más lenta** (1 026 contra 1 022 ms):
lo que pide el enunciado. Los 4 ms de diferencia son el costo de crear 20
tasks y repartirlas.

El speedup no es "20× porque hay 20 URLs": es `suma / máximo`, y depende de
cómo se repartan las demoras. Con 20 URLs de 1 s cada una sería 20×; con una de
10 s y diecinueve de 10 ms sería apenas 1,02×. La concurrencia no hace más
rápida ninguna descarga: **solapa las esperas**. Mientras una URL espera su
respuesta, el loop no tiene nada que hacer con ella y atiende a las otras. Es
la misma cuenta de la clase 14 con threads, pero acá con 20 corrutinas en un
solo hilo y sin pagar un stack de megabytes por cada una.

### 4.2 El event loop bloqueado

Una tarea `hashear` de 5 millones de iteraciones de SHA-256 y, mientras corre,
`GET /tareas` en bucle (pausa de 50 ms entre pedidos) midiendo cuánto tarda cada
respuesta. Sin carga, `GET /tareas` responde en **1,9 ms** (mediana).

| Ejecutor | Duración del hash | Pedidos atendidos | Latencia p50 | p95 | Máxima |
|----------|------------------:|------------------:|-------------:|----:|-------:|
| `loop` — en la corrutina, **sin** executor | 3,54 s | **2** | 1 675,2 ms | 3 345,2 ms | **3 345,2 ms** |
| `hilo` — `asyncio.to_thread` | 3,79 s | 52 | 21,3 ms | 23,3 ms | 25,2 ms |
| `proceso` — `run_in_executor` + `ProcessPoolExecutor` | 4,82 s | 84 | **5 ms** | 6,5 ms | **10,3 ms** |

Los tres modos dieron el mismo hash.

**Interpretación.** Sin executor, el servidor **desapareció** durante 3,4
segundos: el primer `GET` llegó cuando el hash ya corría y no se atendió hasta
que terminó. En todo ese lapso se atendieron dos pedidos en total. No es que la
API "anduvo lenta": el hilo único estaba ocupado calculando, y uvicorn, que
corre en ese mismo hilo, ni siquiera podía hacer `accept()` de la conexión.
Desde afuera es indistinguible de un servidor colgado.

Con el executor, el cálculo **tarda lo mismo** (3,6 – 3,9 s: no se acelera nada,
incluso suma algo por los viajes al proceso) pero deja de bloquear a los demás:
la latencia máxima bajó de 3 366 ms a 10 ms, **336 veces**. Esa es la diferencia
entre concurrencia (asyncio) y paralelismo (procesos): asyncio intercala
esperas, pero no puede calcular dos cosas a la vez.

Entre `hilo` y `proceso` aparece el GIL: con un thread calculando, el hilo del
loop tiene que conseguir el GIL para atender cada pedido, y espera hasta ~5 ms
cada vez que lo pide. Por eso la mediana es 13,7 ms contra 3,8 ms. Con
**varios** cálculos a la vez la diferencia es mayor:

| 4 hashes de 2,5 M iteraciones simultáneos | Tiempo total |
|-------------------------------------------|-------------:|
| `hilo` (`to_thread`) | 15,78 s |
| `proceso` (`ProcessPoolExecutor`, 2 procesos) | **2,43 s** |

Con 2 cores, los procesos van el doble de rápido: corren en paralelo de verdad,
mientras que los threads se turnan el GIL y en la práctica calculan de a uno.
En una máquina con más cores la diferencia crece.

### 4.3 El techo del pool

**A. Tareas I/O (`esperar` de 1 s) con `WORKERS=8`:**

| N tareas a la vez | Tiempo total | Ideal `⌈N/8⌉ × 1 s` | Espera prom. en cola | Espera máx. |
|------------------:|-------------:|--------------------:|---------------------:|------------:|
| 1 | 1,00 s | 1 s | 0,00 s | 0,00 s |
| 2 | 1,00 s | 1 s | 0,00 s | 0,00 s |
| 4 | 1,00 s | 1 s | 0,00 s | 0,00 s |
| 8 | 1,00 s | 1 s | 0,00 s | 0,00 s |
| 16 | 2,01 s | 2 s | 0,50 s | 1,00 s |
| 32 | 4,01 s | 4 s | 1,50 s | 3,00 s |
| 64 | 8,03 s | 8 s | 3,50 s | 7,01 s |
| 128 | 16,05 s | 16 s | 7,51 s | 15,00 s |

El codo está exactamente en **N = WORKERS = 8**. Hasta ahí todo corre a la vez;
a partir de ahí las tareas hacen fila y el tiempo crece en escalones de un
segundo. La duración de cada tarea no cambia (1,00 s en todos los casos): lo que
crece es la **espera en la cola**. Pero este techo es una perilla, no un límite
de la máquina: un worker cuesta lo que una corrutina, unos cientos de bytes.

**¿Qué pasa si la perilla se sube?** `WORKERS=20000`, tareas de 10 s:

| N tareas | Tiempo de los POSTs | Tiempo total | Ideal | Duración mediana |
|---------:|--------------------:|-------------:|------:|-----------------:|
| 1 000 | 0,41 s | 10,51 s | 10 s | 10,019 s |
| 5 000 | 2,53 s | 12,66 s | 10 s | 10,024 s |
| 10 000 | 5,52 s | 15,70 s | 10 s | 10,024 s |
| 20 000 | 16,22 s | 26,42 s | 10 s | 10,030 s |

Veinte mil tareas corriendo a la vez en un hilo, y cada una sigue tardando 10,03
segundos (30 ms de atraso). El servidor ocupaba unos 200 MB. El techo pasó a
ser otro: **cuánto tarda el loop en aceptar los pedidos**. Los POSTs bajan de
2 440 por segundo (con 1 000 tareas vivas) a 1 230 por segundo (con 20 000),
porque el mismo hilo que parsea HTTP tiene que despertar a miles de tareas que
reportan progreso. **El límite real de la parte I/O es la CPU del único hilo
del event loop**: cuando se satura, todo se atrasa a la vez.

**B. Tareas CPU (`hashear` de 1 M iteraciones) con `PROCESOS=2` (2 cores):**

| N tareas a la vez | Tiempo total | Duración mediana | Total / N |
|------------------:|-------------:|-----------------:|----------:|
| 1 | 0,97 s | 0,97 s | 0,97 s |
| 2 | 0,97 s | 0,94 s | **0,49 s** |
| 4 | 0,93 s | 0,91 s | 0,23 s |
| 8 | 1,26 s | 1,21 s | 0,16 s |

Dos hashes tardan lo mismo que uno (corren en paralelo, uno por core); a partir
de ahí el total crece linealmente y el rendimiento se clava en ~0,4 s por tarea
= 0,76 / 2. Acá el techo **no son los 8 workers** (que siguen libres para
atender I/O) sino los **2 procesos**, y en el fondo los 2 cores: más procesos
que cores no agregan paralelismo, solo cambios de contexto.

**C. Ráfaga: 10 000 tareas cortas de golpe** (`esperar` de 0 s, 50 conexiones):

| | `MAX_COLA=10000` (default) | `MAX_COLA=1000` |
|---|---:|---:|
| Aceptadas / rechazadas con 503 | 10 000 / 0 | 1 544 / **8 456** |
| Tiempo de los POSTs | 5,72 s (1 748 tareas/s) | 3,73 s |
| Hasta vaciar la cola | 4,59 s | 3,88 s |
| Espera máxima en cola | 0,91 s | 6,27 s |
| `GET /estadisticas` durante la ráfaga: p50 / máx | 32,5 ms / 44,3 ms | 30,1 ms / 222,7 ms |
| Memoria del servidor (RSS) | 83 → 92 MB | 67 → 77 MB |

Con la cola grande entra todo, la API sigue respondiendo (p50 de 32 ms en vez
de 2 ms: el loop está ocupado parseando POSTs, pero no se cuelga) y la memoria
apenas se mueve. Con `MAX_COLA=1000`, la cola se llena y el **backpressure** hace
su trabajo: 8 456 pedidos rechazados con 503 y `Retry-After`, en vez de aceptar
trabajo que no se puede hacer a tiempo.

**Lo que se rompió primero fue el cliente de la medición.** La primera versión
del script mandaba los 10 000 POSTs con `asyncio.gather` sobre un
`httpx.AsyncClient`: dio **46 tareas/s**, y un `GET /estadisticas` tardó 139
segundos. Mirando `top`: el proceso cliente al **100% de CPU** y el servidor al
**20%**. Había dos problemas, los dos del lado de quien medía:

1. El sondeo de latencia usaba el mismo cliente que los POSTs, así que hacía
   fila detrás de ellos en el pool de conexiones de httpx. Medía esa fila, no al
   servidor. Ahora usa un cliente aparte.
2. Diez mil corrutinas esperando conexión en httpx degradan al propio cliente.
   Con un semáforo de 100 subió a 248 tareas/s; con un cliente HTTP/1.1 escrito
   a mano (`mediciones/comun.py`: 50 sockets keep-alive que sacan cuerpos de una
   `asyncio.Queue` y leen la respuesta por `Content-Length`, todo lo de las
   clases 13, 19 y 21) llegó a **2 428 tareas/s**, diez veces más.

**Respuesta a "si te mando 10 000 tareas de golpe, ¿qué se rompe primero?":** en
mi sistema, con la configuración por defecto, no se rompe nada: entran todas
(la cola es de 10 000) y se procesan en 4,6 s. Lo primero que se degrada es la
**latencia de la API**, porque el único hilo reparte su tiempo entre parsear
POSTs y correr workers. Si mandaras más que `MAX_COLA`, el excedente recibe
**503**. Si las tareas fueran CPU, el cuello serían los procesos. Lo que sí
congelaría el loop es listar las 10 000 de una vez: serializarlas lleva medio
segundo de CPU en el hilo del loop (sección 6), por eso `GET /tareas` no deja
pedir más de 1000.

---

## 5. Conceptos del curso aplicados

| Dónde | Qué | Clase |
|-------|-----|-------|
| `pool.py`: los workers consumen de una `asyncio.Queue` compartida | Productor-consumidor. Igual que con threads, pero sin lock: el loop no interrumpe entre `await`s | 11, 20, 21 |
| `pool.py`: `maxsize` + `put_nowait` → 503 | Backpressure: frenar al productor en vez de dejar crecer la cola | 21 (y `drain()` de la 20) |
| `pool.py`: `cola.task_done()` en un `finally` | Contrato de `join()` | 21 |
| `pool.py`: Task hija por tarea, `cancel()`, `CancelledError` relanzado | Cancelación cooperativa en el próximo `await` | 20 |
| `pool.py`: `asyncio.timeout()` + `expired()` | El timeout como caso particular de la cancelación | 20 |
| `pool.py`: `_vigilar_worker` | El "bug silencioso" de los futures cuyas excepciones nadie lee | 22 |
| `tareas/descargar.py`, `chequear_ssl.py`: `TaskGroup` | Concurrencia estructurada: si la tarea se cancela, ninguna descarga queda huérfana (con `gather` sí podrían quedar) | 21 |
| `tareas/descargar.py`: `Semaphore(max_concurrencia)` | Limitar la concurrencia, como en la clase 11 pero con `async with` | 11, 20 |
| `tareas/descargar.py`: `concurrente: false` | `for` + `await` contra `TaskGroup`: suma contra máximo (medición 1) | 18, 20 |
| `tareas/hashear.py`: `run_in_executor` + `ProcessPoolExecutor` | Sacar el CPU del loop; procesos y no threads por el GIL | 9, 21, 22 |
| `tareas/hashear.py`: bloques | `Future.cancel()` solo funciona si no arrancó | 22 |
| `tareas/hashear.py`: `hash_iterado` a nivel de módulo | Lo que va a otro proceso viaja pickleado | 22 |
| `main.py`: `mp_context=spawn` | Por qué no hacer `fork()` de un proceso con threads y un loop corriendo | 3, 7 |
| `main.py`: pool de procesos y cliente HTTP creados en el `lifespan` | Crear los pools una vez | 19, 22 |
| `tareas/esperar.py`: `asyncio.sleep` | Cede el control; `time.sleep` congelaría el loop | 18 |
| `tareas/chequear_ssl.py`: `open_connection` + `writer.close()` en `finally` | El cliente TCP de tres pasos y "siempre cerrar", sobre streams async; TLS como capa entre TCP y la aplicación | 12, 13, 20 |
| Todo el servidor | Un hilo atendiendo miles de conexiones: el event loop de uvicorn es un `_UnixSelectorEventLoop` sobre `epoll`, la respuesta a C10K | 14, 17, 19 |
| `__main__.py`: `handle_exit` solo asigna flags | Handlers *async-signal-safe*; el trabajo real se hace después, en el loop | 5, 20 |
| `persistencia.py`: `to_thread` + `os.replace` | I/O de disco fuera del loop; escritura atómica con `rename` | 21, bloque 0 |
| `main.py`: todos los endpoints `async def` sin nada bloqueante | Un `async def` con algo bloqueante adentro degrada a todo el servidor | 19 |
| `mediciones/comun.py`: cliente HTTP a mano | HTTP es texto; keep-alive; framing por `Content-Length` | 13, 19 |
| `eventos.py`: una cola acotada por cliente WebSocket, `put_nowait` | Un consumidor lento no frena a los productores: se lo desconecta | 20, 21 |
| `Dockerfile`: `CMD` en forma exec, `stop_grace_period` | La señal tiene que llegarle al proceso correcto | 1, 2, 5 |

---

## 6. Las preguntas de la corrección

**"Mostrame dónde tu código podría bloquear el event loop."**
1. `hashear` con `ejecutor: "loop"` (`tareas/hashear.py`): lo bloquea **a
   propósito**, solo existe para la medición 2 y está apagado por defecto (400
   si no se habilita).
2. `GET /tareas` con muchas tareas: serializar el listado a JSON es CPU en el
   loop. Medido: 1 000 tareas ~80 ms, 10 000 ~500 ms. Por eso `limite` tiene un
   máximo de 1000.
3. El volcado JSON al apagar: lo evité con `to_thread`.
4. `ssl.create_default_context()` lee el almacén de CAs del disco: se crea una
   sola vez al arrancar, con `to_thread`.
5. `Almacen.listar()` recorre el diccionario: O(n) sin `await`. Con 20 000 tareas
   en memoria es del orden de milisegundos.
Todo lo demás espera con `await` (red, `asyncio.sleep`, executor).

**"¿Qué pasa si cancelo una tarea justo cuando está a mitad de una descarga?"**
El `CancelledError` aparece en el `await` en el que estaba esa descarga (leyendo
un trozo del cuerpo). Al subir sale del `async with cliente.stream(...)`, que
cierra la respuesta y libera la conexión. El `TaskGroup` cancela al resto de las
URLs de esa tarea y espera a que todas terminen antes de propagar. El worker ve
`hija.cancelled()`, marca la tarea `cancelada` y queda libre. Hay un test que lo
verifica con un cuerpo que llega de a poco.

**"¿Por qué tu pool de workers no necesita un `Lock`?"** Sección 3.5: porque el
estado compartido solo se modifica en tramos sin `await`, y en asyncio el cambio
de contexto solo puede ocurrir en un `await`.

**"Si te mando 10 000 tareas de golpe, ¿qué se rompe primero?"** Sección 4.3 C.

**"¿Qué diferencia hay entre `asyncio.gather` y un `for` con `await` adentro?"**
El `for` con `await` espera a que termine cada una antes de *empezar* la
siguiente: el tiempo total es la suma. `gather` (o `TaskGroup`) las crea todas
como tasks y espera a que terminen juntas: las esperas se solapan y el total es
el de la más lenta. Medición 1: 14 948 ms contra 1 026 ms. Además, `gather` deja
a las hermanas corriendo si una falla; `TaskGroup` las cancela, por eso uso
`TaskGroup`.

**"¿Por qué `time.sleep()` en una corrutina es un bug y `asyncio.sleep()` no?"**
`time.sleep()` duerme al **hilo**, y en asyncio hay un solo hilo: se duermen el
loop y todas las tareas. `asyncio.sleep()` es una corrutina que registra un
timer y hace `yield` al loop; el loop atiende a los demás y despierta a esta
cuando vence el timer. Es la diferencia entre bloquear y ceder (clase 18), y la
medición 2 muestra lo que cuesta.

---

## 7. Limitaciones conocidas

- **Un solo proceso, estado en memoria.** No se puede correr con `uvicorn
  --workers 4`: cada proceso tendría su propio diccionario y su propia cola, y un
  `GET` podría caer en un proceso que no conoce la tarea (clase 19). Escalar
  horizontalmente requiere sacar el estado a algo compartido (Redis, una base).
- **Las tareas pendientes no sobreviven a un reinicio.** El volcado las guarda y
  el arranque las reporta, pero no las re-encola. Sería fácil hacerlo, pero
  re-ejecutar algo sin que nadie lo pida de nuevo tiene sus riesgos.
- **Un hash cancelado sigue corriendo hasta el final de su bloque** (~0,1 s) en el
  proceso. Bajar `BLOQUE_HASH` acorta eso a costa de más viajes al executor.
- **Sin autenticación ni rate limiting**: cualquiera que llegue al puerto puede
  encolar. Y `descargar` puede apuntar a cualquier URL, incluida la red interna
  (un riesgo de SSRF que un servicio real tendría que filtrar).
- **`GET /tareas` serializa en el loop** (ver arriba). La paginación está limitada
  a las últimas 1000; no hay cursor para recorrer más.
- **El historial se poda**: se guardan hasta `MAX_HISTORIAL` (20 000) tareas
  terminadas; las más viejas se descartan (las estadísticas sí son históricas).
- **El progreso de `esperar` despierta a la tarea cada 0,25–0,5 s.** Con 20 000
  tareas vivas son decenas de miles de despertares por segundo: parte de lo que
  frenó a los POSTs en la medición 3.
- **Las mediciones corrieron con cliente y servidor en la misma máquina** y se
  reparten los mismos cores.
- Los `docker compose` de la medición 2 necesitan `PERMITIR_MODO_BLOQUEANTE=1`, que
  no es el modo normal de uso.

---

## 8. Extensiones (bonus) y tests

| # | Extensión | Dónde |
|---|-----------|-------|
| 1 | **WebSocket `/eventos`**: estado inicial, cada transición, progreso (como mucho cada 250 ms por tarea) y estadísticas cada segundo. Lo consume la página de `/`, que se reconecta con backoff exponencial | `main.py`, `eventos.py`, `static/index.html` |
| 5 | **Métricas Prometheus** en `/metricas` | `main.py` |
| 6 | **Tests** con `pytest-asyncio`: 31 tests, muchos de cancelación, timeouts y fallas | `tests/` |
| 8 | **Tarea propia `chequear_ssl`** | `tareas/chequear_ssl.py` |

Los tests cubren, entre otras cosas: que el POST no espera a la tarea; cancelar
pendiente y en ejecución sin perder el worker; timeout → `fallida`; excepción en
la tarea y muerte del worker; cola llena; apagado ordenado; que el hash por
bloques dé el mismo resultado que de una vez; que con executor el loop no se
atrase más de 100 ms y sin executor sí; concurrente contra secuencial; que el
semáforo limite; que cancelar a mitad de descarga cierre la respuesta;
certificados válido y vencido contra servidores TLS locales; el volcado; la API
completa y el WebSocket.

```bash
docker compose run --rm api pytest -v       # ~12 s
```

---

## 9. Lo que aprendí

<!-- BORRADOR: estos párrafos tienen que ser tuyos. Reescribilos con lo que te
     pasó a vos haciendo el TP; dejé ideas para arrancar. -->

Lo que más me sorprendió fue la medición 2. Sabía de la clase 18 que un cálculo
dentro de una corrutina "bloquea el loop", pero no lo había sentido: ver que un
`GET` que normalmente tarda 2 ms tardaba 3,4 segundos, y que en todo ese tiempo
el servidor atendió dos pedidos, deja claro que asyncio no es "paralelo". Es un
solo hilo que es muy bueno esperando muchas cosas a la vez, y en el momento en
que alguien no cede el control, se cae todo.

La cancelación fue lo más difícil de hacer bien. Al principio el worker hacía
`await` directo de la tarea, y no había forma de distinguir "cancelaron la
tarea" de "me cancelaron a mí". Separar worker y tarea en dos Tasks y usar
`asyncio.wait` lo resolvió, y de paso entendí por qué es tan importante relanzar
el `CancelledError`. También que no todo se puede cancelar: un trabajo que ya está
en otro proceso sigue hasta que termina, y la única forma de acotar eso es
partirlo en pedazos.

Y aprendí a desconfiar de mis mediciones. El primer resultado de la ráfaga
decía que el servidor aceptaba 46 tareas por segundo; el problema era el cliente
que yo había escrito para medir. Mirar `top` mientras corría el script fue lo que
lo mostró.
