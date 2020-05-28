# Unconfigures the base vRA configuration in the HOL-2121 pod

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


def extract_values(obj, key):
    """Pull all values of specified key from nested JSON."""
    arr = []

    def extract(obj, arr, key):
        """Recursively search for values of key in JSON tree."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    extract(v, arr, key)
                elif k == key:
                    arr.append(v)
        elif isinstance(obj, list):
            for item in obj:
                extract(item, arr, key)
        return arr
    results = extract(obj, arr, key)
    return results


def get_deployments():
    # returns an array containing all of the deployment ids
    api_url = '{0}deployment/api/deployments'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        deployments = extract_values(json_data,'id')
        return deployments
    else:
        print('- Failed to find any deployments')
        return None


def delete_deployments(deployments):
    # deletes the list of deployments passed in as an array of ids
    count = len(deployments)
    data = {}
    for i in range(count):
        deplID = deployments[i]
        api_url = '{0}deployment/api/deployments/{1}'.format(api_url_base, deplID)
        response = requests.delete(api_url, headers=headers1, data=json.dumps(data), verify=False)
        if response.status_code == 200:
            print('- Successfully deleted the deployment')
        else:
            print('- Failed to delete the deployment')


def get_holproj():
    # returns the id of the HOL Project
    api_url = '{0}iaas/api/projects'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        count = json_data["totalElements"]
        for x in range(count):
            if 'HOL Project' in content[x]["name"]:       ## Looking to match the HOL Project name
                proj_id = (content[x]["id"])
                return proj_id
    else:
        print('- Failed to get the HOL project ID')
        return None


def unconfigure_project(proj_Id):
    api_url = '{0}iaas/api/projects/{1}'.format(api_url_base,proj_Id)
    data =  {
        "name": "HOL Project",
        "zoneAssignmentConfigurations": []
    }
    response = requests.patch(api_url, headers=headers1, data=json.dumps(data), verify=False)
    if response.status_code == 200:
        print('- Successfully removed cloud zones from HOL Project')
    else:
        print('- Failed to remove cloud zones from HOL Project')

def unconfigure_github():
    # removes GitHub
    github_id = "none"
    api_url = '{0}content/api/sources'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        count = json_data["page"]["totalElements"]
        for x in range(count):
            if 'GitHub CS' in content[x]["name"]:       ## Looking to match the GitHub source
                github_id = (content[x]["id"])
    if github_id == 'none':
        print('- no GitHub integration was found')
    else:
        api_url = '{0}content/api/sources/{1}'.format(api_url_base, github_id)
        response = requests.delete(api_url, headers=headers1, verify=False)
        if response.status_code == 204:
            print('- Successfully deleted the GitHub integration')
        else:
            print('- Failed to delete the GitHub integration')

    
def get_blueprints():
    api_url = '{0}blueprint/api/blueprints'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        bpIds = extract_values(json_data,'id')
        return bpIds
    else:
        print('- Failed to get the blueprint IDs')
        return None

def delete_blueprints(bps):
    # deletes the list of deployments passed in as an array of ids
    count = len(bps)
    data = {}
    for i in range(count):
        bpId = bps[i]
        api_url = '{0}blueprint/api/blueprints/{1}'.format(api_url_base, bpId)
        response = requests.delete(api_url, headers=headers1, data=json.dumps(data), verify=False)
        if response.status_code == 204:
            print('- Successfully deleted the blueprint')
        else:
            print('- Failed to delete the blueprint')


def delete_project(proj_Id):
    api_url = '{0}iaas/api/projects/{1}'.format(api_url_base,proj_Id)
    data =  {}
    response = requests.delete(api_url, headers=headers1, data=json.dumps(data), verify=False)
    if response.status_code == 204:
        print('- Successfully deleted the HOL Project')
    else:
        print('- Failed to delte the HOL Project')


def get_vsphere_ca():
    api_url = '{0}iaas/api/cloud-accounts-vsphere'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        Ids = extract_values(json_data,'id')
        return Ids
    else:
        print('- Failed to get any vSphere cloud accounts')
        return None


def delete_ca(cas):
    # deletes the list of deployments passed in as an array of ids
    count = len(cas)
    data = {}
    for i in range(count):
        caId = cas[i]
        api_url = '{0}iaas/api/cloud-accounts-vsphere/{1}'.format(api_url_base, caId)
        response = requests.delete(api_url, headers=headers1, data=json.dumps(data), verify=False)
        if response.status_code == 204:
            print('- Successfully deleted the cloud account')
        else:
            print('- Failed to delete the cloud account')


def get_czones():
    api_url = '{0}iaas/api/zones'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        Ids = extract_values(json_data,'id')
        return Ids
    else:
        print('- Failed to get any cloud zones')
        return None


def delete_zones(zones):
    # deletes the list of deployments passed in as an array of ids
    count = len(zones)
    data = {}
    for i in range(count):
        Id = zones[i]
        api_url = '{0}iaas/api/zones/{1}'.format(api_url_base, Id)
        response = requests.delete(api_url, headers=headers1, data=json.dumps(data), verify=False)
        if response.status_code == 204:
            print('- Successfully deleted the cloud zone')
        else:
            print('- Failed to delete the cloud zone')


##### MAIN #####

headers = {'Content-Type': 'application/json'}
access_key = get_token("admin","VMware1!")
headers1 = {'Content-Type': 'application/json',
           'Authorization': 'Bearer {0}'.format(access_key)}


print('Deleting deployments - this might take a minute')
deploymentIds = get_deployments()
deployment_count = len(deploymentIds)
delete_deployments(deploymentIds)
while deployment_count > 0:
    time.sleep(5)
    deploymentIds = get_deployments()
    deployment_count = len(deploymentIds)

print('Deleting the HOL Project')
hol_project = get_holproj()
unconfigure_project(hol_project)
unconfigure_github()
blueprint_ids = get_blueprints()
delete_blueprints(blueprint_ids)
delete_project(hol_project)

print('Deleting the private cloud account')
ca = get_vsphere_ca()
delete_ca(ca)

print('Deleting pubic cloud zones')
zones = get_czones()
delete_zones(zones)

