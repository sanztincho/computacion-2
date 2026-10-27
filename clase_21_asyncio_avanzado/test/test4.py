import asyncio

async def cargar_configuracion():
    print('cargando configuracion...')
    await asyncio.sleep(1)                
    print('configuracion lista')

async def inicializar(listo):
    await cargar_configuracion()
    listo.set()                               

async def procesar(tarea, wid):
    await asyncio.sleep(0.5)
    print(f'worker {wid} proceso {tarea}')

async def productor(cola, n):
    for i in range(n):
        await cola.put(f'tarea-{i}')          
        print(f'producida tarea-{i}')

async def worker(cola, wid, listo):
    await listo.wait()                        
    print(f'worker {wid}: ya puedo trabajar')
    while True:
        tarea = await cola.get()              
        try:
            await procesar(tarea, wid)
        finally:
            cola.task_done()                  

async def main():
    cola = asyncio.Queue(maxsize=5)
    listo = asyncio.Event()
    workers = [asyncio.create_task(worker(cola, i, listo)) for i in range(3)]
    
    asyncio.create_task(inicializar(listo))

    await productor(cola, 12)
    await cola.join()                         

    for w in workers:
        w.cancel()                            


if __name__ == '__main__':
    asyncio.run(main())
