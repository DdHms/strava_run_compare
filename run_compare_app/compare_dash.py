import json

import dash
import numpy as np
import pandas as pd
import plotly.graph_objs as go
import requests
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc
from flask import request, redirect, session, Flask

from run_compare.activity_analysis_utils import calculate_analysis, gather_data_for_plotting
from run_compare.constants import BASE_COLOR, INTERVAL_COLOR, N_ACTIVITIES, APP_CLIENT_ID, APP_CLIENT_SECRET
from run_compare.prompt_constants import SUGGESTED_EXERCISE_PROMPT, SYSTEM_PROMPT, ai_schema_type_json
from run_compare.strava_api_utils import get_strava_oauth2_url, get_activities
from run_compare.stravaio import StravaIO
# Import internal organization modules
from run_compare.visualisation_utils import plot_to_date, speed_to_pace, distance_display

# Global session storage to simulate session data
global_session = {'base_activities': [],  # Should be populated after auth
    'interval_activities': []  # Should be populated after auth
}

# Create the Dash app
server = Flask(__name__)
server.secret_key = "supersecretkey"
app = dash.Dash(__name__, server=server, external_stylesheets=[dbc.themes.BOOTSTRAP])

app.layout = html.Div([
    # Define the URL component for routing
    dcc.Location(id='url', refresh=False),

    # Page content will be rendered here
    html.Div(id='page-content')
])

# Custom index string with necessary placeholders
app.index_string = """
<!DOCTYPE html>
<html>
<head>
    <title>Home Page</title>
    <style>
        body, html {
            margin: 0;
            padding: 0;
            height: 100%;
            background: url('https://source.unsplash.com/random/1920x1080') no-repeat center center fixed;
            background-size: cover;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }
        .background {
            text-align: center;
            width: 100%;
        }
        .header {
            font-size: 3em;
            font-weight: bold;
            color: white;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
            margin-bottom: 20px;
        }
        .dropdown-menu {
            margin-top: 20px;
        }
    </style>
</head>
<body>
    {%app_entry%}
    {%config%}
    {%scripts%}
    {%new_dash_renderer%} <!-- Correct DashRenderer Placeholder -->
</body>
</html>
"""
# Utility function to convert activities into a DataFrame for table display
def convert_activities_to_df(base_activities, inteval_activities):
    if not base_activities and not inteval_activities:
        return pd.DataFrame()  # Return empty DataFrame if no data available

    base_df = pd.DataFrame(base_activities)
    intervals_df = pd.DataFrame(inteval_activities)

    base_df['source'] = 'base_activity'
    intervals_df['source'] = 'interval'

    base_df.rename(columns={'SPEED': 'BASE_SPEED', 'DISTANCE': 'BASE_DISTANCE', 'HR': 'BASE_HR'}, inplace=True)
    intervals_df.rename(columns={'INTERVAL_SPEED': 'INTERVAL_SPEED', 'INTERVAL_DISTANCE': 'INTERVAL_DISTANCE',
                                 'INTERVAL_HR': 'INTERVAL_HR'}, inplace=True)

    combined_df = pd.concat([base_df, intervals_df], ignore_index=True).sort_values(by='date').reset_index(drop=True)

    def format_distance(row):
        if row['source'] == 'base_activity':
            return distance_display(row['BASE_DISTANCE'])
        elif row['source'] == 'interval':
            return f"{int(row['N_INTERVALS'])} X {distance_display(row['INTERVAL_DISTANCE'])}"

    def format_hr(row):
        return int(row['BASE_HR']) if row['source'] == 'base_activity' else int(row['INTERVAL_HR'])

    def format_speed(row):
        return speed_to_pace(row['BASE_SPEED']) if row['source'] == 'base_activity' else speed_to_pace(
            row['INTERVAL_SPEED'])

    formatted_df = pd.DataFrame(
        {'date': combined_df['date'].apply(lambda x: x.strftime("%d/%m/%Y")), 'source': combined_df['source'],
            'distance': combined_df.apply(format_distance, axis=1), 'HR': combined_df.apply(format_hr, axis=1),
            'pace': combined_df.apply(format_speed, axis=1)})

    return formatted_df


# Utility function to collect figure data for plotting activities
def collect_data_for_fig(base_activities, interval_activities):
    if not base_activities:
        return {'all_dates': [], 'all_speeds': [], 'all_dspeeds': [], 'all_hr': [], 'all_dhr': [], 'all_labels': [],
            'all_marker_col': []}

    distance = [data['DISTANCE'] for data in base_activities]
    hr = [data['HR'] for data in base_activities]
    dspeed = [data['DSPEED'] for data in base_activities]
    dhr = [data['DHR'] for data in base_activities]
    speed = [data['SPEED'] for data in base_activities]
    dates = [data['date'] for data in base_activities]
    marker_col = [BASE_COLOR] * len(distance)

    # Process interval activities if available
    idistance = [data['INTERVAL_DISTANCE'] for data in interval_activities] if interval_activities else []
    n_int = [data['N_INTERVALS'] for data in interval_activities] if interval_activities else []
    ihr = [data['INTERVAL_HR'] for data in interval_activities] if interval_activities else []
    idspeed = [data['DSPEED'] for data in interval_activities] if interval_activities else []
    idhr = [data['DHR'] for data in interval_activities] if interval_activities else []
    ispeed = [data['INTERVAL_SPEED'] for data in interval_activities] if interval_activities else []
    idates = [data['date'] for data in interval_activities] if interval_activities else []
    imarker_col = [INTERVAL_COLOR] * len(idistance) if interval_activities else []

    # Create labels for base and interval activities
    lnk_base = lambda i: f'https://www.strava.com/activities/{base_activities[i]["id"]}'
    dis_base = lambda i: np.around(distance[i] / 1000, decimals=1)
    sp_base = lambda i: speed_to_pace(speed[i])
    label_base = [f'<a href="{lnk_base(i)}"> {dis_base(i)}k <br> @{sp_base(i)} </a>' for i in range(len(distance))]

    lnk_int = lambda \
        i: f'https://www.strava.com/activities/{interval_activities[i]["id"]}' if interval_activities else ""
    dis_int = lambda i: int(100 * np.around(idistance[i] / 100, decimals=1)) if interval_activities else 0
    sp_int = lambda \
        i: f'{int(np.floor(ispeed[i]))}:{int(np.round(60 * np.remainder(ispeed[i], 1))):02}' if interval_activities else ""
    label_int = [f'<a href="{lnk_int(i)}"> {n_int[i]}X{dis_int(i)}m  <br> @{sp_int(i)} </a>' for i in
                 range(len(idistance))] if interval_activities else []

    all_dates = sorted(dates + idates)
    all_speeds = (speed + ispeed) if interval_activities else speed
    all_dspeeds = (dspeed + idspeed) if interval_activities else dspeed
    all_hr = (hr + ihr) if interval_activities else hr
    all_dhr = (dhr + idhr) if interval_activities else dhr
    all_labels = (label_base + label_int) if interval_activities else label_base
    all_marker_col = (marker_col + imarker_col) if interval_activities else marker_col

    return {'all_dates': all_dates, 'all_speeds': all_speeds, 'all_dspeeds': all_dspeeds, 'all_hr': all_hr,
            'all_dhr': all_dhr, 'all_labels': all_labels, 'all_marker_col': all_marker_col}


# Page layouts for the Dash app
def render_home():
        return html.Div(
            children=[
                # Header
                html.H1("Welcome to My Page", className="header"),

                # Dropdown Menu
                dbc.DropdownMenu(
                    label="Menu",
                    children=[
                        dbc.DropdownMenuItem("Login", href="/login"),
                        dbc.DropdownMenuItem("Graph", href="/graph"),
                        dbc.DropdownMenuItem("Activities", href="/activities"),
                        dbc.DropdownMenuItem("Ask AI", href="/ai"),
                    ],
                    color="primary",
                    className="dropdown-menu"
                ),
            ],
            className="background"
        )
#     return html.Div([html.H2("Home Page"), html.Ul(
#         [html.Li(html.A("Login", href="/login")), html.Li(html.A("Graph", href="/graph")),
#             html.Li(html.A("Activities", href="/activities")), html.Li(html.A("Ask AI", href="/ai"))])])


def render_login():
    # Get the OAuth URL to authenticate; opens in a new tab
    oauth_url = get_strava_oauth2_url(client_id=APP_CLIENT_ID, client_secret=APP_CLIENT_SECRET, port=8001)
    return html.Div([html.H2("Login Page"), html.P("Click the button below to open OAuth in a new tab:"),
        html.A("OAuth Login", href=oauth_url, target="_blank",
               style={'padding': '10px', 'backgroundColor': '#4CAF50', 'color': 'white', 'textDecoration': 'none'}),
        html.Br(), html.Br(), html.A("Back Home", href="/")])


def render_graph():
    # Collect data and plot figure using the utility function; if data is not present, render a dummy graph
    fig_data = collect_data_for_fig(global_session.get('base_activities', []),
                                    global_session.get('interval_activities', []))
    if fig_data['all_dates']:
        fig = plot_to_date(fig_data['all_dates'], fig_data['all_speeds'], fig_data['all_dspeeds'],
                           color='rgba(0,100,255,', name='Speed [min/km]', label=fig_data['all_labels'],
                           marker_col=fig_data['all_marker_col'])
        fig = plot_to_date(fig_data['all_dates'], fig_data['all_hr'], fig_data['all_dhr'], color='rgba(255,100,0,',
                           name='HR [BPM]', label=[f'{int(hr)}' for hr in fig_data['all_hr']], add_to_fig=fig,
                           separate=True)
    else:
        fig = go.Figure(data=[go.Scatter(x=[0, 1, 2], y=[0, 1, 0])])
    return html.Div([html.H2("Graph Page"), dcc.Graph(figure=fig), html.Br(), html.A("Back Home", href="/")])


def render_activities():
    df = convert_activities_to_df(global_session.get('base_activities', []),
                                  global_session.get('interval_activities', []))
    table_html = df.to_html(classes='table table-striped') if not df.empty else "No activity data available."
    return html.Div(
        [html.H2("Activities Page"), html.Div(dcc.Markdown(table_html)), html.Br(), html.A("Back Home", href="/")])


def render_ai():
    # Simulate an AI request; in practice, this should call an external AI service.
    ai_request = {'user_prompt': SUGGESTED_EXERCISE_PROMPT, 'system_prompt': SYSTEM_PROMPT,
        'schema': ai_schema_type_json, 'context': {}}
    try:
        response = requests.post('http://localhost:3888/generate', json=ai_request)
        ai_response = response.json()
    except Exception as e:
        ai_response = {"response": "AI service not available."}
    return html.Div(
        [html.H2("AI Response"), html.Pre(json.dumps(ai_response, indent=2)), html.Br(), html.A("Back Home", href="/")])


# Dash layout with URL routing support
app.layout = html.Div([dcc.Location(id='url', refresh=False), html.Div(id='page-content')])


@app.server.route('/authorization_successful', methods=['GET'])
def authorization_successful():
    # Extract the authorization code from the query parameters
    print('authorization_successful')
    authorization_code = request.args.get('code')
    # Save the code in a global session (if needed)
    global_session['code'] = authorization_code

    # Exchange the code for an access token from the OAuth provider
    response = requests.post("https://www.strava.com/oauth/token",
        data={"client_id": APP_CLIENT_ID, "client_secret": APP_CLIENT_SECRET, "code": authorization_code,
            "grant_type": "authorization_code"})
    response_data = response.json()
    STRAVA_ACCESS_TOKEN = response_data['access_token']

    # Initialize the Strava client with the received access token
    client = StravaIO(access_token=STRAVA_ACCESS_TOKEN)
    athlete = client.get_logged_in_athlete()
    athlete_dict = athlete.to_dict()

    # Save relevant athlete information in the Flask session
    session['athlete_name'] = athlete_dict['firstname'] + ' ' + athlete_dict['lastname']
    session['access_token'] = STRAVA_ACCESS_TOKEN
    session['athlete_id'] = athlete.id

    # Re-initialize StravaIO to ensure session token is used
    client = StravaIO(access_token=session['access_token'])
    non_summarized, full_run_activities = get_activities(access_token=session['access_token'], invalidate_history=False,
                                                         num_activities=N_ACTIVITIES)
    # Process each activity for analysis
    for activity in non_summarized:
        calculate_analysis(activity_id=activity['id'], access_token=session['access_token'], debug=False)

    # Gather plotting data from all activities
    base_activities, interval_activities = gather_data_for_plotting(activity_list=full_run_activities)
    session['base_activities'] = base_activities
    session['interval_activities'] = interval_activities

    # Redirect to the graph page in the Dash app
    return redirect('/graph')


# Callback to update page content based on URL path
@app.callback(Output('page-content', 'children'), Input('url', 'pathname'))
def display_page(pathname):
    if pathname == '/login':
        return render_login()
    elif pathname == '/graph':
        return render_graph()
    elif pathname == '/activities':
        return render_activities()
    elif pathname == '/ai':
        return render_ai()
    else:
        return render_home()


if __name__ == '__main__':
    # Run the Dash server with debug enabled
    app.secret_key = 'WD#RRTGD%&%#'
    app.run_server(debug=True, host='0.0.0.0', port=3475)
