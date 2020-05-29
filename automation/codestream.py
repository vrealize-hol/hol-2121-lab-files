import json
import requests
import time
import urllib3
urllib3.disable_warnings()
    

vra_fqdn = "vr-automation.corp.local"
api_url_base = "https://" + vra_fqdn + "/"


def get_token(user_name,pass_word):
    api_url = '{0}csp/gateway/am/api/login?access_token'.format(api_url_base)
    data =  {
              "username": user_name,
              "password": pass_word
            }
    response = requests.post(api_url, headers=headers, data=json.dumps(data), verify=False)
    if response.status_code == 200:
        json_data = response.json()
        key = json_data['access_token']
        return key
    else:
        return('not ready')


def import_pipelines(pipeNames):
    # imports code stream pipelines contained in the array of names
    api_url = '{0}codestream/api/import'.format(api_url_base)
    count = len(pipeNames)
    for i in range(count):
        fname = pipeNames[i]
        fileName = './automation/', fname, '.yaml'
        file = open(fileName, 'r')
        payload = file.read()
        response = requests.post(api_url, headers=headers2, data=payload, verify=False)
        if response.status_code == 200:
            print('- Imported', fname, 'pipeline')
        else:
            print('- Failed to imort', fname, 'pipeline')



def delete_custom_resource_actions(actions):
    # deletes the list of custom resource actions passed in as an array of ids
    count = len(actions)
    for i in range(count):
        actionId = actions[i]
        api_url = '{0}form-service/api/custom/resource-actions/{1}'.format(api_url_base, actionId)
        response = requests.delete(api_url, headers=headers1, verify=False)
        if response.status_code == 200:
            print('- Successfully deleted the custom resrouce action')
        else:
            print('- Failed to delete the custom resource action')


def get_custom_resources():
    # returns an array containing all of the custom resource ids
    api_url = '{0}form-service/api/custom/resource-types'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        count = json_data["totalElements"]
        arr = []
        for i in range(count):
            Id = content[i]["id"]
            arr.append(Id)
        return arr
    else:
        print('- Failed get custom resrouces')
        return None


def delete_custom_resources(actions):
    # deletes the list of custom resources passed in as an array of ids
    count = len(actions)
    for i in range(count):
        actionId = actions[i]
        api_url = '{0}form-service/api/custom/resource-types/{1}'.format(api_url_base, actionId)
        response = requests.delete(api_url, headers=headers1, verify=False)
        if response.status_code == 200:
            print('- Successfully deleted the custom resrouces')
        else:
            print('- Failed to delete the custom resource')



##### MAIN #####

headers = {'Content-Type': 'application/json'}
access_key = get_token("admin","VMware1!")
headers1 = {'Content-Type': 'application/json',
           'Authorization': 'Bearer {0}'.format(access_key)}
headers2 = {'Content-Type': 'application/x-yaml',
           'Authorization': 'Bearer {0}'.format(access_key)}


print('Importing Code Stream pipelines')
pipe_names = ['CS-Reset-Resources', 'CS-Base-Configuration']
import_pipelines(pipe_names)
#pipeIds = get_pipelines()



