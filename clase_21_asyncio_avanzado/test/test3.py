listo = asyncio.Event()

async def esperar_arranque():
    await listo.wait()                  # se suspende hasta que alguien lo setee
    print('ya puedo trabajar')

async def inicializar():
    await cargar_configuracion()
    listo.set()                         # despierta a todos los que esperan
