# Docker Deployment Guide

## Deployment Options

This project provides two Docker configurations:
1. **Full Application** - Complete Streamlit app with OAuth + AI (larger image)
2. **Auth Server Only** - Slim Flask OAuth handler (minimal image ~50MB)

## Option A: Slim Auth Server Only (Recommended for Remote Server)

Use this to run only the OAuth authentication handler on your remote server.

### Quick Start

```bash
# Build and start the auth server
docker-compose -f docker-compose.auth.yml up -d

# View logs
docker-compose -f docker-compose.auth.yml logs -f

# Stop the server
docker-compose -f docker-compose.auth.yml down
```

### Manual Docker Commands

```bash
# Build the slim auth image
docker build -f Dockerfile.auth -t strava-auth .

# Run the auth server
docker run -d \
  --name strava-auth \
  -p 3476:3476 \
  -v $(pwd)/global.json:/app/global.json \
  -e TOKEN_FILE_PATH=/app/global.json \
  strava-auth

# Check health
curl http://localhost:3476/health
```

### Custom Token File Path

You can specify a custom path for the token file using the `TOKEN_FILE_PATH` environment variable:

```bash
# Using docker run with custom path
docker run -d \
  --name strava-auth \
  -p 3476:3476 \
  -v /path/on/host/my-token.json:/app/token.json \
  -e TOKEN_FILE_PATH=/app/token.json \
  strava-auth

# Using docker-compose: edit docker-compose.auth.yml
# Update the volumes and environment sections:
volumes:
  - /path/on/host/my-token.json:/app/token.json
environment:
  - TOKEN_FILE_PATH=/app/token.json
```

The token file will contain:
```json
{
  "token": "your_access_token_here",
  "athlete": {
    "id": 12345,
    "username": "athlete_name",
    ...
  }
}
```

### Use Case: Split Deployment

Run the auth server on your remote server (hms-thinkcentre-m93p) and the Streamlit app locally:

**On remote server:**
```bash
docker-compose -f docker-compose.auth.yml up -d
```

**On local machine:**
```bash
# Make sure REDIRECT_URI points to remote server
python run_compare_app/streamlit_compare.py
```

The auth server will:
- Listen on port 3476
- Handle OAuth callbacks from Strava
- Save tokens to `global.json`
- Provide health check endpoint at `/health`

## Option B: Full Application

### Using Docker Compose (Recommended)

```bash
# Build and start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the container
docker-compose down

# Rebuild after code changes
docker-compose up -d --build
```

### Option 2: Using Docker directly

```bash
# Build the image
docker build -t strava-run-compare .

# Run the container
docker run -d \
  --name strava-run-compare \
  -p 8501:8501 \
  -p 3476:3476 \
  -p 3888:3888 \
  -v $(pwd)/global.json:/app/global.json \
  strava-run-compare

# View logs
docker logs -f strava-run-compare

# Stop and remove container
docker stop strava-run-compare
docker rm strava-run-compare
```

## Accessing the Application

Once running, access the app at:
- **Streamlit UI**: http://localhost:8501
- **OAuth Callback**: http://localhost:3476 (used by Strava redirect)
- **AI Server**: http://localhost:3888 (if WITH_AI=True)

## Network Configuration

### For Local Network Access

The Dockerfile is configured with `--server.address=0.0.0.0` which allows access from your local network.

To access from other devices on your network:
1. Find your host machine's IP: `ifconfig` (macOS/Linux) or `ipconfig` (Windows)
2. Access from other devices: http://YOUR_IP:8501

### For Remote Server Deployment

If deploying on your hms-thinkcentre-m93p server:

1. Ensure `AUTH_SERVER_HOST` in `streamlit_compare.py` is set to `'0.0.0.0'`
2. Update `REDIRECT_URI` in `run_compare/constants.py` to match your server's hostname
3. Run with docker-compose:
   ```bash
   docker-compose up -d
   ```

## Development Mode

To mount your code for live development (changes reflect without rebuild):

```bash
# Uncomment the volumes section in docker-compose.yml:
# - .:/app

docker-compose up
```

## Troubleshooting

### Port already in use
```bash
# Check what's using the port
lsof -i :8501

# Kill the process or change the port mapping in docker-compose.yml
```

### View container logs
```bash
docker-compose logs -f strava-run-compare
```

### Access container shell
```bash
docker exec -it strava-run-compare /bin/bash
```

### Rebuild after requirements.txt changes
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```