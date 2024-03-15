# shared.py
# import redis
# from .config import Config

# redis_client = redis.Redis.from_url(Config.REDIS_URL, decode_responses=True)
from flask_caching import Cache

cache = Cache(config={'CACHE_TYPE': 'simple'})  