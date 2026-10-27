import asyncio

CENTINELA = object()

async def procesar(item):
    await asyncio.sleep(0.5)          # simula I/O
    print(f"procesado {item}")

async def worker(cola):
    while True:
        item = await cola.get()
        if item is CENTINELA:
            cola.task_done()
            break                             # salida ordenada
        try:
            await procesar(item)
        finally:
            cola.task_done()

async def main():
    cola = asyncio.Queue()
    workers = [asyncio.create_task(worker(cola)) for _ in range(3)]

    for i in range(10):
        await cola.put(i)

    # Para parar N workers, hay que poner N centinelas
    for _ in range(len(workers)):
        await cola.put(CENTINELA)

if __name__ == "__main__":
    asyncio.run(main())

