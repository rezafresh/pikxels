import redis
import rq

from .... import settings

_redis = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
default = rq.Queue(connection=_redis)
low = rq.Queue(connection=_redis)
