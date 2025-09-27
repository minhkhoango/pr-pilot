# Dockerfile
# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
# We copy pyproject.toml and other potential config files first
COPY pyproject.toml poetry.lock* ./

# Install project dependencies
# We use poetry to manage dependencies, but could also use pip with requirements.txt
# Ensure poetry is installed
RUN pip install poetry
# Install dependencies using poetry
RUN poetry config virtualenvs.create false && poetry install --no-dev --no-interaction --no-ansi

# Copy the rest of the application's code into the container
COPY src/ /app/src
COPY entrypoint.sh /app/entrypoint.sh

# Make the entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Set the entrypoint for the container
ENTRYPOINT ["/app/entrypoint.sh"]
