# Use Python 3.11 slim image
FROM python:3.11-slim

# Install curl for health checks and uv installation
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:${PATH}"

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Create virtual environment and install dependencies using uv
RUN uv venv
RUN . .venv/bin/activate && uv pip install -r requirements.txt

# Copy the entire application
COPY . .

# Expose ports
# 3476 - Flask OAuth server
# 8501 - Streamlit default port
# 3888 - AI server (optional)
EXPOSE 3476 8501 3888

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Activate venv and run streamlit
CMD ["/bin/bash", "-c", "source .venv/bin/activate && streamlit run run_compare_app/streamlit_compare.py --server.address=0.0.0.0 --server.port=8501"]