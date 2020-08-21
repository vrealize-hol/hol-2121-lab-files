import urllib3
import sys
import re
import subprocess
from time import strftime, sleep
import calendar
import datetime
from random import seed, randint
from boto3.dynamodb.conditions import Key, Attr
import boto3
import traceback
import os
import time
import requests
import json
urllib3.disable_warnings()

####### I M P O R T A N T #######
# If you are deploying this vPod dircetly in OneCloud and not through the Hands On Lab portal,
# you must uncomment the following lines and supply your own set of AWS and Azure keys
#################################
# awsid = "put your AWS access key here"
# awssec = "put your AWS secret hey here"
# azsub = "put your azure subscription id here"
# azten = "put your azure tenant id here"
# azappid = "put your azure application id here"
# azappkey = "put your azure application key here"

# also change the "local_creds" value below to True
local_creds = False

debug = True

github_key = os.getenv('github_key')
slack_api_key = 'T024JFTN4/B0150SYEHFE/zNcnyZqWvUcEtaqyiRlLj86O'

vra_fqdn = "vr-automation.corp.local"
api_url_base = "https://" + vra_fqdn + "/"
apiVersion = "2019-01-15"

gitlab_api_url_base = "http://gitlab.corp.local/api/v4/"
gitlab_token_suffix = "?private_token=H-WqAJP6whn6KCP2zGSz"
gitlab_header = {'Content-Type': 'application/json'}

# set internet proxy for for communication out of the vPod
proxies = {
    "http": "http://192.168.110.1:3128",
    "https": "https://192.168.110.1:3128"
}

def log(msg):
    if debug:
        sys.stdout.write(msg + '\n')
    file = open("C:\\hol\\vraConfig.log", "a")
    file.write(msg + '\n')
    file.close()


def send_slack_notification(payload):
    #slack_url = 'https://hooks.slack.com/services/'
    #post_url = slack_url + slack_api_key
    #requests.post(url=post_url, proxies=proxies, json=payload)
    return()


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


def get_token(user_name, pass_word):
    api_url = '{0}csp/gateway/am/api/login?access_token'.format(api_url_base)
    data = {
        "username": user_name,
        "password": pass_word
    }
    response = requests.post(api_url, headers=headers,
                             data=json.dumps(data), verify=False)
    if response.status_code == 200:
        json_data = response.json()
        key = json_data['access_token']
        return key
    else:
        return('not ready')


def get_vsphere_regions():
    api_url = '{0}iaas/api/cloud-accounts-vsphere/region-enumeration'.format(
        api_url_base)
    data = {
        "hostName": "vcsa-01a.corp.local",
        "acceptSelfSignedCertificate": "true",
        "password": "VMware1!",
        "name": "vSphere Cloud Account",
                "description": "vSphere Cloud Account",
                "username": "administrator@corp.local"
    }
    response = requests.post(api_url, headers=headers1,
                             data=json.dumps(data), verify=False)
    if response.status_code == 200:
        json_data = response.json()
        regions = json_data["externalRegionIds"]
        log('- Successfully got vSphere Datacenters')
        return(regions)
    else:
        log('- Failed to get vSphere Datacenters')
        return None


def get_czids():
    api_url = '{0}iaas/api/zones'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        cz_id = extract_values(json_data, 'id')
        return cz_id
    else:
        log('- Failed to get the cloud zone IDs')
        return None


def get_right_czid_vsphere(czid):
    api_url = '{0}iaas/api/zones/{1}'.format(api_url_base, czid)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        cz_name = extract_values(json_data, 'name')
        for x in cz_name:
            if 'RegionA01' in x:        # Looking for the CZ for vSphere
                return czid
    else:
        log('- Failed to get the right vSphere cloud zone ID')
        return None


def get_right_czid_aws(czid):
    api_url = '{0}iaas/api/zones/{1}'.format(api_url_base, czid)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        cz_name = extract_values(json_data, 'name')
        for x in cz_name:
            if x == 'AWS Cloud Account / us-west-1':
                return czid
    else:
        log('- Failed to get the right AWS cloud zone ID')
        return None


def get_right_czid_azure(czid):
    api_url = '{0}iaas/api/zones/{1}'.format(api_url_base, czid)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        cz_name = extract_values(json_data, 'name')
        for x in cz_name:
            if x == 'Azure Cloud Account / westus':
                return czid
    else:
        log('- Failed to get Azure cloud zone ID')
        return None


def get_czid_aws(czid):
    for x in czid:
        api_url = '{0}iaas/api/zones/{1}'.format(api_url_base, x)
        response = requests.get(api_url, headers=headers1, verify=False)
        if response.status_code == 200:
            json_data = response.json()
            cz_name = extract_values(json_data, 'name')
            cz_name = cz_name[0]
            if cz_name == 'AWS-West-1 / us-west-1':
                return x
        else:
            log('- Failed to get the AWS cloud zone ID')
            return None


def get_projids():
    api_url = '{0}iaas/api/projects'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        proj_id = extract_values(json_data, 'id')
        return proj_id
    else:
        log('- Failed to get the project IDs')
        return None


def get_right_projid(projid):
    api_url = '{0}iaas/api/projects/{1}'.format(api_url_base, projid)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        proj_name = extract_values(json_data, 'name')
        for x in proj_name:
            if x == 'HOL Project':
                return projid
    else:
        log('- Failed to get the right project ID')
        return None


def get_right_projid_rp(projid):
    api_url = '{0}iaas/api/projects/{1}'.format(api_url_base, projid)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        proj_name = extract_values(json_data, 'name')
        for x in proj_name:
            if x == 'Rainpole Project':
                return projid
    else:
        log('- Failed to get the right project ID')
        return None




def tag_vsphere_cz(cz_Ids):
    if cz_Ids is not None:
        for x in cz_Ids:
            cloudzone_id = get_right_czid_vsphere(x)
            if cloudzone_id is not None:
                api_url = '{0}iaas/api/zones/{1}'.format(
                    api_url_base, cloudzone_id)
                data = {
                    "name": "Private Cloud / RegionA01",
                            "placementPolicy": "SPREAD",
                    "tags": [
                        {
                            "key": "cloud",
                            "value": "vsphere"
                        }
                    ],
                    "tagsToMatch": [
                        {
                            "key": "compute",
                            "value": "vsphere"
                        }
                    ]
                }
                response = requests.patch(
                    api_url, headers=headers1, data=json.dumps(data), verify=False)
                if response.status_code == 200:
                    log('- Successfully Tagged vSphere Cloud Zone')
                    return(cloudzone_id)
                else:
                    log('- Failed to tag vSphere cloud zone')
                    return None
    else:
        log('- Failed to tag vSphere cloud zone')
        return None




def get_azure_regionid():
    api_url = '{0}iaas/api/regions'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        region_id = extract_values(json_data, 'id')
        for x in region_id:
            api_url2 = '{0}iaas/api/regions/{1}'.format(api_url_base, x)
            response2 = requests.get(api_url2, headers=headers1, verify=False)
            if response2.status_code == 200:
                json_data2 = json.loads(response2.content.decode('utf-8'))
                region_name = extract_values(json_data2, 'externalRegionId')
                compare = region_name[0]
                if compare == 'westus':
                    region_id = extract_values(json_data2, 'id')
                    return region_id
    else:
        log('- Failed to get Azure region ID')
        return None


def create_azure_flavor():
    azure_id = get_azure_regionid()
    azure_id = azure_id[0]
    api_url = '{0}iaas/api/flavor-profiles'.format(api_url_base)
    data = {
        "name": "azure",
                "flavorMapping": {
                    "tiny": {
                        "name": "Standard_B1ls"
                    },
                    "small": {
                        "name": "Standard_B1s"
                    },
                    "medium": {
                        "name": "Standard_B1ms"
                    },
                    "large": {
                        "name": "Standard_B2s"
                    }
                },
        "regionId": azure_id
    }
    response = requests.post(api_url, headers=headers1,
                             data=json.dumps(data), verify=False)
    if response.status_code == 201:
        log('- Successfully created Azure flavor mapping')
    else:
        log('- Failed to create Azure flavor mapping')
        return None


def get_aws_regionid():
    api_url = '{0}iaas/api/regions'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        region_id = extract_values(json_data, 'id')
        for x in region_id:
            api_url2 = '{0}iaas/api/regions/{1}'.format(api_url_base, x)
            response2 = requests.get(api_url2, headers=headers1, verify=False)
            if response2.status_code == 200:
                json_data2 = json.loads(response2.content.decode('utf-8'))
                region_name = extract_values(json_data2, 'externalRegionId')
                compare = region_name[0]
                if compare == 'us-west-1':
                    aws_region_id = extract_values(json_data2, 'id')
                    return aws_region_id
    else:
        log('- Failed to get AWS region')
        return None


def get_computeids():
    api_url = '{0}iaas/api/fabric-computes'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        comp_id = extract_values(json_data, 'id')
    return(comp_id)


def tag_vsphere_clusters(computes):
    for x in computes:
        api_url = '{0}iaas/api/fabric-computes/{1}'.format(api_url_base, x)
        response = requests.get(api_url, headers=headers1, verify=False)
        if response.status_code == 200:
            json_data = response.json()
            cluster = extract_values(json_data, 'name')
            if "Workload" in cluster[0]:
                ## This is a vSphere workload cluster - tag it ##
                data = {
                    "tags": [
                        {
                            "key": "compute",
                            "value": "vsphere"
                        }
                    ]
                }
                response1 = requests.patch(
                    api_url, headers=headers1, data=json.dumps(data), verify=False)
                if response1.status_code == 200:
                    msg = "- Tagged " + cluster[0] + " cluster"
                    log(msg)
                else:
                    msg = "- Failed to tag: " + cluster[0] + " cluster"
                    log(msg)

        else:
            log('Failed to tag vSphere workload clusters')
    return None



def get_fabric_network_ids():
    api_url = '{0}iaas/api/fabric-networks-vsphere'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        net_ids = extract_values(json_data, 'id')
    return(net_ids)


def update_networks(net_ids):
    for x in net_ids:
        api_url = '{0}iaas/api/fabric-networks-vsphere/{1}'.format(
            api_url_base, x)
        response = requests.get(api_url, headers=headers1, verify=False)
        if response.status_code == 200:
            json_data = response.json()
            network = extract_values(json_data, 'name')
            if "VM-Region" in network[0]:
                ## This is the vSphere VM network - update it ##
                data = {
                    "isDefault": "true",
                    "domain": "corp.local",
                    "defaultGateway": "192.168.110.1",
                    "dnsServerAddresses": ["192.168.110.10"],
                    "cidr": "192.168.110.0/24",
                            "dnsSearchDomains": ["corp.local"],
                            "tags": [
                                {
                                    "key": "net",
                                    "value": "vsphere"
                                }
                    ]
                }
                response1 = requests.patch(
                    api_url, headers=headers1, data=json.dumps(data), verify=False)
                if response1.status_code == 200:
                    log("- Updated the " + network[0] + " network")
                    return(x)
                else:
                    log("- Failed to update " + network[0] + " network")
                    return None

        else:
            log('Failed to get vSphere networks')
    return None



def get_vsphere_region_id():
    api_url = '{0}iaas/api/regions'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        count = json_data["totalElements"]
        for x in range(count):
            # Looking to match the vSphere datacenter name
            if 'RegionA01' in content[x]["name"]:
                vsphere_id = (content[x]["id"])
                return vsphere_id
    else:
        log('- Failed to get the vSphere region (datacenter) ID')
        return None

def get_vsphere_datastore_id():
    api_url = '{0}iaas/api/fabric-vsphere-datastores'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        count = json_data["totalElements"]
        for x in range(count):
            # Looking to match the right datastore name
            if 'ISCSI01' in content[x]["name"]:
                vsphere_ds = (content[x]["id"])
                return vsphere_ds
    else:
        log('- Failed to get the vSphere datastore ID')
        return None


def get_pricing_card():
    api_url = '{0}price/api/private/pricing-cards'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        count = json_data["totalElements"]
        for x in range(count):
            # Looking to match the Default pricing card
            if 'Default Pricing' in content[x]["name"]:
                id = (content[x]["id"])
                return id
    else:
        log('- Failed to get default pricing card')
        return None

def sync_price():
    url = f"{api_url_base}price/api/sync-price-task"
    response = requests.request(
        "POST", url, headers=headers1, data=json.dumps({}), verify=False)
    if response.status_code == 202:
        log('- Successfully synced prices')
    else:
        log(f'- Failed to sync prices ({response.status_code})')


def get_blueprint_id(bpName):
    api_url = '{0}blueprint/api/blueprints'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        count = json_data["totalElements"]
        for x in range(count):
            if bpName in content[x]["name"]:  # Looking to match the blueprint name
                bp_id = (content[x]["id"])
                return bp_id
    else:
        log('- Failed to get the blueprint ID for ' + bpName)
        return None


def get_cat_id(item_name):
    api_url = '{0}catalog/api/items'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        count = json_data["totalElements"]
        for x in range(count):
            # Looking to match the named catalog item
            if item_name in content[x]["name"]:
                cat_id = (content[x]["id"])
                return cat_id
    else:
        log('- Failed to get the blueprint ID')
        return None


def getOrg(headers):
    url = f"{api_url_base}csp/gateway/am/api/loggedin/user/orgs"
    response = requests.request(
        "GET", url, headers=headers, verify=False)
    return response.json()['items'][0]['id']


def getEndpoints(headers):
    url = f"{api_url_base}provisioning/uerp/provisioning/mgmt/endpoints?expand"
    response = requests.request("GET", url, headers=headers, verify=False)
    if response.status_code == 200:
        log("- Successfully retrieved endpoint list")    
        endpointList = {}
        for endpoint_link in response.json()['documentLinks']:
            endpoint = response.json()['documents'][endpoint_link]
            endpointList[endpoint['endpointType']] = endpoint['documentSelfLink']
        return endpointList


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
            log('- Did not find the dev gitlab project')
    else:
        log('- Failed to get gitlab projects')


def update_git_proj(projId):
    # sets the visibility of the passed project ID to public
    api_url = '{0}projects/{1}{2}'.format(gitlab_api_url_base, projId, gitlab_token_suffix)
    data = {
        "visibility": "public"
    }
    response = requests.put(api_url, headers=gitlab_header, data=json.dumps(data), verify=False)
    if response.status_code == 200:
        log('- Updated the gitlab project')
    else:
        log('- Failed to update the gitlab project')


##### MAIN #####

headers = {'Content-Type': 'application/json'}

###########################################
# API calls below as vcapadmin
###########################################
access_key = get_token("vcapadmin", "VMware1!")

# find out if vRA is ready. if not ready we need to exit or the configuration will fail
if access_key == 'not ready':  # we are not even getting an auth token from vRA yet
    log('\n\n\nvRA is not yet ready in this pod - no access token yet')
    log('Wait for the lab status to be *Ready* and then run this script again')
    sys.stdout.write('vRA did not return an access key')
    sys.exit(1)

headers1 = {'Content-Type': 'application/json',
            'Authorization': 'Bearer {0}'.format(access_key)}
headers2 = {'Content-Type': 'application/x-yaml',
            'Authorization': 'Bearer {0}'.format(access_key)}

