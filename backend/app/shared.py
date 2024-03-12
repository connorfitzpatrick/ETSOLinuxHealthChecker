# shared.py
import redis
from .config import Config  # Assuming Config contains the REDIS_URL

redis_client = redis.Redis.from_url(Config.REDIS_URL, decode_responses=True)
