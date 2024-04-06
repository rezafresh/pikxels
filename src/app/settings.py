import os

REDIS_URL = os.getenv("APP_REDIS_URL", "redis://localhost:6379/")
PW_CDP_ENDPOINT_URL = os.getenv("APP_PW_CDP_ENDPOINT_URL", "ws://localhost:3000/")
PW_DEFAULT_TIMEOUT = int(os.getenv("APP_PW_DEFAULT_TIMEOUT", 60000))  # 1 minute
