"""Tarea propia (bonus 8): `chequear_ssl`.

Abre una conexión TLS a cada host con `asyncio.open_connection` y devuelve
cuántos días faltan para que venza su certificado. Es la pregunta que se
hace todo el que mantiene un sitio: "¿cuándo se me vence el certificado?".

Conecta con varias clases:

* **Clase 13 (sockets TCP)**: `open_connection` hace el mismo
  `socket()` + `connect()` del cliente de tres pasos, pero sin bloquear.
  Lo que devuelve (reader, writer) es la API de streams de la clase 20
  sobre ese socket. Y como en la clase 13, el socket SIEMPRE se cierra:
  `writer.close()` va en un `finally`.
* **Clase 12 (modelo OSI)**: TLS es la capa que se mete entre TCP y HTTP.
  Acá la usamos sola, sin HTTP arriba: el handshake ya nos trae el
  certificado y no necesitamos pedir nada más.
* **Clase 21**: los hosts se chequean en un `TaskGroup`.

Si el certificado no valida (vencido, autofirmado, nombre equivocado), se
informa el motivo y se hace un segundo handshake *sin* verificar para poder
leer igual la fecha de vencimiento: un certificado vencido es justamente el
caso que más interesa reportar.
"""
from __future__ import annotations

import asyncio
import contextlib
import ssl
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from cryptography import x509
from cryptography.x509.oid import NameOID

if TYPE_CHECKING:
    from . import Contexto


def separar_host(entrada: str, puerto_defecto: int) -> tuple[str, int]:
    """Acepta 'ejemplo.com', 'ejemplo.com:8443' o directamente una URL."""
    entrada = entrada.strip()
    if '://' in entrada:
        partes = urlsplit(entrada)
        return partes.hostname or '', partes.port or puerto_defecto
    if entrada.count(':') == 1:
        host, _, puerto = entrada.partition(':')
        return host, int(puerto)
    return entrada, puerto_defecto


async def _handshake(host: str, puerto: int, contexto: ssl.SSLContext,
                     timeout: float) -> tuple[dict[str, Any] | None, bytes | None, str, str]:
    """Conecta, hace el handshake TLS y cierra. Devuelve el certificado."""
    async with asyncio.timeout(timeout):
        _reader, writer = await asyncio.open_connection(
            host, puerto, ssl=contexto, server_hostname=host)
    try:
        objeto_ssl: ssl.SSLObject = writer.get_extra_info('ssl_object')
        cert_dict = objeto_ssl.getpeercert()                 # {} si no se verificó
        cert_der = objeto_ssl.getpeercert(binary_form=True)  # siempre disponible
        cifrado = objeto_ssl.cipher()
        return cert_dict, cert_der, objeto_ssl.version() or '?', cifrado[0] if cifrado else '?'
    finally:
        writer.close()
        # El cierre TLS manda un close_notify; si el otro lado no contesta, no
        # vamos a esperar para siempre por cortesía.
        with contextlib.suppress(Exception):
            async with asyncio.timeout(2):
                await writer.wait_closed()


def _dias_hasta(vence: datetime) -> float:
    return (vence - datetime.now(timezone.utc)).total_seconds() / 86_400


def _desde_dict(cert: dict[str, Any]) -> dict[str, Any]:
    """Datos del certificado verificado, con el parser de la stdlib."""
    vence = datetime.fromtimestamp(ssl.cert_time_to_seconds(cert['notAfter']), timezone.utc)
    emisor = dict(par[0] for par in cert.get('issuer', ()))
    sujeto = dict(par[0] for par in cert.get('subject', ()))
    return {
        'vence': vence.isoformat(),
        'dias_restantes': int(_dias_hasta(vence) // 1),
        'emisor': emisor.get('organizationName') or emisor.get('commonName'),
        'sujeto': sujeto.get('commonName'),
        'nombres': [valor for tipo, valor in cert.get('subjectAltName', ()) if tipo == 'DNS'][:10],
    }


def _desde_der(der: bytes) -> dict[str, Any]:
    """Datos de un certificado NO verificado (la stdlib no lo parsea)."""
    cert = x509.load_der_x509_certificate(der)
    vence = cert.not_valid_after_utc

    def nombre(n: x509.Name) -> str | None:
        for oid in (NameOID.ORGANIZATION_NAME, NameOID.COMMON_NAME):
            atributos = n.get_attributes_for_oid(oid)
            if atributos:
                return str(atributos[0].value)
        return None

    return {
        'vence': vence.isoformat(),
        'dias_restantes': int(_dias_hasta(vence) // 1),
        'emisor': nombre(cert.issuer),
        'sujeto': nombre(cert.subject),
    }


async def chequear_host(entrada: str, puerto_defecto: int, ctx: 'Contexto') -> dict[str, Any]:
    """Chequea un host. Nunca lanza (salvo CancelledError, que debe pasar)."""
    host, puerto = separar_host(entrada, puerto_defecto)
    base: dict[str, Any] = {'host': host, 'puerto': puerto}
    timeout = ctx.config.timeout_http
    inicio = time.perf_counter()
    try:
        cert, _der, version, cifrado = await _handshake(host, puerto, ctx.ssl_verificado, timeout)
        return {**base, 'valido': True, **_desde_dict(cert or {}), 'tls': version,
                'cifrado': cifrado, 'tiempo_ms': round((time.perf_counter() - inicio) * 1000, 1)}
    except ssl.SSLCertVerificationError as exc:
        motivo = exc.verify_message or str(exc)
        try:
            _cert, der, version, cifrado = await _handshake(
                host, puerto, ctx.ssl_sin_verificar, timeout)
            datos = _desde_der(der) if der else {}
        except (OSError, TimeoutError, ValueError) as exc2:
            datos = {'error': f'{type(exc2).__name__}: {exc2}'}
            version = cifrado = None
        return {**base, 'valido': False, 'motivo': motivo, **datos, 'tls': version,
                'cifrado': cifrado, 'tiempo_ms': round((time.perf_counter() - inicio) * 1000, 1)}
    except TimeoutError:
        return {**base, 'valido': False, 'error': f'sin respuesta en {timeout:g}s'}
    except (OSError, ssl.SSLError, ValueError) as exc:
        # DNS que no resuelve, conexión rechazada, el puerto no habla TLS...
        return {**base, 'valido': False, 'error': f'{type(exc).__name__}: {exc}'}


async def ejecutar(params: dict[str, Any], ctx: 'Contexto') -> dict[str, Any]:
    hosts: list[str] = params['hosts']
    puerto: int = params.get('puerto', 443)
    resultados: list[dict[str, Any] | None] = [None] * len(hosts)
    hechos = 0

    async def uno(i: int, entrada: str) -> None:
        nonlocal hechos
        resultados[i] = await chequear_host(entrada, puerto, ctx)
        hechos += 1
        ctx.reportar(hechos / len(hosts))

    async with asyncio.TaskGroup() as grupo:
        for i, entrada in enumerate(hosts):
            grupo.create_task(uno(i, entrada))

    validos = [r for r in resultados if r and r.get('valido')]
    con_fecha = [r for r in resultados if r and r.get('dias_restantes') is not None]
    proximo = min(con_fecha, key=lambda r: r['dias_restantes'], default=None)
    return {
        'resumen': {
            'total': len(hosts),
            'validos': len(validos),
            'invalidos': len(hosts) - len(validos),
            'proximo_a_vencer': (
                {'host': proximo['host'], 'dias_restantes': proximo['dias_restantes']}
                if proximo else None),
        },
        'hosts': resultados,
    }
