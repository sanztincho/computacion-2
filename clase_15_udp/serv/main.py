#!/usr/bin/env python3
"""Servidor eco UDP."""
import socket
import struct

def enviar_numerado(sock, seq, payload, destino):
    """Prefija el número de secuencia al payload."""
    sock.sendto(struct.pack('!I', seq) + payload, destino)

def recibir_numerado(sock):
    datos, origen = sock.recvfrom(65535)
    (seq,) = struct.unpack('!I', datos[:4])
    return seq, datos[4:], origen

def pedir_con_reintentos(sock, mensaje, destino, intentos=3, timeout=1.0):
    """Manda un mensaje y espera respuesta, reintentando si se pierde."""
    sock.settimeout(timeout)
    for intento in range(1, intentos + 1):
        sock.sendto(mensaje, destino)
        try:
            respuesta, _ = sock.recvfrom(65535)
            return respuesta
        except TimeoutError:
            print(f'Intento {intento}: sin respuesta, reintento')
    return None

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', 8080))
    print('Escuchando en 0.0.0.0:8080')

    while True:
        datos, origen = s.recvfrom(4096)
        print(f'{origen}: {datos!r}')
        s.sendto(datos, origen)              # eco al remitente
