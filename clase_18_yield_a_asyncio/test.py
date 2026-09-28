def contador():
    n = 0
    while True:
        print(f'  voy por {n}')
        yield
        n += 1