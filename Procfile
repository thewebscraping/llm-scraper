[run]
# This file allows you to run the entire system with a single command.
# It uses `honcho`, a Procfile runner, to manage all the processes.
#
# Installation:
# pip install honcho
#
# Usage:
# honcho start

# 1. API Server: The FastAPI application that serves user requests.
api: uvicorn api:app --host 0.0.0.0 --port 8000 --reload

# 2. Celery Worker: The process that executes background tasks sent from the API.
#    The `-l info` flag sets the logging level to info.
worker: celery -A celery_app worker -l info

# 3. Celery Beat: The scheduler process that triggers periodic/scheduled tasks.
#    This is responsible for running the automated system scrapes.
beat: celery -A celery_app beat -l info
