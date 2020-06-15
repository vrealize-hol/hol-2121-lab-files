import json
import urllib3
urllib3.disable_warnings()

gitlab_api_url_base = "http://gitlab.corp.local/api/v4/"
gitlab_token_suffix = "?private_token=H-WqAJP6whn6KCP2zGSz"
gitlab_header = {'Content-Type': 'application/json'}

def get_gitlab_projects():
    # returns an array containing all of the project ids
    api_url = '{0}projects{1}'.format(gitlab_api_url_base, gitlab_token_suffix)
    response = requests.get(api_url, headers=gitlab_header, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        Ids = extract_values(json_data, 'id')
        return Ids
    else:
        print('- Failed to get pipelines')
        return None

git_proj_ids = get_gitlab_projects()
print git_proj_ids

