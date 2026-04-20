# Clase 3: Procesos - Autoevaluación

Responde estas preguntas para verificar tu comprensión. Las respuestas están al final.

---

## Parte 1: Conceptos básicos (6 preguntas)

### Pregunta 1
¿Cuál es la diferencia entre un programa y un proceso?

a) Son lo mismo, solo nombres diferentes
b) El programa es código en disco, el proceso es una instancia en ejecución con su contexto
c) El proceso es más grande que el programa
d) El programa puede correr, el proceso no

### Pregunta 2
¿Qué estructura organiza los procesos en Linux?

a) Lista enlazada
b) Array circular
c) Árbol jerárquico (cada proceso tiene un padre)
d) Grafo sin estructura específica

### Pregunta 3
¿Qué proceso es el ancestro de todos los demás en Linux?

a) El shell
b) El kernel
c) init/systemd (PID 1)
d) El proceso de login

### Pregunta 4
¿Qué información NO contiene un proceso?

a) Su espacio de memoria
b) Los file descriptors abiertos
c) El código fuente del programa
d) Su PID y PPID

### Pregunta 5
¿Qué es un proceso zombie?

a) Un proceso que consume muchos recursos
b) Un proceso terminado cuyo padre no recogió su estado de salida
c) Un proceso que no responde
d) Un proceso sin memoria asignada

### Pregunta 6
¿Qué comando muestra el árbol de procesos con PIDs?

a) `ps aux`
b) `pstree -p`
c) `top`
d) `tree /proc`

---

## Parte 2: fork() (6 preguntas)

### Pregunta 7
¿Qué hace la llamada fork()?

a) Ejecuta un nuevo programa
b) Crea una copia del proceso actual
c) Termina el proceso
d) Cambia el PID del proceso

### Pregunta 8
¿Qué retorna fork() en el proceso HIJO?

a) El PID del padre
b) El PID del hijo
c) 0
d) -1

### Pregunta 9
¿Qué retorna fork() en el proceso PADRE?

a) 0
b) El PID del hijo creado
c) El PID del padre
d) El número de hijos

### Pregunta 10
¿Qué significa Copy-on-Write (COW)?

a) La memoria se copia inmediatamente al hacer fork
b) La memoria se comparte y solo se copia cuando uno de los procesos escribe
c) El padre no puede escribir después del fork
d) Solo el hijo puede modificar memoria

### Pregunta 11
Después de un fork(), ¿cuántos procesos ejecutan la línea que sigue al fork?

a) Solo el padre
b) Solo el hijo
c) Ambos (padre e hijo)
d) Ninguno

### Pregunta 12
¿Por qué usamos `os._exit()` en el hijo en lugar de `sys.exit()`?

a) Es más rápido
b) `_exit()` termina inmediatamente sin ejecutar handlers de limpieza que podrían afectar al padre
c) `sys.exit()` no funciona después del fork
d) Es solo una convención de estilo

---

## Parte 3: exec() (4 preguntas)

### Pregunta 13
¿Qué hace exec()?

a) Crea un nuevo proceso
b) Reemplaza el programa del proceso actual por otro
c) Duplica el proceso
d) Termina el proceso

### Pregunta 14
Después de un exec() exitoso, ¿qué permanece igual?

a) El programa en memoria
b) Las variables
c) El PID del proceso
d) El stack

### Pregunta 15
¿Qué significa la "p" en `execlp()` o `execvp()`?

a) Process - trabaja con procesos
b) Path - busca el ejecutable en PATH
c) Parallel - ejecuta en paralelo
d) Pipe - conecta con pipes

### Pregunta 16
Si exec() falla, ¿qué sucede?

a) El proceso termina automáticamente
b) Se crea un nuevo proceso
c) La función retorna y el programa original continúa
d) El sistema se reinicia

---

## Parte 4: wait() (4 preguntas)

### Pregunta 17
¿Por qué el padre debe llamar a wait() después de que un hijo termina?

a) Para darle más tiempo de CPU al hijo
b) Para recoger el estado de salida y evitar zombies
c) Para reiniciar al hijo
d) No es necesario, es opcional

### Pregunta 18
¿Qué retorna os.wait()?

a) Solo el código de salida
b) Una tupla (PID del hijo, status)
c) El tiempo que tardó el hijo
d) Un booleano de éxito

### Pregunta 19
¿Qué hace os.waitpid(pid, os.WNOHANG)?

a) Espera indefinidamente al hijo específico
b) Retorna inmediatamente si el hijo no terminó
c) Mata al hijo si no terminó
d) Espera a cualquier hijo

### Pregunta 20
¿Qué función extrae el código de salida del status retornado por wait()?

a) `os.WEXITSTATUS(status)`
b) `os.exit_code(status)`
c) `status.code`
d) `os.get_exit(status)`

---

## Parte 5: Patrón fork-exec (5 preguntas)

### Pregunta 21
¿Cuál es el orden correcto para ejecutar un programa externo?

a) exec, fork, wait
b) wait, fork, exec
c) fork, exec (en hijo), wait (en padre)
d) exec, wait, fork

### Pregunta 22
¿Por qué el comando `cd` debe ser interno al shell?

a) Es más rápido como interno
b) Si fuera externo, cambiaría el directorio del hijo (que termina), no del shell
c) `cd` no existe como programa
d) Es una limitación de Linux

### Pregunta 23
¿Qué módulo de Python simplifica el patrón fork-exec-wait?

a) os
b) sys
c) subprocess
d) multiprocessing

### Pregunta 24
¿Cuál es la principal ventaja de usar subprocess sobre fork/exec manual?

a) Es más rápido
b) Es más simple, portable, y maneja muchos casos edge
c) Usa menos memoria
d) Permite más procesos simultáneos

### Pregunta 25
¿Qué parámetro de subprocess.run() captura stdout y stderr?

a) `output=True`
b) `capture_output=True`
c) `get_output=True`
d) `stdout=True`

---

## Respuestas

<details>
<summary>Click para ver respuestas</summary>

### Parte 1: Conceptos básicos
1. **b** - El programa es código en disco, el proceso es una instancia en ejecución
2. **c** - Árbol jerárquico (cada proceso tiene un padre)
3. **c** - init/systemd (PID 1)
4. **c** - El código fuente del programa (no está en memoria en esa forma)
5. **b** - Un proceso terminado cuyo padre no recogió su estado de salida
6. **b** - `pstree -p`

### Parte 2: fork()
7. **b** - Crea una copia del proceso actual
8. **c** - 0
9. **b** - El PID del hijo creado
10. **b** - La memoria se comparte y solo se copia cuando uno escribe
11. **c** - Ambos (padre e hijo)
12. **b** - `_exit()` termina inmediatamente sin ejecutar handlers de limpieza

### Parte 3: exec()
13. **b** - Reemplaza el programa del proceso actual por otro
14. **c** - El PID del proceso
15. **b** - Path - busca el ejecutable en PATH
16. **c** - La función retorna y el programa original continúa

### Parte 4: wait()
17. **b** - Para recoger el estado de salida y evitar zombies
18. **b** - Una tupla (PID del hijo, status)
19. **b** - Retorna inmediatamente si el hijo no terminó
20. **a** - `os.WEXITSTATUS(status)`

### Parte 5: Patrón fork-exec
21. **c** - fork, exec (en hijo), wait (en padre)
22. **b** - Si fuera externo, cambiaría el directorio del hijo, no del shell
23. **c** - subprocess
24. **b** - Es más simple, portable, y maneja muchos casos edge
25. **b** - `capture_output=True`

### Puntuación
- 23-25: Excelente comprensión de procesos
- 18-22: Buen nivel, listo para temas más avanzados
- 13-17: Necesitas repasar algunos conceptos
- <13: Revisa el material nuevamente antes de continuar

</details>

---

*Computación II - 2026 - Clase 3*
