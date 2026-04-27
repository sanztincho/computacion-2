#!/usr/bin/env python3
"""Pipeline de dos comandos: cmd1 | cmd2."""
import os


def pipeline_dos_comandos(cmd1, args1, cmd2, args2):
    """Ejecuta cmd1 | cmd2 usando pipes y fork."""

    # Crear un pipe para conectar stdout de cmd1 con stdin de cmd2
    read_fd, write_fd = os.pipe()

    # Primer proceso: ejecuta cmd1
    pid1 = os.fork()
    if pid1 == 0:
        # En el hijo 1: no necesita el extremo de lectura del pipe
        os.close(read_fd)

        # Redirigir stdout al extremo de escritura del pipe
        os.dup2(write_fd, 1)
        os.close(write_fd)

        # Reemplazar el hijo con el primer comando
        os.execvp(cmd1, [cmd1] + args1)
        os._exit(1)

    # Segundo proceso: ejecuta cmd2
    pid2 = os.fork()
    if pid2 == 0:
        # En el hijo 2: no necesita el extremo de escritura del pipe
        os.close(write_fd)

        # Redirigir stdin al extremo de lectura del pipe
        os.dup2(read_fd, 0)
        os.close(read_fd)

        os.execvp(cmd2, [cmd2] + args2)
        os._exit(1)

    # En el padre: ya no necesita ninguno de los extremos del pipe
    os.close(read_fd)
    os.close(write_fd)

    # Esperar a que los hijos terminen
    os.waitpid(pid1, 0)
    os.waitpid(pid2, 0)


if __name__ == "__main__":
    print("=== Ejemplo: ls -la | grep '.py' ===")
    pipeline_dos_comandos("ls", ["-la"], "grep", [".py"])
