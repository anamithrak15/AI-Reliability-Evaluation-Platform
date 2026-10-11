import redis
from rq import Queue, Worker

from app.core.config import get_settings
from app.core.logging import configure_logging

QUEUE_NAME = "evaluations"


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    connection = redis.Redis.from_url(settings.redis_url)
    Worker([Queue(QUEUE_NAME, connection=connection)], connection=connection).work()


if __name__ == "__main__":
    main()
