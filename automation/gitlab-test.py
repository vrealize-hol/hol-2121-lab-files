import json
import urllib3
import requests
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
        for project in json_data:
            if 'dev' in project['name']:        # looking for the 'dev' project
                return project['id']
        else:
            print('- Did not find the dev gitlab project')
    else:
        print('- Failed to get pipelines')


def update_git_proj(projId):
    # sets the visibility of the passed project ID to public
    api_url = '{0}projects/{1}{2}'.format(gitlab_api_url_base, projId, gitlab_token_suffix)
    data = {
        "visibility": "public"
    }
    response = requests.put(api_url, headers=gitlab_header, data=json.dumps(data), verify=False)
    if response.status_code == 200:
        print('- Updated the gitlab project')
    else:
        print('- Failed to update the gitlab project')


git_proj_id = get_gitlab_projects()
update_git_proj(git_proj_id)

