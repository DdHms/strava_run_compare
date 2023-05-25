import os

import constants
from constants import DESCRIPTION_HEADER, DESCRIPTION_FOOTER, BASE_BLOCK_TEMPLATE, INTERVAL_BLOCK_TEMPLATE, \
    wrap_interval_data, wrap_base_data
import swagger_client
import requests
from stravaio import run_server_and_wait_for_token
import urllib
import webbrowser

activites_url = "https://www.strava.com/api/v3/athlete/activities"
auth_url = "https://www.strava.com/oauth/token"


def _request_strava_authorize(client_id, port):
    params_oauth = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": f"http://localhost:{port}/authorization_successful",
        "scope": "read,profile:read_all,activity:write,activity:read",
        "state": 'https://github.com/sladkovm/strava-http',
        "approval_prompt": "force"
    }
    values_url = urllib.parse.urlencode(params_oauth)
    base_url = 'https://www.strava.com/oauth/authorize'
    rv = base_url + '?' + values_url
    webbrowser.get().open(rv)
    return None

def strava_oauth2(client_id=None, client_secret=None, port=8000):
    """Run strava authorization flow. This function will open a default system
    browser alongside starting a local webserver. The authorization procedure will be completed in the browser.

    The access token will be returned in the browser in the format ready to copy to the .env file.

    Parameters:
    -----------
    client_id: int, if not provided will be retrieved from the STRAVA_CLIENT_ID env viriable
    client_secret: str, if not provided will be retrieved from the STRAVA_CLIENT_SECRET env viriable
    """
    if client_id is None:
        client_id = os.getenv('STRAVA_CLIENT_ID', None)
        if client_id is None:
            raise ValueError('client_id is None')
    if client_secret is None:
        client_secret = os.getenv('STRAVA_CLIENT_SECRET', None)
        if client_secret is None:
            raise ValueError('client_secret is None')

    # port = 8000
    _request_strava_authorize(client_id, port)


    token = run_server_and_wait_for_token(
        port=port,
        client_id=client_id,
        client_secret=client_secret
    )

    return token

def fetch_token():
    client_id = input('input client id from this page: https://www.strava.com/settings/api')
    print(
        f'Go to https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&scope=activity:read_all&redirect_uri=http://Localhost&approval_prompt=force')
    code = input('insert received access token from the page above:')
    client_secret = input('enter your client secret code from this page: https://www.strava.com/settings/api')

    cmd = f'''curl -X POST {auth_url} -d client_id={client_id} -d client_secret={client_secret} -d code={code} -d grant_type=authorization_code'''
    res = eval(os.popen(cmd).read().replace('null', 'None').replace('false', 'False').replace('true', 'True'))
    refresh_token = res['refresh_token']

    cmd = f'''curl -X POST {auth_url} -d client_id={client_id} -d client_secret={client_secret} -d refresh_token={refresh_token} -d grant_type=refresh_token'''
    res = eval(os.popen(cmd).read().replace('null', 'None').replace('false', 'False').replace('true', 'True'))
    access_token = res['access_token']
    return access_token


def upload_description_from_summary(summary, activity_id, client):
    body = swagger_client.UpdatableActivity()
    if summary['type'] == constants.INTERVAL:
        data_block = eval("f'" + constants.INTERVAL_BLOCK_TEMPLATE + "'")
    elif summary['type'] == constants.BASE:
        data_block = eval("f'" + BASE_BLOCK_TEMPLATE + "'")
    textual_summary = f'{DESCRIPTION_HEADER}{data_block}{DESCRIPTION_FOOTER}'
    # url = f"https://www.strava.com/api/v3/activities/{activity_id}/?" \
    #       f"access_token={access_token}"
    # requests.put(url, {'description': '#<<<<<-------------ACTIVITY SUMMARY START------------->>>>>#\n testing'})
    body.description = textual_summary
    client.activities_api.update_activity_by_id(activity_id, body=body)

    pass

def template2separators(template):
    return [prt.split('}')[-1] for prt in template.split('{')]

def parser(text, separators):
    if text.startswith(separators[0]):
        separators = separators[1:]
    output = []
    rest = text
    for sep in separators:
        if len(sep) == 0:
            continue
        out, rest = rest.split(sep)[0], sep.join(rest.split(sep)[1:])

        output.append(out)
    if not text.endswith(separators[-1]):
        output.append(rest)
    return output

def summary_from_description(textual_summary):
    textual_summary = textual_summary.split(DESCRIPTION_HEADER)[1].split(DESCRIPTION_FOOTER)[0]
    activity_type, rest = textual_summary.split(':')[0], ''.join(textual_summary.split(':')[1:])
    if activity_type == constants.INTERVAL:
        input_values = parser(rest, template2separators(INTERVAL_BLOCK_TEMPLATE)[1:])
        input_keys = wrap_interval_data.__code__.co_varnames
        data = wrap_interval_data(*input_values)
    elif activity_type == constants.BASE:
        input_values = parser(rest, template2separators(BASE_BLOCK_TEMPLATE)[1:])
        input_keys = wrap_base_data.__code__.co_varnames
        data = wrap_base_data(*input_values)
    return data


def get_athlete_activities(access_token, n=30, after=None):
    activities_url = f"https://www.strava.com/api/v3/athlete/activities?" \
                     f"per_page={n}&access_token={access_token}"
    if after is not None:
        activities_url += f'&after={after}' # empty string starts from day 0!!
    response = requests.get(activities_url)
    return response.json()


def get_run_activities(activities_json):
    runs = [act for act in activities_json if act['type'] == 'Run']
    return runs


def get_full_activities(access_token, activities_list):
    full_activities_list = activities_list
    for i, act in enumerate(activities_list):
        url = f"https://www.strava.com/api/v3/activities/{act['id']}/?" \
              f"access_token={access_token}"
        full_activities_list[i] = requests.get(url).json()
    return full_activities_list




def get_summarized_activites(full_activities_json):
    summarized = [act for act in full_activities_json if constants.DESCRIPTION_HEADER in act['description']]
    return summarized

def exists_and_summarized(act):
    if act['description'] is None:
        return False
    elif constants.DESCRIPTION_HEADER not in act['description']:
        return False
    else:
        return True

def get_non_summarized_activities(full_activities_json):
    non_summarized = [act for act in full_activities_json if not exists_and_summarized(act)]
    return non_summarized