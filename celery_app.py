from celery import Celery
from llm_scraper.settings import settings

# Initialize the Celery application
# The first argument is the name of the current module, which is important for Celery's auto-discovery of tasks.
# The `broker` and `backend` are set to the Redis URL from our settings.
# - Broker: The message queue where tasks are sent.
# - Backend: The store where task results and statuses are saved.
celery_app = Celery(
    "llm_scraper_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["worker"],  # Correctly point to the worker module
)

# Optional: Configure Celery settings for better performance and reliability
celery_app.conf.update(
    task_track_started=True,
    result_expires=3600,  # Expire results after 1 hour
    broker_connection_retry_on_startup=True,
)
