from flask import Flask
import redis
import os
import platform

app = Flask(__name__)

redis_host = os.getenv('REDIS_HOST', 'localhost')
r = redis.Redis(host=redis_host, port=6379)

@app.route('/')
def index():
    contador = r.get('contador')
    if contador:
        contador = contador.decode()
    else:
        contador = '0'

    sistema = platform.uname()
    return f"Contador: {contador}\nSistema: {sistema.system} {sistema.release} {sistema.machine}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)