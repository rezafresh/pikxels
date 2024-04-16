import os

CONCURRENCY = int(os.getenv("APP_CONCURRENCY", 2))
REDIS_URL = os.getenv("APP_REDIS_URL", "redis://localhost:6379/")
PW_WS_ENDPOINT = os.getenv("APP_PW_WS_ENDPOINT", "ws://localhost:3000/")
PW_DEFAULT_TIMEOUT = int(os.getenv("APP_PW_DEFAULT_TIMEOUT", 60000))  # 1 minute
