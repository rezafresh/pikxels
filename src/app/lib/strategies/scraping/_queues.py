import redis
import rq

from .... import settings

_redis = redis.Redis.from_url(settings.REDIS_URL)
default = rq.Queue("default", connection=_redis)
