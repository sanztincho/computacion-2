"""Tests de cada tipo de tarea."""
from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import ssl
import time

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from app import persistencia
from app.tareas.chequear_ssl import separar_host

from .conftest import esperar_estado


# --------------------------------------------------------------- hashear

def _esperado(texto: str, n: int) -> str:
    dato = texto.encode()
    for _ in range(n):
        dato = hashlib.sha256(dato).digest()
    return dato.hex()


@pytest.mark.parametrize('ejecutor', ['proceso', 'hilo'])
async def test_hashear_por_bloques_da_el_mismo_hash(crear_pool, ejecutor):
    # 50.000 iteraciones en bloques de 20.000: 3 viajes al executor.
    async with crear_pool() as pool:
        t = pool.encolar('hashear', {'texto': 'hola', 'iteraciones': 50_000,
                                     'ejecutor': ejecutor}, None)
        await esperar_estado(pool, t.id, 'completada')
        assert t.resultado['hash'] == _esperado('hola', 50_000)
        assert t.resultado['bloques'] == 3


async def _peor_atraso_del_loop(mientras: asyncio.Future) -> float:
    """Se despierta cada 10 ms y mide cuánto tarde lo despiertan."""
    peor = 0.0
    while not mientras.done():
        antes = time.perf_counter()
        await asyncio.sleep(0.01)
        peor = max(peor, time.perf_counter() - antes - 0.01)
    return peor


async def test_hashear_en_proceso_no_bloquea_el_loop(crear_pool):
    async with crear_pool() as pool:
        t = pool.encolar('hashear', {'texto': 'x', 'iteraciones': 1_500_000}, None)
        listo = asyncio.ensure_future(esperar_estado(pool, t.id, 'completada'))
        atraso = await _peor_atraso_del_loop(listo)
        assert t.estado.value == 'completada'
        assert atraso < 0.1, f'el loop se atrasó {atraso * 1000:.0f} ms'


async def test_hashear_en_loop_si_bloquea(crear_pool):
    """El contraejemplo: lo que pasa sin executor."""
    async with crear_pool(permitir_modo_bloqueante=True) as pool:
        t = pool.encolar('hashear', {'texto': 'x', 'iteraciones': 1_000_000,
                                     'ejecutor': 'loop'}, None)
        listo = asyncio.ensure_future(esperar_estado(pool, t.id, 'completada'))
        atraso = await _peor_atraso_del_loop(listo)
        assert atraso > 0.3, 'el loop debería haberse congelado durante el cálculo'


async def test_hashear_modo_loop_deshabilitado_por_defecto(crear_pool):
    async with crear_pool() as pool:
        t = pool.encolar('hashear', {'texto': 'x', 'iteraciones': 10, 'ejecutor': 'loop'}, None)
        await esperar_estado(pool, t.id, 'fallida')
        assert 'deshabilitado' in t.error


async def test_hashear_se_cancela_entre_bloques(crear_pool):
    async with crear_pool() as pool:
        t = pool.encolar('hashear', {'texto': 'x', 'iteraciones': 100_000_000}, None)
        await esperar_estado(pool, t.id, 'ejecutando')
        await asyncio.sleep(0.2)
        inicio = time.perf_counter()
        await pool.cancelar(t.id)
        assert t.estado.value == 'cancelada'
        # Como mucho, lo que tarda un bloque de 20.000 iteraciones.
        assert time.perf_counter() - inicio < 0.5


# --------------------------------------------------------------- descargar

def _transporte_lento(demora: float) -> httpx.MockTransport:
    async def manejar(pedido: httpx.Request) -> httpx.Response:
        if pedido.url.path == '/404':
            return httpx.Response(404, content=b'no')
        if pedido.url.path == '/caido':
            raise httpx.ConnectError('conexión rechazada', request=pedido)
        await asyncio.sleep(demora)
        return httpx.Response(200, content=b'x' * 1234)
    return httpx.MockTransport(manejar)


async def test_descargar_concurrente_vs_secuencial(crear_pool):
    urls = [f'http://sitio/{i}' for i in range(10)]
    async with crear_pool(transporte=_transporte_lento(0.1)) as pool:
        conc = pool.encolar('descargar', {'urls': urls, 'concurrente': True,
                                          'max_concurrencia': 20}, None)
        sec = pool.encolar('descargar', {'urls': urls, 'concurrente': False}, None)
        await esperar_estado(pool, conc.id, 'completada')
        await esperar_estado(pool, sec.id, 'completada')
        t_conc = conc.resultado['resumen']['tiempo_total_ms']
        t_sec = sec.resultado['resumen']['tiempo_total_ms']
        assert t_conc < 300            # ~ la más lenta (100 ms)
        assert t_sec > 950             # ~ la suma (1000 ms)


async def test_descargar_semaforo_limita(crear_pool):
    urls = [f'http://sitio/{i}' for i in range(6)]
    async with crear_pool(transporte=_transporte_lento(0.1)) as pool:
        t = pool.encolar('descargar', {'urls': urls, 'max_concurrencia': 2}, None)
        await esperar_estado(pool, t.id, 'completada')
        # 6 URLs, de a 2: tres tandas de 100 ms
        assert 280 < t.resultado['resumen']['tiempo_total_ms'] < 500


async def test_descargar_informa_errores_sin_fallar(crear_pool):
    urls = ['http://sitio/ok', 'http://sitio/404', 'http://sitio/caido']
    async with crear_pool(transporte=_transporte_lento(0)) as pool:
        t = pool.encolar('descargar', {'urls': urls}, None)
        await esperar_estado(pool, t.id, 'completada')
        ok, no_esta, caido = t.resultado['urls']
        assert ok['ok'] and ok['codigo'] == 200 and ok['tamanio'] == 1234
        assert not no_esta['ok'] and no_esta['codigo'] == 404
        assert not caido['ok'] and caido['codigo'] is None and 'ConnectError' in caido['error']
        assert t.resultado['resumen']['caidas'] == 2


class _CuerpoLento(httpx.AsyncByteStream):
    """Un cuerpo que llega de a poco y registra si lo cerraron."""
    def __init__(self) -> None:
        self.cerrado = False
        self.trozos = 0

    async def __aiter__(self):
        for _ in range(1000):
            await asyncio.sleep(0.01)
            self.trozos += 1
            yield b'z' * 100

    async def aclose(self) -> None:
        self.cerrado = True


async def test_cancelar_a_mitad_de_descarga_cierra_la_respuesta(crear_pool):
    cuerpos: list[_CuerpoLento] = []

    async def manejar(pedido):
        cuerpo = _CuerpoLento()
        cuerpos.append(cuerpo)
        return httpx.Response(200, stream=cuerpo)

    async with crear_pool(transporte=httpx.MockTransport(manejar)) as pool:
        t = pool.encolar('descargar', {'urls': ['http://a/', 'http://b/']}, None)
        await esperar_estado(pool, t.id, 'ejecutando')
        await asyncio.sleep(0.15)
        await pool.cancelar(t.id)
        assert t.estado.value == 'cancelada'
        assert len(cuerpos) == 2
        assert all(0 < c.trozos < 1000 for c in cuerpos)    # estaban a la mitad
        assert all(c.cerrado for c in cuerpos)              # y se cerraron


# ------------------------------------------------------------ chequear_ssl

def _certificado(nombre: str, clave_emisor, clave, dias_desde: int, dias_hasta: int,
                 es_ca: bool = False):
    ahora = dt.datetime.now(dt.timezone.utc)
    emisor = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'TP2 CA'),
                        x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'TP2 CA')])
    sujeto = emisor if es_ca else x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, nombre),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'TP2 Test')])
    constructor = (
        x509.CertificateBuilder()
        .subject_name(sujeto)
        .issuer_name(emisor)
        .public_key(clave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ahora + dt.timedelta(days=dias_desde))
        .not_valid_after(ahora + dt.timedelta(days=dias_hasta))
        .add_extension(x509.BasicConstraints(ca=es_ca, path_length=None), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(clave.public_key()),
                       critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(
            clave_emisor.public_key()), critical=False)
    )
    if es_ca:
        constructor = constructor.add_extension(x509.KeyUsage(
            digital_signature=True, key_cert_sign=True, crl_sign=True,
            content_commitment=False, key_encipherment=False, data_encipherment=False,
            key_agreement=False, encipher_only=False, decipher_only=False), critical=True)
    else:
        constructor = constructor.add_extension(
            x509.SubjectAlternativeName([x509.DNSName('localhost')]), critical=False)
    return constructor.sign(clave_emisor, hashes.SHA256())


@pytest.fixture
def pki(tmp_path):
    """Una CA propia y dos certificados para 'localhost': uno válido por 30
    días y otro que venció hace 3."""
    clave_ca = ec.generate_private_key(ec.SECP256R1())
    ca = _certificado('TP2 CA', clave_ca, clave_ca, -10, 365, es_ca=True)
    archivos = {}
    for nombre, (desde, hasta) in {'valido': (-1, 30), 'vencido': (-60, -3)}.items():
        clave = ec.generate_private_key(ec.SECP256R1())
        cert = _certificado('localhost', clave_ca, clave, desde, hasta)
        ruta_cert, ruta_clave = tmp_path / f'{nombre}.pem', tmp_path / f'{nombre}.key'
        ruta_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        ruta_clave.write_bytes(clave.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()))
        archivos[nombre] = (ruta_cert, ruta_clave)
    confianza = ssl.create_default_context(
        cadata=ca.public_bytes(serialization.Encoding.PEM).decode())
    return archivos, confianza


async def _servidor_tls(cert, clave) -> asyncio.Server:
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexto.load_cert_chain(cert, clave)

    async def atender(_r, w):
        w.close()

    return await asyncio.start_server(atender, '127.0.0.1', 0, ssl=contexto)


async def test_chequear_ssl_valido_y_vencido(crear_pool, pki):
    archivos, confianza = pki
    srv_ok = await _servidor_tls(*archivos['valido'])
    srv_vencido = await _servidor_tls(*archivos['vencido'])
    p_ok = srv_ok.sockets[0].getsockname()[1]
    p_vencido = srv_vencido.sockets[0].getsockname()[1]
    try:
        async with crear_pool(ssl_verificado=confianza) as pool:
            t = pool.encolar('chequear_ssl', {
                'hosts': [f'localhost:{p_ok}', f'localhost:{p_vencido}', 'localhost:1'],
                'puerto': 443}, None)
            await esperar_estado(pool, t.id, 'completada')
    finally:
        srv_ok.close()
        srv_vencido.close()

    ok, vencido, cerrado = t.resultado['hosts']
    assert ok['valido'] is True
    assert ok['dias_restantes'] in (29, 30)
    assert ok['emisor'] == 'TP2 CA'
    assert ok['nombres'] == ['localhost']

    assert vencido['valido'] is False
    assert 'expired' in vencido['motivo']
    assert vencido['dias_restantes'] in (-3, -4)       # igual se lee la fecha

    assert cerrado['valido'] is False and 'error' in cerrado
    assert t.resultado['resumen']['proximo_a_vencer']['dias_restantes'] < 0


def test_separar_host():
    assert separar_host('ejemplo.com', 443) == ('ejemplo.com', 443)
    assert separar_host('ejemplo.com:8443', 443) == ('ejemplo.com', 8443)
    assert separar_host('https://ejemplo.com/ruta?x=1', 443) == ('ejemplo.com', 443)


# ------------------------------------------------------------ persistencia

async def test_volcado_y_lectura(tmp_path):
    tareas = [{'id': '1', 'estado': 'completada'}, {'id': '2', 'estado': 'pendiente'}]
    ruta = await persistencia.volcar(tmp_path, tareas, {'total': 2})
    assert ruta.name.startswith('estado_') and ruta.suffix == '.json'
    assert not list(tmp_path.glob('*.tmp'))
    previo = await persistencia.reportar_volcado_previo(tmp_path)
    assert previo['tareas'] == 2
    assert previo['por_estado'] == {'completada': 1, 'pendiente': 1}


async def test_sin_volcado_previo(tmp_path):
    assert await persistencia.reportar_volcado_previo(tmp_path / 'no-existe') is None
