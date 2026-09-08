#!/usr/bin/env python3
"""
Ejecutor de comandos en paralelo.
Uso: python3 paralelo.py "cmd1" "cmd2" ...
"""
import os
import sys
import time

def main():
    if len(sys.argv) < 2:
        print(f"Uso: {sys.argv[0]} comando1 [comando2 ...]")
        sys.exit(1)

    comandos = sys.argv[1:]
    procesos = {}  # pid -> comando

    # Iniciar temporizador
    inicio = time.time()

    # Crear un hijo por cada comando
    for cmd in comandos:
        pid = os.fork()

        if pid == 0:
            # Hijo: ejecutar comando
            partes = cmd.split()
            try:
                os.execvp(partes[0], partes)
            except OSError as e:
                print(f"Error ejecutando '{cmd}': {e}", file=sys.stderr)
                os._exit(127)
        else:
            # Padre: registrar el hijo
            procesos[pid] = cmd
            print(f"[{pid}] Iniciado: {cmd}")

    # Esperar a todos los hijos
    exitosos = 0
    fallidos = 0
    while procesos:
        pid, status = os.wait()
        cmd = procesos.pop(pid)
        if os.WIFEXITED(status):
            codigo = os.WEXITSTATUS(status)
            if codigo == 0:
                exitosos += 1
            else:
                fallidos += 1
        else:
            codigo = -1
            fallidos += 1
        print(f"[{pid}] Terminado: {cmd} (código: {codigo})")

    # Calcular tiempo total
    duracion = time.time() - inicio

    # Mostrar resumen
    total = len(comandos)
    print(f"\nResumen:")
    print(f"- Comandos ejecutados: {total}")
    print(f"- Exitosos: {exitosos}")
    print(f"- Fallidos: {fallidos}")
    print(f"- Tiempo total: {duracion:.2f}s")

if __name__ == "__main__":
    main()