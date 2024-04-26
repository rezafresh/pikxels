import os

CONCURRENCY = int(os.getenv("APP_CONCURRENCY", 1))
REDIS_URL = os.getenv("APP_REDIS_URL")
PW_WS_ENDPOINT = os.getenv("APP_PW_WS_ENDPOINT")
PW_DEFAULT_TIMEOUT = int(os.getenv("APP_PW_DEFAULT_TIMEOUT", 60000))  # 1 minute
PW_PROXY_ENABLED = bool(int(os.getenv("APP_PW_PROXY_ENABLED", 0)))
WEBSHARE_TOKEN = os.getenv("APP_WEBSHARE_TOKEN")
