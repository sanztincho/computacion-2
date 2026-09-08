import redis
import os
import time

redis_host = os.getenv('REDIS_HOST', 'localhost')
r = redis.Redis(host=redis_host, port=6379)

print("Worker iniciado, incrementando contador cada segundo...")

while True:
    r.incr('contador')
    time.sleep(1)