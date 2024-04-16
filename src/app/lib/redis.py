from contextlib import closing, contextmanager

from redis import Redis

from .. import settings


@contextmanager
def get_redis_connection():
    with closing(Redis.from_url(settings.REDIS_URL, decode_responses=True)) as client:
        yield client
