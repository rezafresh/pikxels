from .providers import webshare

get_available_proxy = webshare.create_proxy_yielder()
