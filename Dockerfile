# Dockerfile
# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
# We copy pyproject.toml and other potential config files first
COPY pyproject.toml poetry.lock* ./

# Install project dependencies
# Ensure poetry is installed
RUN apt-get update && apt-get install -y jq && pip install poetry
# Install dependencies using poetry
RUN poetry config virtualenvs.create false && poetry install --only main --no-interaction --no-ansi --no-root

# Copy the rest of the application's code into the container
COPY src/ /app/src
COPY entrypoint.sh /app/entrypoint.sh

# Make the entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Set the entrypoint for the container
ENTRYPOINT ["/app/entrypoint.sh"]
