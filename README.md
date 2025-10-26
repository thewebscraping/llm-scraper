# LLM Scraper

A flexible, configuration-driven web scraper designed to extract article content and feed it into a Retrieval-Augmented Generation (RAG) pipeline.

This project uses a professional, scalable architecture with FastAPI, Celery, and Redis to create a robust system for data ingestion.

## Core Features

- **Config-Driven Parsing**: Define how to scrape any site using simple JSON configuration files.
- **RAG-Ready**: Automatically chunks content, generates embeddings via OpenAI, and stores it in an AstraDB vector store.
- **Scalable Architecture**:
  - **FastAPI**: For a high-performance, non-blocking API.
  - **Celery**: For distributed background task processing.
  - **Redis**: As the message broker and result backend for Celery.
- **Automated & On-Demand Scraping**:
  - Scrape entire sites on a recurring schedule.
  - Scrape specific sites or single URLs via API endpoints.

## Project Structure

```
.
├── Procfile              # Defines processes for Honcho (api, worker, beat)
├── api.py                # FastAPI application, the user-facing entrypoint
├── celery_app.py         # Celery application instance configuration
├── pyproject.toml        # Project metadata and dependencies
├── src/
│   └── llm_scraper/
│       ├── __init__.py
│       ├── articles.py   # Core Article data model and chunking logic
│       ├── meta.py       # Metadata extraction logic
│       ├── parsers/      # Site-specific parser configurations
│       ├── schema.py     # Pydantic models for configuration and data
│       ├── settings.py   # Application settings management (from .env)
│       ├── utils.py      # Utility functions
│       └── vector_store.py # Handles interaction with OpenAI and AstraDB
└── worker.py             # Celery worker and scheduler (Celery Beat) definitions
```

## Setup

1.  **Install Dependencies**: This project uses `uv` for package management.
    ```bash
    uv pip install -r requirements.txt
    ```

2.  **Environment Variables**: Create a `.env` file in the root directory and add your credentials:
    ```env
    # .env
    OPENAI_API_KEY="sk-..."
    ASTRA_DB_APPLICATION_TOKEN="AstraCS:..."
    ASTRA_DB_API_ENDPOINT="https://..."
    ASTRA_DB_COLLECTION_NAME="your_collection_name"
    REDIS_URL="redis://localhost:6379/0"
    ```

3.  **Run Redis**: Ensure you have a Redis server running locally. You can use Docker for this:
    ```bash
    docker run -d -p 6379:6379 redis
    ```

## How to Run

You can run the system in two ways: locally using `honcho` or with Docker.

### 1. Running with Docker (Recommended)

This is the easiest way to run the entire system, including the Redis database.

**Prerequisites**:
- Docker and Docker Compose installed.
- A `.env` file with your credentials (see Setup section).

**To start the entire system, run:**
```bash
docker-compose up --build
```
This command will:
1.  Build the Docker image for the application based on the `Dockerfile`.
2.  Start containers for the `api`, `worker`, `beat`, and `redis` services.
3.  Display all logs in your terminal.

To stop the services, press `Ctrl+C`.

### 2. Running Locally with Honcho

Use this method if you prefer not to use Docker.

**Prerequisites**:
- Python and `uv` installed.
- A running Redis server (e.g., `docker run -d -p 6379:6379 redis`).
- Dependencies installed (`uv pip install -r requirements.txt`).
- A `.env` file with your credentials.

**To start the entire system, run:**
```bash
honcho start
```

## API Usage

-   **`POST /scrape-url`**: Scrape a single URL on-demand.
-   **`POST /scrape-site`**: Trigger a background task to scrape an entire pre-configured site.
-   **`GET /tasks/{task_id}`**: Check the status of a background task.
-   **`POST /query`**: Perform a similarity search on the vectorized data in AstraDB.
