import redis
import rq

from .... import settings

queue_default = rq.Queue(
    connection=redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
)
queue_low = rq.Queue(
    "low", connection=redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
)
