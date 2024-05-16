import requests
import urllib3
import os
import numpy as np
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from strava_api_utils import activites_url, auth_url, fetch_token

access_token = fetch_token()
def get_activites(access_token, max_entries=np.inf, entries_per_page=50):
    n = 0
    page = 1
    while n < max_entries:
        # cmd = f'''curl -X GET {activites_url}?-d access_token={access_token}'''
        cmd = f'''curl -X GET {activites_url}?{access_token}&per_page={entries_per_page}&page={page}'''
        res = eval(os.popen(cmd).read().replace('null', 'None').replace('false', 'False').replace('true', 'True'))
        page += 1
        n += entries_per_page
        return res
get_activites(access_token)



# print("Access Token = {}\n".format(access_token))
# # access_token = 'ee409d14ac0b0c65aec31775dfc42ed9afac282a'
# header = {'Authorization': 'Bearer ' + access_token}
# param = {'per_page': 200, 'page': 1}
# my_dataset = requests.get(activites_url, headers=header, params=param).json()
#
# print(my_dataset[0]["name"])
# print(my_dataset[0]["map"]["summary_polyline"])