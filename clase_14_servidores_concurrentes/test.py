#!/usr/bin/env python3
"""Servidor eco: un proceso por cliente, con fork()."""
import os
import signal
import socket

def atender(conn):
    while True:
        datos = conn.recv(4096)
        if not datos:
            break
        conn.sendall(datos)

# Evitar procesos zombie: el kernel se encarga de los hijos terminados.
#signal.signal(signal.SIGCHLD, signal.SIG_IGN)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind(('0.0.0.0', 8080))
    servidor.listen(128)
    print(f'PADRE pid={os.getpid()}')

    while True:
        conn, direccion = servidor.accept()
        pid = os.fork()

        if pid == 0:
            # ---- HIJO ----
            servidor.close()        # el hijo NO necesita el socket que escucha
            atender(conn)
            conn.close()
            os._exit(0)             # salir sin ejecutar cleanup del padre
        else:
            # ---- PADRE ----
            conn.close()            # el padre NO necesita el socket del cliente
            print(f'Cliente {direccion} atendido por hijo pid={pid}')

