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

def get_vlp_urn():
    # determine current pod's URN (unique ID) using Main Console guestinfo
    # this uses a VLP-set property named "vlp_vapp_urn" and will only work for a pod deployed by VLP

    tools_location = 'C:\\Program Files\\VMware\\VMware Tools\\vmtoolsd.exe'
    command = '--cmd "info-get guestinfo.ovfenv"'
    full_command = tools_location + " " + command

    if os.path.isfile(tools_location):
        response = subprocess.run(full_command, stdout=subprocess.PIPE)
        byte_response = response.stdout
        txt_response = byte_response.decode("utf-8")

        try:
            urn = re.search('urn:vcloud:vapp:(.+?)"/>', txt_response).group(1)
        except:
            return('No urn parameter found')

        if len(urn) > 0:
            return urn
        else:
            return('No urn value found')

    else:
        return('Error: VMware tools not found')


def get_available_pod():
    # this function checks the dynamoDB to see if there are any available AWS and Azure key sets to configure the cloud accounts

    dynamodb = boto3.resource(
        'dynamodb', aws_access_key_id=d_id, aws_secret_access_key=d_sec, region_name=d_reg)
    table = dynamodb.Table('HOL-keys')

    response = table.scan(
        FilterExpression=Attr('reserved').eq(0),
        ProjectionExpression="pod, in_use"
    )
    pods = response['Items']
    # the number of pods not reserved
    num_not_reserved = len(pods)
    available_pods = 0  # set counter to zero
    pod_array = []
    for i in pods:
        if i['in_use'] == 0:  # pod is available
            available_pods += 1  # increment counter
            pod_array.append(i['pod'])

    if available_pods == 0:  # all credentials are assigned
        # get the oldest credentials and re-use those
        response = table.scan(
            FilterExpression=Attr('check_out_epoch').gt(0),
            ProjectionExpression="pod, check_out_epoch"
        )
        pods = response['Items']
        oldest = pods[0]['check_out_epoch']
        pod = pods[0]['pod']
        for i in pods:
            if i['check_out_epoch'] < oldest:
                pod = i['pod']
                oldest = i['check_out_epoch']
    else:
        # get random pod from those available
        dt = datetime.datetime.microsecond
        seed(dt)
        rand_int = randint(0, available_pods-1)
        pod = pod_array[rand_int]
    return(pod, num_not_reserved, available_pods)


def get_creds(cred_set, vlp_urn_id):

    dynamodb = boto3.resource(
        'dynamodb', aws_access_key_id=d_id, aws_secret_access_key=d_sec, region_name=d_reg)
    table = dynamodb.Table('HOL-keys')

    a = time.gmtime()  # gmt in structured format
    epoch_time = calendar.timegm(a)  # convert to epoc
    human_time = strftime("%m-%d-%Y %H:%M", a)

    # get the key set
    response = table.get_item(
        Key={
            'pod': cred_set
        }
    )
    results = response['Item']

    # write some items
    response = table.update_item(
        Key={
            'pod': cred_set
        },
        UpdateExpression="set in_use = :inuse, vlp_urn=:vlp, check_out_epoch=:out, check_out_human=:hout",
        ExpressionAttributeValues={
            ':inuse': 1,
            ':vlp': vlp_urn_id,
            ':out': epoch_time,
            ':hout': human_time
        },
        ReturnValues="UPDATED_NEW"
    )

    return(results)

def log(msg):
    if debug:
        sys.stdout.write(msg + '\n')
    file = open("C:\\hol\\vraConfig.log", "a")
    file.write(msg + '\n')
    file.close()


def send_slack_notification(payload):
    slack_url = 'https://hooks.slack.com/services/'
    post_url = slack_url + slack_api_key
    requests.post(url=post_url, proxies=proxies, json=payload)
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


def create_vsphere_ca(region_ids):
    api_url = '{0}iaas/api/cloud-accounts-vsphere'.format(api_url_base)
    data = {
        "hostName": "vcsa-01a.corp.local",
        "acceptSelfSignedCertificate": "true",
        "password": "VMware1!",
        "createDefaultZones": "true",
        "name": "Private Cloud",
                "description": "vSphere Cloud Account",
                "regionIds": region_ids,
                "username": "administrator@corp.local",
                "tags": [
                ]
    }
    response = requests.post(api_url, headers=headers1,
                             data=json.dumps(data), verify=False)
    if response.status_code == 201:
        log('- Successfully Created vSphere Cloud Account')
    else:
        log('- Failed to Create the vSphere Cloud Account')
        return None


def create_aws_ca():
    api_url = '{0}iaas/api/cloud-accounts-aws'.format(api_url_base)
    data = {
        "description": "AWS Cloud Account",
        "accessKeyId": awsid,
        "secretAccessKey": awssec,
        "cloudAccountProperties": {

        },
        "regionIds": [
            "us-west-1"
        ],
        "tags": [
        ],
        "createDefaultZones": "true",
        "name": "AWS Cloud Account"
    }
    response = requests.post(api_url, headers=headers1,
                             data=json.dumps(data), verify=False)
    if response.status_code == 201:
        log('- Successfully Created AWS Cloud Account')
    else:
        log('- Failed to Create the AWS Cloud Account')
        return None


def create_azure_ca():
    api_url = '{0}iaas/api/cloud-accounts-azure'.format(api_url_base)
    data = {
        "name": "Azure Cloud Account",
        "description": "Azure Cloud Account",
        "subscriptionId": azsub,
        "tenantId": azten,
        "clientApplicationId": azappid,
        "clientApplicationSecretKey": azappkey,
        "regionIds": [
            "westus"
        ],
        "tags": [
        ],
        "createDefaultZones": "true"
    }
    response = requests.post(api_url, headers=headers1,
                             data=json.dumps(data), verify=False)
    if response.status_code == 201:
        log('- Successfully Created Azure Cloud Account')
    else:
        log('- Failed to create the Azure Cloud Account')
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


def create_project(vsphere, aws, azure):
    api_url = '{0}iaas/api/projects'.format(api_url_base)
    data = {
        "name": "HOL Project",
                "zoneAssignmentConfigurations": [
                    {
                        "zoneId": vsphere,
                        "maxNumberInstances": 20,
                        "priority": 1,
                        "cpuLimit": 40,
                        "memoryLimitMB": 33554
                    },
                    {
                        "zoneId": aws,
                        "maxNumberInstances": 10,
                        "priority": 1,
                        "cpuLimit": 20,
                        "memoryLimitMB": 41943

                    },
                    {
                        "zoneId": azure,
                        "maxNumberInstances": 10,
                        "priority": 1,
                        "cpuLimit": 20,
                        "memoryLimitMB": 41943
                    }
                ],
        "administrators": [
                    {
                        "email": "holadmin"
                    }
                ],
        "members": [
                    {
                        "email": "holuser"
                    },
                    {
                        "email": "holdev"
                    }
                ],
        "machineNamingTemplate": "${resource.name}-${###}",
        "sharedResources": "true"
    }
    response = requests.post(api_url, headers=headers1,
                             data=json.dumps(data), verify=False)
    if response.status_code == 201:
        json_data = response.json()
        project_id = extract_values(json_data, 'id')
        log('- Successfully created the HOL Project')
        return project_id[0]
    else:
        log('- Failed to create the HOL Project')


def create_labauto_project():
    api_url = '{0}iaas/api/projects'.format(api_url_base)
    data = {
        "name": "Lab Automation Project",
        "administrators": [
                    {
                        "email": "holadmin"
                    }
                ],
        "sharedResources": "true"
    }
    response = requests.post(api_url, headers=headers1,
                             data=json.dumps(data), verify=False)
    if response.status_code == 201:
        log('- Successfully created the Lab Automation project')
    else:
        log('- Failed to create the Lab Automation project')


def create_sd_project():
    api_url = '{0}iaas/api/projects'.format(api_url_base)
    data = {
        "name": "Service Desk Project",
                "zoneAssignmentConfigurations": [],
        "administrators": [
                    {
                        "email": "holadmin"
                    }
                ],
        "members": [
                    {
                        "email": "holservicedesk"
                    }
                ],
        "sharedResources": "true"
    }
    response = requests.post(api_url, headers=headers1,
                             data=json.dumps(data), verify=False)
    if response.status_code == 201:
        log('- Successfully created the Service Desk Project')
    else:
        log('- Failed to create the Service Desk Project')


def create_odyssey_project(vsphere, aws, azure):
    api_url = '{0}iaas/api/projects'.format(api_url_base)
    data = {
        "name": "Odyssey Project",
                    "zoneAssignmentConfigurations": [
                        {
                        "zoneId": vsphere
                        },
                        {
                        "zoneId": aws
                        },
                        {
                        "zoneId": azure
                        }
                    ],
                    "administrators": [
                        {
                            "email": "holadmin"
                        }
                    ],
                    "members": [
                        {
                            "email": "holuser"
                        },
                        {
                            "email": "holdev"
                        }
                    ],
        "sharedResources": "true"
                }
    response = requests.post(api_url, headers=headers1,
                             data=json.dumps(data), verify=False)
    if response.status_code == 201:
        log('- Successfully created the Odyssey Project')
    else:
        log('- Failed to create the Odyssey Project')


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


def tag_aws_cz(cz_Ids):
    if cz_Ids is not None:
        for x in cz_Ids:
            cloudzone_id = get_right_czid_aws(x)
            if cloudzone_id is not None:
                api_url = '{0}iaas/api/zones/{1}'.format(
                    api_url_base, cloudzone_id)
                data = {
                    "name": "AWS / us-west-1",
                    "tags": [
                        {
                            "key": "cloud",
                            "value": "aws"
                        }
                    ]
                }
                response = requests.patch(
                    api_url, headers=headers1, data=json.dumps(data), verify=False)
                if response.status_code == 200:
                    log('- Successfully Tagged AWS cloud zone')
                    return cloudzone_id
                else:
                    log('- Failed to tag AWS cloud zone - bad response code')
                    return None
    else:
        log('- Failed to tag AWS cloud zone'
)
        return None


def tag_azure_cz(cz_Ids):
    if cz_Ids is not None:
        for x in cz_Ids:
            cloudzone_id = get_right_czid_azure(x)
            if cloudzone_id is not None:
                api_url = '{0}iaas/api/zones/{1}'.format(
                    api_url_base, cloudzone_id)
                data = {
                    "name": "Azure / West US",
                    "tags": [
                        {
                            "key": "cloud",
                            "value": "azure"
                        }
                    ]
                }
                response = requests.patch(
                    api_url, headers=headers1, data=json.dumps(data), verify=False)
                if response.status_code == 200:
                    log('- Successfully tagged Azure cloud zone')
                    return cloudzone_id
                else:
                    log('- Failed to tag Azure cloud zone')
                    return None
    else:
        log('- Failed to tag Azure cloud zone')
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


def create_aws_flavor():
    aws_id = get_aws_regionid()
    aws_id = aws_id[0]
    api_url = '{0}iaas/api/flavor-profiles'.format(api_url_base)
    data = {
        "name": "aws-west-1",
                "flavorMapping": {
                    "tiny": {
                        "name": "t2.nano"
                    },
                    "small": {
                        "name": "t2.micro"
                    },
                    "medium": {
                        "name": "t2.small"
                    },
                    "large": {
                        "name": "t2.medium"
                    }
                },
        "regionId": aws_id
    }
    response = requests.post(api_url, headers=headers1,
                             data=json.dumps(data), verify=False)
    if response.status_code == 201:
        log('- Successfully created AWS flavors')
    else:
        log('- Failed to created AWS flavors')
        return None


def create_aws_image():
    aws_id = get_aws_regionid()
    aws_id = aws_id[0]
    api_url = '{0}iaas/api/image-profiles'.format(api_url_base)
    data = {
        "name": "aws-image-profile",
        "description": "Image Profile for AWS Images",
        "imageMapping": {
            "CentOS7": {
                "name": "ami-a83d0cc8"
            },
            "Ubuntu18": {
                "name": "ami-0d705db840ec5f0c5"
            }
        },
        "regionId": aws_id
    }
    response = requests.post(api_url, headers=headers1,
                             data=json.dumps(data), verify=False)
    if response.status_code == 201:
        log('- Successfully created AWS images')
    else:
        log('- Failed to created AWS images')
        return None


def create_azure_image():
    azure_id = get_azure_regionid()
    azure_id = azure_id[0]
    api_url = '{0}iaas/api/image-profiles'.format(api_url_base)
    data = {
        "name": "azure-image-profile",
        "description": "Image Profile for Azure Images",
        "imageMapping": {
            "Ubuntu18": {
                "name": "Canonical:UbuntuServer:18.04-LTS:latest"
            },
            "CentOS7": {
                "name": "OpenLogic:CentOS:7.4:7.4.20180704"
            }
        },
        "regionId": azure_id
    }
    response = requests.post(api_url, headers=headers1,
                             data=json.dumps(data), verify=False)
    if response.status_code == 201:
        log('- Successfully created Azure images')
    else:
        log('- Failed to created Azure images')
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


def add_github_integration():
    # adds GitHub as an integration endpoint
    api_url = '{0}provisioning/uerp/provisioning/mgmt/endpoints?external'.format(
        api_url_base)
    data = {
        "endpointProperties": {
            "url": "https://api.github.com",
            "privateKey": github_key,
            "dcId": "onprem"
        },
        "customProperties": {
            "isExternal": "true"
        },
        "endpointType": "com.github.saas",
        "associatedEndpointLinks": [],
        "name": "HOL Lab Files",
        "tagLinks": []
    }
    response = requests.post(api_url, headers=headers1,
                             data=json.dumps(data), verify=False)
    if response.status_code == 200:
        json_data = response.json()
        integrationSelfLink = json_data["documentSelfLink"]
        integrationId = re.findall(
            r"([0-9A-F]{8}[-]?(?:[0-9A-F]{4}[-]?){3}[0-9A-F]{12})", integrationSelfLink, re.IGNORECASE)[0]
        log('- Successfully added GitHub integration endpoint')
        return(integrationId)
    else:
        log('- Failed to add GitHub integration endpoint')


def configure_github(projId, gitId):
    # adds GitHub blueprint integration with the HOL Project
    api_url = '{0}content/api/sources'.format(api_url_base)
    data = {
        "name": "GitHub CS",
        "typeId": "com.github",
        "syncEnabled": "true",
        "projectId": projId,
        "config": {
            "integrationId": gitId,
            "repository": "vrealize-hol/hol-2121-lab-files",
            "path": "blueprints",
            "branch": "sandbox",
            "contentType": "blueprint"
        }
    }
    response = requests.post(api_url, headers=headers1,
                             data=json.dumps(data), verify=False)
    if response.status_code == 201:
        log('- Successfully added blueprint repo to project')
    else:
        log('- Failed to add the blueprint repo to project')


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


def create_ip_pool():
    api_url = '{0}iaas/api/network-ip-ranges'.format(api_url_base)
    data = {
        "ipVersion": "IPv4",
        "fabricNetworkId": vm_net_id,
        "name": "vSphere Static Pool",
                "description": "For static IP assignment to deployed VMs",
                "startIPAddress": "192.168.110.225",
                "endIPAddress": "192.168.110.254"
    }
    response = requests.post(api_url, headers=headers1,
                             data=json.dumps(data), verify=False)
    if response.status_code == 201:
        log('- Successfully created the IP pool')
    else:
        log('- Failed to create the IP pool')
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


def create_net_profile():
    api_url = '{0}iaas/api/network-profiles'.format(api_url_base)
    data = {
        "regionId": vsphere_region_id,
        "fabricNetworkIds": [vm_net_id],
        "name": "vSphere Networks",
                "description": "vSphere networks where VMs will be deployed",
                "tags": [
                    {
                        "key": "net",
                        "value": "vsphere"
                    }
        ]
    }
    response = requests.post(api_url, headers=headers1,
                             data=json.dumps(data), verify=False)
    if response.status_code == 201:
        log('- Successfully created the network profile')
    else:
        log('- Failed to create the network profile')
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


def create_storage_profile():
    api_url = '{0}iaas/api/storage-profiles-vsphere'.format(api_url_base)
    data = {
        "regionId": vsphere_region_id,
        "datastoreId": datastore,
        "name": "vSphere Storage",
                "description": "vSphere shared datastore where VMs will be deployed",
                "sharesLevel": "normal",
                "diskMode": "dependent",
                "provisioningType": "thin",
                "defaultItem": "true",
                "tags": [
                            {
                                "key": "storage",
                                "value": "vsphere"
                            }
                ]
    }
    response = requests.post(api_url, headers=headers1,
                             data=json.dumps(data), verify=False)
    if response.status_code == 201:
        log('- Successfully created the storage profile')
    else:
        log('- Failed to create the storage profile')
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

def modify_pricing_card(cardid):
    # modifies the Default Pricing card
    api_url = '{0}price/api/private/pricing-cards/{1}'.format(
        api_url_base, cardid)
    data = {
        "name": "HOL Pricing Card",
        "description": "Sets pricing rates for vSphere VMs",
        "meteringItems": [
            {
                "itemName": "vcpu",
                "metering": {
                    "baseRate": 29,
                    "chargePeriod": "MONTHLY",
                    "chargeOnPowerState": "ALWAYS",
                    "chargeBasedOn": "USAGE"
                }
            },
            {
                "itemName": "memory",
                "metering": {
                    "baseRate": 85,
                    "chargePeriod": "MONTHLY",
                    "chargeOnPowerState": "ALWAYS",
                    "chargeBasedOn": "USAGE",
                    "unit": "gb"
                },
            },
            {
                "itemName": "storage",
                "metering": {
                    "baseRate": 0.14,
                    "chargePeriod": "MONTHLY",
                    "chargeOnPowerState": "ALWAYS",
                    "chargeBasedOn": "USAGE",
                    "unit": "gb"
                }
            }
        ],
        "chargeModel": "PAY_AS_YOU_GO"
    }
    response = requests.put(api_url, headers=headers1,
                            data=json.dumps(data), verify=False)
    if response.status_code == 200:
        log('- Successfully modified the pricing card')
    else:
        log('- Failed to modify the pricing card')


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


def release_blueprint(bpid, ver):
    api_url = '{0}blueprint/api/blueprints/{1}/versions/{2}/actions/release'.format(
        api_url_base, bpid, ver)
    data = {}
    response = requests.post(api_url, headers=headers1,
                             data=json.dumps(data), verify=False)
    if response.status_code == 200:
        log('- Successfully released the blueprint')
    else:
        log('- Failed to releasea the blueprint')


def add_bp_cat_source(projid):
    # adds blueprints from 'projid' project as a content source
    api_url = '{0}catalog/api/admin/sources'.format(api_url_base)
    data = {
        "name": "HOL Project Blueprints",
        "typeId": "com.vmw.blueprint",
        "description": "Released blueprints in the HOL Project",
        "config": {"sourceProjectId": projid},
        "projectId": projid
    }
    response = requests.post(api_url, headers=headers1,
                             data=json.dumps(data), verify=False)
    if response.status_code == 201:
        json_data = response.json()
        sourceId = json_data["id"]
        log('- Successfully added blueprints as a catalog source')
        return sourceId
    else:
        log('- Failed to add blueprints as a catalog source')
        return None


def share_bps(source, project):
    # shares blueprint content (source) from 'projid' project to the catalog
    api_url = '{0}catalog/api/admin/entitlements'.format(api_url_base)
    data = {
        "definition": {"type": "CatalogSourceIdentifier", "id": source},
        "projectId": project
    }
    response = requests.post(api_url, headers=headers1,
                             data=json.dumps(data), verify=False)
    if response.status_code == 201:
        log('- Successfully added blueprint catalog entitlement')
    else:
        log('- Failed to add blueprint catalog entitlement')
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


def deploy_cat_item(catId, project):
    # shares blueprint content (source) from 'projid' project to the catalog
    api_url = '{0}catalog/api/items/{1}/request'.format(api_url_base, catId)
    data = {
        "deploymentName": "vSphere Ubuntu",
        "projectId": project,
        "version": "1",
        "reason": "Deployment of vSphere vm from blueprint",
        "inputs": {}
    }
    response = requests.post(api_url, headers=headers1,
                             data=json.dumps(data), verify=False)
    if response.status_code == 200:
        log('- Successfully deployed the catalog item')
    else:
        log('- Failed to deploy the catalog item')


def check_for_assigned(vlpurn):
    # this function checks the dynamoDB to see if this pod urn already has a credential set assigned

    dynamodb = boto3.resource(
        'dynamodb', aws_access_key_id=d_id, aws_secret_access_key=d_sec, region_name=d_reg)
    table = dynamodb.Table('HOL-keys')

    response = table.scan(
        FilterExpression="attribute_exists(vlp_urn)",
        ProjectionExpression="pod, vlp_urn"
    )
    urns = response['Items']
    urn_assigned = False
    for i in urns:
        if i['vlp_urn'] == vlpurn:  # This URN already has a key assigned
            urn_assigned = True

    return(urn_assigned)


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


def addCustomResource(headers, vro_endpoint, resource_file):
    resource_content = json.loads(open(resource_file).read())
    resource_content['mainActions']['create']['endpointLink'] = vro_endpoint
    resource_content['mainActions']['delete']['endpointLink'] = vro_endpoint

    url = f"{api_url_base}form-service/api/custom/resource-types"
    response = requests.request(
        "POST", url, headers=headers, data=json.dumps(resource_content), verify=False)
    if response.status_code == 200:
        log("- Successfully added Custom Resource")
    else:
        log(f"- Failed to add Custom Resource ({response.status_code})")


def addResourceAction(headers, vro_endpoint, org, resource_file):
    resource_content = json.loads(open(resource_file).read())
    resource_content['runnableItem']['endpointLink'] = vro_endpoint
    resource_content['orgId'] = org
    resource_content['formDefinition']['tenant'] = org

    url = f"{api_url_base}form-service/api/custom/resource-actions"
    response = requests.request(
        "POST", url, headers=headers, data=json.dumps(resource_content), verify=False)
    if response.status_code == 200:
        response = requests.request(
            "POST", url, headers=headers, data=json.dumps(resource_content), verify=False)
        if response.status_code == 200:
            log("- Successfully added Custom Action")
        else:
            log(f"- Failed to add Custom Action ({response.status_code})")
    else:
        log(f"- Failed to add Custom Action ({response.status_code})")


def create_approval_policy(catId, projId):
    # creates an approval policy
    api_url = '{0}policy/api/policies'.format(api_url_base)
    data = {
        "name" : "Azure approval",
        "description" : "Approval policy for a catalog item that deploys to Azure",
        "typeId" : "com.vmware.policy.approval",
        "enforcementType" : "HARD",
        "projectId" : projId,
        "definition" : {
            "level" : 1,
            "approvalMode" : "ANY_OF",
            "autoApprovalDecision" : "APPROVE",
            "approvers" : [
                "USER:holadmin"
                ],
            "autoApprovalExpiry" :1,
            "actions" :[
                "Deployment.Create"
                ]
            },
        "criteria" :{
            "matchExpression" :[
                {
                    "key" :"catalogItemId",
                    "operator" :"eq",
                    "value" :catId
                }
            ]
        }
    }
    response = requests.post(api_url, headers=headers1, data=json.dumps(data) ,verify=False)
    if response.status_code == 201:
        log('- Successfully created the approval policy')
    else:
        log('- Failed to create the approval policy')


def create_cs_endpoint():
    # creates a dummy code stream endpoint for the chat app pipeline example
    api_url = '{0}codestream/api/endpoints'.format(api_url_base)
    data = {
        "name": "Ent PKS Prod",
        "description": "Dummy endpoint for chat app pipeline",
        "isRestreicted": "",
        "project": "HOL Project",
        "type": "k8s",
        "properties": {
            "kubernetesURL": "http://1.2.3.4",
            "authType": "basicAuth",
            "userName": "holuser",
            "password": "VMware1!"
        }
    }
    response = requests.post(api_url, headers=headers1, data=json.dumps(data) ,verify=False)
    if response.status_code == 200:
        log('- Successfully created the code stream endpoint')
    else:
        log('- Failed to create the code stream endpoint')


def import_pipelines(pipeNames):
    # imports code stream pipelines contained in the array of names
    api_url = '{0}codestream/api/import'.format(api_url_base)
    count = len(pipeNames)
    for i in range(count):
        fname = pipeNames[i]
        fileName = 'C:/hol-2121-lab-files/automation/' + fname + '.yaml'
        file = open(fileName, 'r')
        payload = file.read()
        response = requests.post(api_url, headers=headers2, data=payload, verify=False)
        if response.status_code == 200:
            log('- Imported' + fname + 'pipeline')
        else:
            log('- Failed to imort' + fname + 'pipeline')


def get_pipelines():
    # returns an array containing all of the pipeline ids
    api_url = '{0}codestream/api/pipelines'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        Ids = extract_values(json_data, 'id')
        return Ids
    else:
        log('- Failed to get pipelines')
        return None


def enable_pipelines(Ids):
    # enables all pipelines the array
    count = len(Ids)
    data = { "enabled": "true"}
    for i in range(count):
        api_url = '{0}codestream/api/pipelines/{1}'.format(api_url_base, Ids[i])
        response = requests.patch(api_url, headers=headers1, data=json.dumps(data), verify=False)
        if response.status_code == 200:
            log('- Enabled pipeline')
        else:
            log('- Failed to enable pipeline')

def is_configured():
    # checks to see if vRA is already configured
    api_url = '{0}iaas/api/cloud-accounts'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        caTypes = extract_values(json_data, 'cloudAccountType')
        for x in caTypes:
            if 'azure' in x: 
                return True
        return False
    else:
        log('Could not get cloud accounts')


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

if local_creds != True:
    log('Getting ddb creds from router')
    try:
        keyfile = subprocess.check_output('plink -ssh router -l holuser -pw VMware1! cat mainconsole/ddb.json')
    except:
        log('Unable to get ddb creds from router')
        log('... exiting')
        vlpurn = get_vlp_urn()
        payload = {"text": f"*WARNING - Could not get ddb creds for the pod with VLP URN: {vlpurn}*"}
        send_slack_notification(payload)
        sys.exit()
    log('Got ddb creds from router')
    json_data = json.loads(keyfile)
    d_id = json_data['d_id']
    d_sec = json_data['d_sec']
    d_reg = json_data['d_reg']
    subprocess.call('plink -ssh router -l holuser -pw VMware1! rm mainconsole/ddb.json')
    log('Removed ddb creds from router')

###########################################
# API calls below as holadmin
###########################################
access_key = get_token("holadmin", "VMware1!")

# find out if vRA is ready. if not ready we need to exit or the configuration will fail
if access_key == 'not ready':  # we are not even getting an auth token from vRA yet
    log('\n\n\nvRA is not yet ready in this Hands On Lab pod - no access token yet')
    log('Wait for the lab status to be *Ready* and then run this script again')
    sys.stdout.write('vRA did not return an access key')
    sys.exit(1)

headers1 = {'Content-Type': 'application/json',
            'Authorization': 'Bearer {0}'.format(access_key)}
headers2 = {'Content-Type': 'application/x-yaml',
            'Authorization': 'Bearer {0}'.format(access_key)}

# check to see if vRA is already configured and exit if it is
if is_configured():
    log('vRA is already configured')
    log('... exiting')
    sys.stdout.write('vRA is already configured')
    sys.exit(1)

# check to see if this vPod was deployed by VLP (is it an active Hands on Lab?)
result = get_vlp_urn()
log('VLP URN = ' + result)
hol = True  # assume it is - the next step will change it if not
if 'No urn' in result:
    # this pod was not deployed by VLP = keys must be defined at top of this file
    hol = False
    log('\n\nThis pod was not deployed as a Hands On Lab')
    try:
        # test to see if public cloud keys are included at start of script
        msg = awsid
    except:
        log('\n\n* * * *   I M P O R T A N T   * * * * *\n')
        log('You must provide AWS and Azure key sets at the top of the "C:\\hol-2121-lab-files\\automation\\2121-base-config.py" script')
        log('Uncomment the keys, replace with your own and run the configuration script again')
        sys.exit()
else:
    vlp = result

# if this pod is running as a Hands On Lab
if hol:
    log('Pod is running in VLP')

    # find out if this pod already has credentials assigned
    credentials_used = check_for_assigned(vlp)
    if credentials_used:
        log('\n\n\nThis Hands On Lab pod already has credentials assigned')
        log('You do not need to run this script again')
        sys.exit()

    assigned_pod = get_available_pod()  # find an available credential set
    cred_set = assigned_pod[0]
    unreserved_count = assigned_pod[1]
    available_count = assigned_pod[2]
    keys = get_creds(cred_set, vlp)
    log(f'cred set: {cred_set}')
    awsid = keys['aws_access_key']
    awssec = keys['aws_secret_key']
    azsub = keys['azure_subscription_id']
    azten = keys['azure_tenant_id']
    azappkey = keys['azure_application_key']
    azappid = keys['azure_application_id']

    if available_count > 0:
        available_count = available_count-1

    # build and send Slack notification
    info = ""
    info += (f'*Credential set {cred_set} was assigned to the {vlp} VLP urn* \n')
    info += (f'- There are {available_count} sets remaining out of {unreserved_count} available \n')
    payload = {"text": info}
    send_slack_notification(payload)

log('\nPublic cloud credentials found. Configuring vRealize Automation\n')

log('Creating cloud accounts')
create_aws_ca()
create_azure_ca()

log('Tagging cloud zones')
c_zones_ids = get_czids()
aws_cz = tag_aws_cz(c_zones_ids)
azure_cz = tag_azure_cz(c_zones_ids)
vsphere_cz = tag_vsphere_cz(c_zones_ids)

log('Tagging vSphere workload clusters')
compute = get_computeids()
tag_vsphere_clusters(compute)

log('Creating projects')
hol_project = create_project(vsphere_cz, aws_cz, azure_cz)
create_labauto_project()
create_sd_project()
create_odyssey_project(vsphere_cz, aws_cz, azure_cz)

log('Creating GitHub blueprint repo integration')
gitId = add_github_integration()
configure_github(hol_project, gitId)

log('Waiting for git repo to sync')
time.sleep(20)

log('Update the vSphere networking')
networks = get_fabric_network_ids()
vm_net_id = update_networks(networks)
create_ip_pool()
vsphere_region_id = get_vsphere_region_id()
create_net_profile()

log('Create storage profiles')
datastore = get_vsphere_datastore_id()
create_storage_profile()

log('Updating flavor profiles')
create_azure_flavor()
create_aws_flavor()

log('Updating image profiles')
create_azure_image()
create_aws_image()

log('Configuring pricing')
pricing_card_id = get_pricing_card()
modify_pricing_card(pricing_card_id)
sync_price()

log('Adding blueprints to the catalog')
blueprint_id = get_blueprint_id('Ubuntu 18')
release_blueprint(blueprint_id, 1)
blueprint_id = get_blueprint_id('AWS Machine')
release_blueprint(blueprint_id, 1)
blueprint_id = get_blueprint_id('Azure Machine')
release_blueprint(blueprint_id, 1)
blueprint_id = get_blueprint_id('Count-vms')
release_blueprint(blueprint_id, 1)
bp_source = add_bp_cat_source(hol_project)
share_bps(bp_source, hol_project)

log('Adding Custom Resources and Actions')
org = getOrg(headers1)
endpoints = getEndpoints(headers1)
addCustomResource(headers1, endpoints['vro'],
                  'C:/hol-2121-lab-files/automation/resource-ad-user.json')
addResourceAction(
    headers1, endpoints['vro'], org, 'C:/hol-2121-lab-files/automation/resource-action-vmotion.json')

log('Creating the approval policy')
catalog_item = get_cat_id('Azure Machine')
create_approval_policy(catalog_item, hol_project)

log('Importing Code Stream pipelines')
create_cs_endpoint()
pipe_names = ['CS-Reset-Resources', 'CS-Base-Configuration', 'CS-Chat-App']
import_pipelines(pipe_names)
pipeIds = get_pipelines()
enable_pipelines(pipeIds)

##########################################
# API calls below as holuser
##########################################
access_key = get_token("holuser", "VMware1!")
headers1 = {'Content-Type': 'application/json',
            'Authorization': 'Bearer {0}'.format(access_key)}

time.sleep(90)
log('Deploying vSphere VM')
catalog_item = get_cat_id('Ubuntu 18')
deploy_cat_item(catalog_item, hol_project)

##########################################
# Configure GitLab Project
##########################################
log('Configuring GitLab')
git_proj_id = get_gitlab_projects()
update_git_proj(git_proj_id)
