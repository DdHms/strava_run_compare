# Use Python 3.11 slim image
FROM python:3.11-slim

# Install system dependencies (only curl is needed for uv installation)
# This step is the one that was failing. We keep it concise.
RUN apt-get update
RUN apt-get install -y curl
# RUN rm -rf /var/lib/apt/lists/*
# Set working directory
WORKDIR /app

# Install uv (Astral's fast dependency manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Copy requirements file
COPY requirements.txt .

# Create virtual environment and install dependencies using uv
# We don't need to explicitly 'uv venv' if we use 'uv pip install' with the --venv option
RUN uv venv ./.venv

# 2. Install dependencies using the uv binary inside the new venv
# This ensures dependencies are installed correctly into ./.venv
RUN uv pip install -r requirements.txt --python ./.venv/bin/python

# Copy application files
COPY auth_constants.py .
COPY auth_app.py .

# Expose the Flask port
EXPOSE 3476

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TOKEN_FILE_PATH=/app/global.json

# Run the Flask auth server
# Use the full path to the python executable within the venv
CMD ["/app/.venv/bin/python", "auth_app.py"]