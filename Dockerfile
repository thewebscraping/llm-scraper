# Dockerfile

# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install uv, our package manager
RUN pip install uv

# Copy the dependency files and install dependencies
# This layer is cached to speed up builds if dependencies don't change
COPY pyproject.toml uv.lock ./
RUN uv pip install --system -r requirements.txt

# Copy the rest of the application's source code
COPY . .

# The command to run the application will be specified in docker-compose.yml
