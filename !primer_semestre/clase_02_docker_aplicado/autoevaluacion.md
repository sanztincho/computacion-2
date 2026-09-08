# Clase 2: Docker Aplicado - Autoevaluación

Responde estas preguntas para verificar tu comprensión. Las respuestas están al final.

---

## Parte 1: Volúmenes (5 preguntas)

### Pregunta 1
¿Qué problema fundamental resuelven los volúmenes en Docker?

a) Hacen los contenedores más rápidos
b) Permiten persistir datos más allá del ciclo de vida del contenedor
c) Reducen el tamaño de las imágenes
d) Mejoran la seguridad

### Pregunta 2
¿Cuál es la diferencia principal entre un bind mount y un named volume?

a) Los bind mounts son más rápidos
b) Los bind mounts montan una ruta específica del host, los named volumes son gestionados por Docker
c) Los named volumes no persisten datos
d) No hay diferencia, son sinónimos

### Pregunta 3
¿Qué comando lista todos los volúmenes de Docker?

a) `docker volumes`
b) `docker volume list`
c) `docker volume ls`
d) `docker show volumes`

### Pregunta 4
En la opción `-v /host/path:/container/path`, ¿cuál es la ruta del contenedor?

a) `/host/path`
b) `/container/path`
c) Ambas son del contenedor
d) Depende del orden

### Pregunta 5
¿Qué sucede con un named volume cuando eliminas el contenedor que lo usa?

a) Se elimina automáticamente
b) Permanece disponible para otros contenedores
c) Se corrompe
d) Se convierte en bind mount

---

## Parte 2: Redes (4 preguntas)

### Pregunta 6
¿Qué ventaja tiene crear una red personalizada frente a usar la red bridge por defecto?

a) Es más rápida
b) Permite resolución DNS por nombre de contenedor
c) Usa menos memoria
d) Es más segura automáticamente

### Pregunta 7
¿Qué comando crea una red llamada "mi_red"?

a) `docker network new mi_red`
b) `docker network create mi_red`
c) `docker create network mi_red`
d) `docker net create mi_red`

### Pregunta 8
Si dos contenedores están en la misma red personalizada, ¿cómo se conectan entre sí?

a) Solo por IP
b) Por nombre de contenedor (DNS automático)
c) No pueden conectarse
d) Solo a través del host

### Pregunta 9
¿Qué tipo de red usarías si necesitas que un contenedor comparta el stack de red del host?

a) bridge
b) host
c) none
d) overlay

---

## Parte 3: Dockerfile (5 preguntas)

### Pregunta 10
¿Qué instrucción establece el directorio de trabajo dentro del contenedor?

a) `CD /app`
b) `DIR /app`
c) `WORKDIR /app`
d) `CHDIR /app`

### Pregunta 11
¿Cuál es la diferencia entre `COPY` y `ADD`?

a) No hay diferencia
b) `ADD` puede extraer archivos tar y descargar URLs, `COPY` solo copia
c) `COPY` es más nuevo y reemplaza a `ADD`
d) `ADD` solo funciona con directorios

### Pregunta 12
¿Por qué es importante el orden de las instrucciones en un Dockerfile?

a) Docker las ejecuta en paralelo
b) El orden afecta el cache de capas - lo que cambia menos va primero
c) Solo importa que FROM sea primero
d) El orden no importa

### Pregunta 13
¿Qué diferencia hay entre `CMD` y `ENTRYPOINT`?

a) Son exactamente iguales
b) `CMD` puede sobrescribirse fácilmente, `ENTRYPOINT` define el ejecutable base
c) `ENTRYPOINT` es obsoleto
d) `CMD` solo acepta un argumento

### Pregunta 14
¿Qué hace la instrucción `EXPOSE 8000`?

a) Publica automáticamente el puerto 8000
b) Documenta que el contenedor escucha en el puerto 8000
c) Bloquea el puerto 8000
d) Redirige el puerto 8000 al 80

---

## Parte 4: Docker Compose (6 preguntas)

### Pregunta 15
¿Qué problema resuelve Docker Compose?

a) Hace las imágenes más pequeñas
b) Orquesta múltiples contenedores como una aplicación unificada
c) Reemplaza a Kubernetes
d) Comprime los contenedores

### Pregunta 16
¿Qué comando levanta todos los servicios definidos en docker-compose.yml?

a) `docker-compose start`
b) `docker-compose run`
c) `docker-compose up`
d) `docker-compose launch`

### Pregunta 17
¿Qué hace la opción `-d` en `docker-compose up -d`?

a) Modo debug
b) Modo detached (segundo plano)
c) Modo desarrollo
d) Elimina contenedores previos

### Pregunta 18
¿Qué significa `depends_on` en un servicio de Compose?

a) Instala dependencias de Python
b) Define el orden de inicio de contenedores
c) Copia archivos de otro servicio
d) Comparte volúmenes

### Pregunta 19
¿Cómo defines una variable de entorno en docker-compose.yml?

a) `vars: [MI_VAR=valor]`
b) `environment: - MI_VAR=valor`
c) `env: MI_VAR=valor`
d) `export MI_VAR=valor`

### Pregunta 20
¿Qué archivo se aplica automáticamente junto con docker-compose.yml?

a) docker-compose.prod.yml
b) docker-compose.override.yml
c) docker-compose.local.yml
d) docker-compose.dev.yml

---

## Respuestas

<details>
<summary>Click para ver respuestas</summary>

### Parte 1: Volúmenes
1. **b** - Permiten persistir datos más allá del ciclo de vida del contenedor
2. **b** - Los bind mounts montan una ruta específica del host, los named volumes son gestionados por Docker
3. **c** - `docker volume ls`
4. **b** - `/container/path` (formato: host:contenedor)
5. **b** - Permanece disponible para otros contenedores

### Parte 2: Redes
6. **b** - Permite resolución DNS por nombre de contenedor
7. **b** - `docker network create mi_red`
8. **b** - Por nombre de contenedor (DNS automático)
9. **b** - host

### Parte 3: Dockerfile
10. **c** - `WORKDIR /app`
11. **b** - `ADD` puede extraer archivos tar y descargar URLs, `COPY` solo copia
12. **b** - El orden afecta el cache de capas - lo que cambia menos va primero
13. **b** - `CMD` puede sobrescribirse fácilmente, `ENTRYPOINT` define el ejecutable base
14. **b** - Documenta que el contenedor escucha en el puerto 8000

### Parte 4: Docker Compose
15. **b** - Orquesta múltiples contenedores como una aplicación unificada
16. **c** - `docker-compose up`
17. **b** - Modo detached (segundo plano)
18. **b** - Define el orden de inicio de contenedores
19. **b** - `environment: - MI_VAR=valor`
20. **b** - docker-compose.override.yml

### Puntuación
- 18-20: Excelente dominio de Docker aplicado
- 14-17: Buen nivel, listo para usar Docker en proyectos
- 10-13: Necesitas repasar algunos conceptos
- <10: Revisa el material y practica más

</details>

---

*Computación II - 2026 - Clase 2*
