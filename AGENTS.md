# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

Strava Run Compare is a web application that analyzes and visualizes Strava running activities. It automatically classifies runs as either "base" runs or "interval" training, extracts key metrics (pace, distance, heart rate), and provides AI-powered training recommendations.

## Architecture

### Two-Tier Structure

The codebase is organized into two main modules:

1. **`run_compare/`** - Core analysis and API utilities
   - Signal processing and activity classification
   - Strava API interactions (OAuth, activity fetching/updating)
   - Data extraction and visualization utilities

2. **`run_compare_app/`** - Web application frontends
   - Flask web app (`compare.py`, `views.py`)
   - Streamlit app (`streamlit_compare.py`)
   - HTML templates and static assets

### Key Components

**Activity Analysis Pipeline** (`run_compare/activity_analysis_utils.py`):
- Uses signal processing (FFT, convolution) to detect periodic patterns in pace data
- Classifies activities as BASE (steady-state) or INTERVAL (structured speedwork)
- Extracts metrics: pace ± std dev, heart rate ± std dev, distance
- For intervals: detects number of repetitions, interval distance, and work pace/HR

**Strava API Integration** (`run_compare/strava_api_utils.py`):
- OAuth2 flow for authentication
- Uses `curl` subprocess calls (not requests library) for API calls
- Embeds analysis summaries in activity descriptions on Strava
- Parses summaries back out using template-based text parsing

**Data Flow**:
1. Fetch activities via Strava API → 2. Download activity streams (time, distance, velocity, HR) → 3. Signal processing analysis → 4. Upload summary to activity description → 5. Visualize trends over time

**AI Integration** (`run_compare_app/streamlit_compare.py:118-196`):
- Runs local LLM server (port 3888) in background thread
- Sends activity history + prompts to generate training recommendations
- Uses structured JSON schema for responses

## Running the Application

### Prerequisites

```bash
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

**Important**: The `requirements.txt` includes a custom fork of the Strava Python client:
```
git+git://github.com/SantoshML/python-client@master
```

### Strava API Credentials

Set up your Strava application at https://www.strava.com/settings/api

Update credentials in `run_compare/constants.py`:
- `APP_CLIENT_ID`
- `APP_CLIENT_SECRET`
- `REDIRECT_URI` (must match your deployment environment)

### Running Locally (Debug Mode)

For local development where OAuth redirects to localhost:

1. **Update the redirect URI** in `run_compare/constants.py`:
   ```python
   REDIRECT_URI = 'http://localhost:3476/authorization_successful'
   ```

2. **Run the Streamlit app**:
   ```bash
   python run_compare_app/streamlit_compare.py
   ```
   - Starts Flask OAuth server on port 3476
   - Starts AI server on port 3888 (if needed)
   - Streamlit UI runs on default port 8501

3. **Run the Flask app**:
   ```bash
   python run.py
   ```
   - Runs on port 3474
   - Navigate to `http://localhost:3474/`

### Running on Remote Server (Production)

For deployment on hms-thinkcentre-m93p server:

1. **Update the redirect URI** in `run_compare/constants.py` to use Tailscale hostname:
   ```python
   REDIRECT_URI = 'https://hms-thinkcentre-m93p.taile37d5a.ts.net/authorization_successful/'
   ```

2. **Flask app**:
   ```bash
   python run.py
   ```

3. **Streamlit app**:
   ```bash
   streamlit run run_compare_app/streamlit_compare.py
   ```

### Docker Deployment (Recommended)

The project includes Docker configurations for easy deployment:

**Option 1: Slim Auth Server Only (~50MB image)**

Use this to run only the OAuth authentication handler on your remote server. This is ideal for a split deployment where the auth server runs remotely and the Streamlit app runs locally.

```bash
# Build and run the auth server
docker-compose -f docker-compose.auth.yml up -d

# View logs
docker-compose -f docker-compose.auth.yml logs -f

# Check health
curl http://localhost:3476/health
```

The auth server (`auth_server.py`):
- Handles OAuth callbacks on port 3476
- Exchanges authorization codes for access tokens using curl
- Saves tokens to `global.json` (mounted as volume)
- Provides `/health` endpoint for monitoring
- Minimal dependencies (Flask only)

**Option 2: Full Application with Streamlit**

```bash
# Build and run complete app
docker-compose up -d

# View logs
docker-compose logs -f
```

Exposes:
- Port 8501 - Streamlit UI
- Port 3476 - OAuth callback
- Port 3888 - AI server (if WITH_AI=True)

**Split Deployment Setup**:

On remote server (hms-thinkcentre-m93p):
```bash
docker-compose -f docker-compose.auth.yml up -d
```

On local machine:
```bash
# Ensure AUTH_SERVER_HOST in streamlit_compare.py points to remote server
python run_compare_app/streamlit_compare.py
```

See `DOCKER.md` for detailed Docker instructions, troubleshooting, and advanced configurations.

### OAuth Flow

Both apps use multi-threaded OAuth handling:
1. User clicks "Authorize" button
2. Redirected to Strava OAuth page
3. After approval, Strava redirects to `/authorization_successful`
4. Flask handler exchanges auth code for access token
5. Token stored in session (Flask) or `global.json` file (Streamlit)

## Important Implementation Details

### Using curl Instead of Requests

The codebase deliberately uses `subprocess.run()` with `curl` commands instead of the `requests` library for Strava API calls. See:
- `run_compare/strava_api_utils.py:126` - Updating activity descriptions
- `run_compare/strava_api_utils.py:174` - Fetching athlete activities
- `run_compare/activity_analysis_utils.py:163` - Fetching activity streams

### Activity Summary Format

Summaries are embedded in Strava activity descriptions between markers:
```
#<-ACTIVITY SUMMARY START->#
base:5000m@4.5±Δ0.2min/km🫀165±Δ5BPM
#<-ACTIVITY SUMMARY END->#
```

Or for intervals:
```
#<-ACTIVITY SUMMARY START->#
interval:8X[400m@3.8±Δ0.1min/km🫀175]±Δ3BPM
#<-ACTIVITY SUMMARY END->#
```

Templates defined in `run_compare/constants.py`:
- `BASE_BLOCK_TEMPLATE`
- `INTERVAL_BLOCK_TEMPLATE`

Parsing logic in `run_compare/strava_api_utils.py:149-160`

### Configuration Constants

Key configuration in `run_compare/constants.py`:
- `N_ACTIVITIES = 20` - Number of recent activities to analyze
- `DECIMALS = 3` - Precision for metric rounding
- OAuth URLs and credentials
- Color scheme for visualizations

## Development Workflow

### Analyzing a Single Activity

```python
from run_compare.activity_analysis_utils import calculate_analysis

calculate_analysis(
    activity_id=12345678,
    access_token="your_access_token",
    debug=False
)
```

### Testing Signal Processing

The interval detection algorithm in `activity_analysis_utils.py`:
- `is_periodic()` - Detects if pace signal has repetitive structure
- `find_intervals()` - Extracts interval start/end indices
- `extract_interval_data()` - Computes aggregate interval metrics

Debug by setting `debug=True` in `calculate_analysis()` to visualize signal processing steps.

### AI Training Recommendations

Prompts defined in `run_compare/prompt_constants.py`:
- `SYSTEM_PROMPT` - Instructions for the LLM
- `SUGGESTED_EXERCISE_PROMPT` - Query for next workout recommendation
- `ai_schema_type_json` - Structured output schema

The AI server must be running at `http://localhost:3888/generate` endpoint.

## Common Tasks

**Add support for a new activity type**: Extend classification logic in `activity_analysis_utils.py:148-152`, add new wrapper function like `wrap_interval_data()` in `constants.py`

**Modify visualization**: Update plotting functions in `run_compare/visualisation_utils.py` and chart assembly in `run_compare_app/compare.py:219-262`

**Change OAuth flow**: Update Flask routes in `run_compare_app/compare.py:92-125` (Flask) or threading logic in `run_compare_app/streamlit_compare.py:74-148` (Streamlit)

**Adjust analysis parameters**: Modify signal processing parameters in `activity_analysis_utils.py` (e.g., kernel width, peak detection thresholds)