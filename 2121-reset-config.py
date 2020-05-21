####### I M P O R T A N T #######
## If you are deploying this vPod dircetly in OneCloud and not through the Hands On Lab portal,
## you must uncomment the following lines and supply your own set of AWS and Azure keys
#################################
# awsid = "put your AWS access key here"
# awssec = "put your AWS secret hey here"
# azsub = "put your azure subscription id here"
# azten = "put your azure tenant id here"
# azappkey = "put your azure application key here"
# azappid = "put your azure application id here"
## also change the value below to True
local_creds = True

import json
import requests
import time
import os
import traceback
import boto3
from boto3.dynamodb.conditions import Key, Attr
from random import seed, randint
import datetime
import calendar
from time import strftime
import subprocess
import re
import sys
import urllib3
urllib3.disable_warnings()

##### Remove from final pod
awsid = os.getenv('temp_awsid')
awssec = os.getenv('temp_awssec')
azsub = os.getenv('temp_azsub')
azten = os.getenv('temp_azten')
azappkey = os.getenv('temp_azappkey')
azappid = os.getenv('temp_azappid')


if local_creds != True:
    d_id = os.getenv('D_ID')
    d_sec = os.getenv('D_SEC')
    d_reg = os.getenv('D_REG')
    

vra_fqdn = "vr-automation.corp.local"
api_url_base = "https://" + vra_fqdn + "/"
apiVersion = "2020-"

# set internet proxy for for communication out of the vPod
proxies = {
    "http": "http://192.168.110.1:3128",
    "https": "https://192.168.110.1:3128"
}

slack_api_key = os.getenv('SLACK_KEY')

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

    dynamodb = boto3.resource('dynamodb', aws_access_key_id=d_id, aws_secret_access_key=d_sec, region_name=d_reg)
    table = dynamodb.Table('HOL-keys')

    response = table.scan(
        FilterExpression=Attr('reserved').eq(0),
        ProjectionExpression="pod, in_use"
    )
    pods = response['Items']

    # the number of pods not reserved
    num_not_reserved = len(pods)

    available_pods = 0  #set counter to zero
    pod_array = []
    for i in pods:
        if i['in_use'] == 0:    #pod is available
            available_pods += 1 #increment counter
            pod_array.append(i['pod'])

    if available_pods == 0:     #no pod credentials are available
        return("T0", num_not_reserved, available_pods)
            
    #get random pod from those available
    dt = datetime.datetime.microsecond
    seed(dt)
    rand_int = randint(0,available_pods-1)
    pod = pod_array[rand_int]

    return(pod, num_not_reserved, available_pods)

def get_creds(cred_set,vlp_urn_id):

    dynamodb = boto3.resource('dynamodb', aws_access_key_id=d_id, aws_secret_access_key=d_sec, region_name=d_reg)
    table = dynamodb.Table('HOL-keys')

    a = time.gmtime()   #gmt in structured format
    epoch_time = calendar.timegm(a)     #convert to epoc
    human_time = strftime("%m-%d-%Y %H:%M", a)

    #get the key set
    response = table.get_item(
        Key={
            'pod': cred_set
        }
    )
    results = response['Item']

    #write some items
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

def get_token(user_name,pass_word):
    api_url = '{0}csp/gateway/am/api/login?access_token'.format(api_url_base)
    data =  {
              "username": user_name,
              "password": pass_word
            }
    response = requests.post(api_url, headers=headers, data=json.dumps(data), verify=False)
    if response.status_code == 200:
        json_data = json.loads(response.content.decode('utf-8'))
        key = json_data['access_token']
        return key
    else:
        return('not ready')

def vra_ready():  # this is a proxy to test whether vRA is ready or not since the deployments service is one of the last to come up
    api_url = '{0}deployment/api/deployments'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = json.loads(response.content.decode('utf-8'))
        deployments = extract_values(json_data,'id')
        ready = True
    else:
        ready = False
    return(ready)

def get_vsphere_regions():
    api_url = '{0}iaas/api/cloud-accounts-vsphere/region-enumeration'.format(api_url_base)
    data =  {
                "hostName": "vcsa-01a.corp.local",
                "acceptSelfSignedCertificate": "true",
                "password": "VMware1!",
                "name": "vSphere Cloud Account",
                "description": "vSphere Cloud Account",
                "username": "administrator@corp.local"
            }
    response = requests.post(api_url, headers=headers1, data=json.dumps(data), verify=False)
    if response.status_code == 200:
        json_data = json.loads(response.content.decode('utf-8'))
        regions = json_data["externalRegionIds"]
        print('- Successfully got vSphere Datacenters')
        return(regions)
    else:
        print('- Failed to get vSphere Datacenters')
        return None


def create_vsphere_ca(region_ids):
    api_url = '{0}iaas/api/cloud-accounts-vsphere'.format(api_url_base)
    data =  {
                "hostName": "vcsa-01a.corp.local",
                "acceptSelfSignedCertificate": "true",
                "password": "VMware1!",
                "createDefaultZones" : "true",
                "name": "Private Cloud",
                "description": "vSphere Cloud Account",
                "regionIds": region_ids,
                "username": "administrator@corp.local",
                "tags": [
                        ]              
            }
    response = requests.post(api_url, headers=headers1, data=json.dumps(data), verify=False)
    if response.status_code == 201:
        json_data = json.loads(response.content.decode('utf-8'))
        print('- Successfully Created vSphere Cloud Account')
    else:
        print('- Failed to Create the vSphere Cloud Account')
        return None


def create_aws_ca():
    api_url = '{0}iaas/api/cloud-accounts-aws'.format(api_url_base)
    data =  {
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
                "createDefaultZones" : "true",
                "name": "AWS Cloud Account"
            }
    response = requests.post(api_url, headers=headers1, data=json.dumps(data), verify=False)
    if response.status_code == 201:
        json_data = json.loads(response.content.decode('utf-8'))
        print('- Successfully Created AWS Cloud Account')
    else:
        print('- Failed to Create the AWS Cloud Account')
        return None

def create_azure_ca():
    api_url = '{0}iaas/api/cloud-accounts-azure'.format(api_url_base)
    data =  {
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
    response = requests.post(api_url, headers=headers1, data=json.dumps(data), verify=False)
    if response.status_code == 201:
        json_data = json.loads(response.content.decode('utf-8'))
        print('- Successfully Created Azure Cloud Account')
    else:
        print('- Failed to create the Azure Cloud Account')
        return None

def get_czids():
    api_url = '{0}iaas/api/zones'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = json.loads(response.content.decode('utf-8'))
        cz_id = extract_values(json_data,'id')
        return cz_id
    else:
        print('- Failed to get the cloud zone IDs')
        return None

def get_right_czid_vsphere(czid):
    api_url = '{0}iaas/api/zones/{1}'.format(api_url_base,czid)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = json.loads(response.content.decode('utf-8'))
        cz_name = extract_values(json_data,'name')
        for x in cz_name:
            if 'RegionA01' in x:        # Looking for the CZ for vSphere
                return czid
    else:
        print('- Failed to get the right vSphere cloud zone ID')
        return None

def get_right_czid_aws(czid):
    api_url = '{0}iaas/api/zones/{1}'.format(api_url_base,czid)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = json.loads(response.content.decode('utf-8'))
        cz_name = extract_values(json_data,'name')
        for x in cz_name:
            if x == 'AWS Cloud Account / us-west-1':
                return czid
    else:
        print('- Failed to get the right AWS cloud zone ID')
        return None

def get_right_czid_azure(czid):
    api_url = '{0}iaas/api/zones/{1}'.format(api_url_base,czid)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = json.loads(response.content.decode('utf-8'))
        cz_name = extract_values(json_data,'name')
        for x in cz_name:
            if x == 'Azure Cloud Account / westus':
                return czid
    else:
        print('- Failed to get Azure cloud zone ID')
        return None

def get_czid_aws(czid):
    for x in czid:
        api_url = '{0}iaas/api/zones/{1}'.format(api_url_base,x)
        response = requests.get(api_url, headers=headers1, verify=False)
        if response.status_code == 200:
            json_data = json.loads(response.content.decode('utf-8'))
            cz_name = extract_values(json_data,'name')
            cz_name = cz_name[0]
            if cz_name == 'AWS-West-1 / us-west-1':
                return x
        else:
            print('- Failed to get the AWS cloud zone ID')
            return None

def get_projids():
    api_url = '{0}iaas/api/projects'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = json.loads(response.content.decode('utf-8'))
        proj_id = extract_values(json_data,'id')
        return proj_id
    else:
        print('- Failed to get the project IDs')
        return None

def get_right_projid(projid):
    api_url = '{0}iaas/api/projects/{1}'.format(api_url_base,projid)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = json.loads(response.content.decode('utf-8'))
        proj_name = extract_values(json_data,'name')
        for x in proj_name:
            if x == 'HOL Project':
                return projid
    else:
        print('- Failed to get the right project ID')
        return None

def get_right_projid_rp(projid):
    api_url = '{0}iaas/api/projects/{1}'.format(api_url_base,projid)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = json.loads(response.content.decode('utf-8'))
        proj_name = extract_values(json_data,'name')
        for x in proj_name:
            if x == 'Rainpole Project':
                return projid
    else:
        print('- Failed to get the right project ID')
        return None

def create_project(vsphere,aws,azure):
    api_url = '{0}iaas/api/projects'.format(api_url_base)
    data =  {
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
                "machineNamingTemplate": "${project.name}-${resource.image}-${###}",
                "sharedResources": "true"
            }
    response = requests.post(api_url, headers=headers1, data=json.dumps(data), verify=False)
    if response.status_code == 201:
        json_data = json.loads(response.content.decode('utf-8'))
        print('- Successfully created HOL Project')
    else:
        print('- Failed to create HOL Project')


def update_project(proj_Ids,vsphere,aws,azure):
    if proj_Ids is not None:
        for x in proj_Ids:
            project_id = get_right_projid(x)
            if project_id is not None:
                api_url = '{0}iaas/api/projects/{1}'.format(api_url_base,project_id)
                data =  {
                    "name": "HOL Project",
                    "machineNamingTemplate": "${resource.name}-${###}",
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
                    "sharedResources": "true"
                }
                response = requests.patch(api_url, headers=headers1, data=json.dumps(data), verify=False)
                if response.status_code == 200:
                    json_data = json.loads(response.content.decode('utf-8'))
                    print('- Successfully added cloud zones to HOL Project')
                    return project_id
                else:
                    print('- Failed to add cloud zones to HOL Project')
    

def update_project_rp(proj_Ids,vsphere,aws,azure):
    if proj_Ids is not None:
        for x in proj_Ids:
            project_id = get_right_projid_rp(x)
            if project_id is not None:
                api_url = '{0}iaas/api/projects/{1}'.format(api_url_base,project_id)
                data =  {
                            "name": "Rainpole Project",
                        	"zoneAssignmentConfigurations": [
                                        {
                                            "zoneId": vsphere,
                                            "maxNumberInstances": 20,
                                            "priority": 1
                                        },
                                        {
                                            "zoneId": aws,
                                            "maxNumberInstances": 10,
                                            "priority": 1
                                        }
                                    ]
                        }
                response = requests.patch(api_url, headers=headers1, data=json.dumps(data), verify=False)
                if response.status_code == 200:
                    json_data = json.loads(response.content.decode('utf-8'))
                    print('- Successfully added cloud zones to Rainpole project')
                else:
                    print('- Failed to add cloud zones to Rainpole project')
                    return None


def tag_vsphere_cz(cz_Ids):
    if cz_Ids is not None:
        for x in cz_Ids:
            cloudzone_id = get_right_czid_vsphere(x)
            if cloudzone_id is not None:
                api_url = '{0}iaas/api/zones/{1}'.format(api_url_base,cloudzone_id)
                data =  {
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
                response = requests.patch(api_url, headers=headers1, data=json.dumps(data), verify=False)
                if response.status_code == 200:
                    print('- Successfully Tagged vSphere Cloud Zone')
                    return(cloudzone_id)
                else:
                    print('- Failed to tag vSphere cloud zone')
                    return None
    else:
        print('- Failed to tag vSphere cloud zone')
        return None

def tag_aws_cz(cz_Ids):
    if cz_Ids is not None:
        for x in cz_Ids:
            cloudzone_id = get_right_czid_aws(x)
            if cloudzone_id is not None:
                api_url = '{0}iaas/api/zones/{1}'.format(api_url_base,cloudzone_id)
                data =  {
                            "name": "AWS / us-west-1",
                        	"tags": [
                                        {
                                            "key": "cloud",
                                            "value": "aws"
                                        }
                                    ]
                        }
                response = requests.patch(api_url, headers=headers1, data=json.dumps(data), verify=False)
                if response.status_code == 200:
                    json_data = json.loads(response.content.decode('utf-8'))
                    print('- Successfully Tagged AWS cloud zone')
                    return cloudzone_id
                else:
                    print('- Failed to tag AWS cloud zone - bad response code')
                    return None
    else:
        print('- Failed to tag AWS cloud zone')
        return None



def tag_azure_cz(cz_Ids):
    if cz_Ids is not None:
        for x in cz_Ids:
            cloudzone_id = get_right_czid_azure(x)
            if cloudzone_id is not None:
                api_url = '{0}iaas/api/zones/{1}'.format(api_url_base,cloudzone_id)
                data =  {
                            "name": "Azure / West US",
                        	"tags": [
                                        {
                                            "key": "cloud",
                                            "value": "azure"
                                        }
                                    ]
                        }
                response = requests.patch(api_url, headers=headers1, data=json.dumps(data), verify=False)
                if response.status_code == 200:
                    json_data = json.loads(response.content.decode('utf-8'))
                    print('- Successfully tagged Azure cloud zone')
                    return cloudzone_id
                else:
                    print('- Failed to tag Azure cloud zone')
                    return None
    else:
        print('- Failed to tag Azure cloud zone')
        return None


def get_azure_regionid():
    api_url = '{0}iaas/api/regions'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = json.loads(response.content.decode('utf-8'))
        region_id = extract_values(json_data,'id')
        for x in region_id:
            api_url2 = '{0}iaas/api/regions/{1}'.format(api_url_base,x)
            response2 = requests.get(api_url2, headers=headers1, verify=False)
            if response2.status_code == 200:
                json_data2 = json.loads(response2.content.decode('utf-8'))
                region_name = extract_values(json_data2,'externalRegionId')
                compare = region_name[0]
                if compare == 'westus':
                    region_id = extract_values(json_data2,'id')
                    return region_id
    else:
        print('- Failed to get Azure region ID')
        return None

def create_azure_flavor():
    azure_id = get_azure_regionid()
    azure_id = azure_id[0]
    api_url = '{0}iaas/api/flavor-profiles'.format(api_url_base)
    data =  {
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
    response = requests.post(api_url, headers=headers1, data=json.dumps(data), verify=False)
    if response.status_code == 201:
        json_data = json.loads(response.content.decode('utf-8'))
        print('- Successfully created Azure flavor mapping')
    else:
        print('- Failed to create Azure flavor mapping')
        return None

def get_aws_regionid():
    api_url = '{0}iaas/api/regions'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = json.loads(response.content.decode('utf-8'))
        region_id = extract_values(json_data,'id')
        for x in region_id:
            api_url2 = '{0}iaas/api/regions/{1}'.format(api_url_base,x)
            response2 = requests.get(api_url2, headers=headers1, verify=False)
            if response2.status_code == 200:
                json_data2 = json.loads(response2.content.decode('utf-8'))
                region_name = extract_values(json_data2,'externalRegionId')
                compare = region_name[0]
                if compare == 'us-west-1':
                    aws_region_id = extract_values(json_data2,'id')
                    return aws_region_id
    else:
        print('- Failed to get AWS region')
        return None

def create_aws_flavor():
        aws_id = get_aws_regionid()
        aws_id = aws_id[0]
        api_url = '{0}iaas/api/flavor-profiles'.format(api_url_base)
        data =  {
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
        response = requests.post(api_url, headers=headers1, data=json.dumps(data), verify=False)
        if response.status_code == 201:
            json_data = json.loads(response.content.decode('utf-8'))
            print('- Successfully created AWS flavors')
        else:
            print('- Failed to created AWS flavors')
            return None


def create_aws_image():
        aws_id = get_aws_regionid()
        aws_id = aws_id[0]
        api_url = '{0}iaas/api/image-profiles'.format(api_url_base)
        data =  {
                  "name" : "aws-image-profile",
                  "description": "Image Profile for AWS Images",
                  "imageMapping" : {
                    "CentOS7": {
                        "name": "ami-a83d0cc8"
                    },
                    "Ubuntu18": {
                        "name": "hol-ubuntu16-apache"
                    }
                  },
                  "regionId": aws_id
                }
        response = requests.post(api_url, headers=headers1, data=json.dumps(data), verify=False)
        if response.status_code == 201:
            json_data = json.loads(response.content.decode('utf-8'))
            print('- Successfully created AWS images')
        else:
            print('- Failed to created AWS images')
            return None


def create_azure_image():
        azure_id = get_azure_regionid()
        azure_id = azure_id[0]
        api_url = '{0}iaas/api/image-profiles'.format(api_url_base)
        data =  {
                  "name" : "azure-image-profile",
                  "description": "Image Profile for Azure Images",
                  "imageMapping" : {
                    "Ubuntu18": {
                        "name": "Canonical:UbuntuServer:18.04-LTS:latest"
                    },
                    "CentOS7": {
                        "name": "OpenLogic:CentOS:7.4:7.4.20180704"
                    }
                  },
                  "regionId": azure_id
                }
        response = requests.post(api_url, headers=headers1, data=json.dumps(data), verify=False)
        if response.status_code == 201:
            json_data = json.loads(response.content.decode('utf-8'))
            print('- Successfully created Azure images')
        else:
            print('- Failed to created Azure images')
            return None

def get_computeids():
    api_url = '{0}iaas/api/fabric-computes'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = json.loads(response.content.decode('utf-8'))
        comp_id = extract_values(json_data,'id')
    return(comp_id)


def tag_vsphere_clusters(computes):
    for x in computes:
        api_url = '{0}iaas/api/fabric-computes/{1}'.format(api_url_base,x)
        response = requests.get(api_url, headers=headers1, verify=False)
        if response.status_code == 200:
            json_data = json.loads(response.content.decode('utf-8'))
            cluster = extract_values(json_data,'name')
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
                response1 = requests.patch(api_url, headers=headers1, data=json.dumps(data), verify=False)
                if response1.status_code == 200:
                    print("- Tagged", cluster[0], "cluster")
                else:
                    print("- Failed to tag", cluster[0], "cluster")

        else:
            print('Failed to tag vSphere workload clusters')
    return None


def get_fabric_network_ids():
    api_url = '{0}iaas/api/fabric-networks-vsphere'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = json.loads(response.content.decode('utf-8'))
        net_ids = extract_values(json_data,'id')
    return(net_ids)


def update_networks(net_ids):
    for x in net_ids:
        api_url = '{0}iaas/api/fabric-networks-vsphere/{1}'.format(api_url_base,x)
        response = requests.get(api_url, headers=headers1, verify=False)
        if response.status_code == 200:
            json_data = json.loads(response.content.decode('utf-8'))
            network = extract_values(json_data,'name')
            if "VM-Region" in network[0]:
                ## This is the vSphere VM network - update it ##
                data = {
                            "isDefault": "true",
                            "domain": "corp.local",
                            "defaultGateway": "192.168.120.1",
                            "dnsServerAddresses": ["192.168.110.10"],
                            "cidr": "192.168.120.0/24",
                            "dnsSearchDomains": ["corp.local"],
                            "tags": [
                                        {
                                            "key": "net",
                                            "value": "vsphere"
                                        }
                                    ]
                        }
                response1 = requests.patch(api_url, headers=headers1, data=json.dumps(data), verify=False)
                if response1.status_code == 200:
                    print("- Updated the", network[0], "network")
                    return(x)
                else:
                    print("- Failed to update", network[0], "network")
                    return None

        else:
            print('Failed to get vSphere networks')
    return None


def create_ip_pool():
    api_url = '{0}iaas/api/network-ip-ranges'.format(api_url_base)
    data =  {
                "ipVersion": "IPv4",
                "fabricNetworkId": vm_net_id,
                "name": "vSphere Static Pool",
                "description": "For static IP assignment to deployed VMs",
                "startIPAddress" : "192.168.120.2",
                "endIPAddress": "192.168.120.30"           
            }
    response = requests.post(api_url, headers=headers1, data=json.dumps(data), verify=False)
    if response.status_code == 201:
        json_data = json.loads(response.content.decode('utf-8'))
        print('- Successfully created the IP pool')
    else:
        print('- Failed to create the IP pool')
    return None


def get_vsphere_region_id():
    api_url = '{0}iaas/api/regions'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = json.loads(response.content.decode('utf-8'))
        content = json_data["content"]
        count = json_data["totalElements"]
        for x in range(count):
            if 'RegionA01' in content[x]["name"]:              ## Looking to match the vSphere datacenter name
                vsphere_id = (content[x]["id"])
                return vsphere_id
    else:
        print('- Failed to get the vSphere region (datacenter) ID')
        return None


def create_net_profile():
    api_url = '{0}iaas/api/network-profiles'.format(api_url_base)
    data =  {
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
    response = requests.post(api_url, headers=headers1, data=json.dumps(data), verify=False)
    if response.status_code == 201:
        print('- Successfully created the network profile')
    else:
        print('- Failed to create the network profile')
        return None


def get_vsphere_datastore_id():
    api_url = '{0}iaas/api/fabric-vsphere-datastores'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = json.loads(response.content.decode('utf-8'))
        content = json_data["content"]
        count = json_data["totalElements"]
        for x in range(count):
            if 'ISCSI01' in content[x]["name"]:         ## Looking to match the right datastore name
                vsphere_ds = (content[x]["id"])
                return vsphere_ds
    else:
        print('- Failed to get the vSphere datastore ID')
        return None


def create_storage_profile():
    api_url = '{0}iaas/api/storage-profiles-vsphere'.format(api_url_base)
    data =  {
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
    response = requests.post(api_url, headers=headers1, data=json.dumps(data), verify=False)
    if response.status_code == 201:
        print('- Successfully created the storage profile')
    else:
        print('- Failed to create the storage profile')
        return None

def get_pricing_card():
    api_url = '{0}price/api/private/pricing-cards'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = json.loads(response.content.decode('utf-8'))
        content = json_data["content"]
        count = json_data["totalElements"]
        for x in range(count):
            if 'Default Pricing' in content[x]["name"]:       ## Looking to match the Default pricing card
                id = (content[x]["id"])
                return id
    else:
        print('- Failed to get default pricing card')
        return None


def modify_pricing_card(cardid):
    # modifies the Default Pricing card
    api_url = '{0}price/api/private/pricing-cards/{1}'.format(api_url_base, cardid)
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
                    "baseRate": 18,
                    "chargePeriod": "MONTHLY",
                    "chargeOnPowerState": "ALWAYS",
                    "chargeBasedOn": "USAGE",
                    "unit": "gb"
                },
            },
            {
                "itemName": "storage",
                "metering": {
                    "baseRate": 0.13,
                    "chargePeriod": "MONTHLY",
                    "chargeOnPowerState": "ALWAYS",
                    "chargeBasedOn": "USAGE",
                    "unit": "gb"
                }
            }
        ],
        "chargeModel": "PAY_AS_YOU_GO"
    }
    response = requests.put(api_url, headers=headers1, data=json.dumps(data), verify=False)
    if response.status_code == 200:
        print('- Successfully modified the pricing card')
    else:
        print('- Failed to modify the pricing card')

def get_blueprint_id(bpName):
    api_url = '{0}blueprint/api/blueprints'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = json.loads(response.content.decode('utf-8'))
        content = json_data["content"]
        count = json_data["totalElements"]
        for x in range(count):
            if bpName in content[x]["name"]:       ## Looking to match the blueprint name
                bp_id = (content[x]["id"])
                return bp_id
    else:
        print('- Failed to get the blueprint ID for', bpName)
        return None


def release_blueprint(bpid,ver):
    api_url = '{0}blueprint/api/blueprints/{1}/versions/{2}/actions/release'.format(api_url_base, bpid, ver)
    data = {}
    response = requests.post(api_url, headers=headers1, data=json.dumps(data), verify=False)
    if response.status_code == 200:
        print('- Successfully released the blueprint')
    else:
        print('- Failed to releasea the blueprint')


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
    response = requests.post(api_url, headers=headers1, data=json.dumps(data), verify=False)
    if response.status_code == 201:
        json_data = json.loads(response.content.decode('utf-8'))
        itemsFound = json_data["itemsFound"]
        itemsImported = json_data["itemsImported"]
        sourceId = json_data["id"]
        print('- Successfully added blueprints as a catalog source')
        return sourceId
    else:
        print('- Failed to add blueprints as a catalog source')
        return None

def share_bps(source, project):
    # shares blueprint content (source) from 'projid' project to the catalog
    api_url = '{0}catalog/api/admin/entitlements'.format(api_url_base)
    data = {
        "definition": {"type": "CatalogSourceIdentifier", "id": source},
        "projectId": project
    }
    response = requests.post(api_url, headers=headers1, data=json.dumps(data), verify=False)
    if response.status_code == 201:
        print('- Successfully added blueprint catalog entitlement')
    else:
        print('- Failed to add blueprint catalog entitlement')
        return None

def get_cat_id():
    api_url = '{0}catalog/api/items'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = json.loads(response.content.decode('utf-8'))
        content = json_data["content"]
        count = json_data["totalElements"]
        for x in range(count):
            if 'Ubuntu 18' in content[x]["name"]:       ## Looking to match the Ubuntu 18 blueprint catalog item
                cat_id = (content[x]["id"])
                return cat_id
    else:
        print('- Failed to get the blueprint ID')
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
    response = requests.post(api_url, headers=headers1, data=json.dumps(data), verify=False)
    if response.status_code == 200:
        print('- Successfully deployed the catalog item')
    else:
        print('- Failed to deploy the catalog item')

 



def get_deployments():
    # returns an array containing all of the deployment ids
    api_url = '{0}deployment/api/deployments'.format(api_url_base)
    response = requests.get(api_url, headers=headers1, verify=False)
    if response.status_code == 200:
        json_data = json.loads(response.content.decode('utf-8'))
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
        json_data = json.loads(response.content.decode('utf-8'))
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
        print('- Successfully removed configuration from HOL Project')
    else:
        print('- Failed to remove configuration from HOL Project')

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
            print('- Failed to delte the GitHub integration')

    

def delete_project(proj_Id):
    api_url = '{0}iaas/api/projects/{1}'.format(api_url_base,proj_Id)
    data =  {}
    response = requests.delete(api_url, headers=headers1, data=json.dumps(data), verify=False)
    if response.status_code == 204:
        print('- Successfully deleted the HOL Project')
    else:
        print('- Failed to delte the HOL Project')

##### MAIN #####

headers = {'Content-Type': 'application/json'}

###########################################  
## API calls below as admin
###########################################  
access_key = get_token("admin","VMware1!")
headers1 = {'Content-Type': 'application/json',
           'Authorization': 'Bearer {0}'.format(access_key)}


print('Deleting deployments')
deploymentIds = get_deployments()
delete_deployments(deploymentIds)

print('Removing cloud zones from the HOL Project')
hol_project = get_holproj()
unconfigure_project(hol_project)
unconfigure_github()
delete_project(hol_project)


sys.exit()

####


print('Tagging cloud zones')
c_zones_ids = get_czids()
aws_cz = tag_aws_cz(c_zones_ids)
azure_cz = tag_azure_cz(c_zones_ids)
vsphere_cz = tag_vsphere_cz(c_zones_ids)  

print('Tagging vSphere workload clusters')
compute = get_computeids()
tag_vsphere_clusters(compute)

#create_project(vsphere_cz,aws_cz,azure_cz)
print('Udating projects')
project_ids = get_projids()
hol_project = update_project(project_ids,vsphere_cz,aws_cz,azure_cz)
#update_project_rp(project_ids,vsphere_cz,aws_cz,azure_cz)

print('Update the vSphere networking')
networks = get_fabric_network_ids()
vm_net_id = update_networks(networks)
create_ip_pool()
vsphere_region_id = get_vsphere_region_id()
create_net_profile()

print('Create storage profiles')
datastore = get_vsphere_datastore_id()
create_storage_profile()

print('Updating flavor profiles')
create_azure_flavor()
create_aws_flavor()

print('Updating image profiles')
create_azure_image()
create_aws_image()

print('Configuring pricing')
pricing_card_id = get_pricing_card()
modify_pricing_card(pricing_card_id)

print('Adding blueprint to the catalog')
blueprint_id = get_blueprint_id('Ubuntu 18')
release_blueprint(blueprint_id, 1)
blueprint_id = get_blueprint_id('MOAD-Retail-LB')
release_blueprint(blueprint_id, 1)
bp_source = add_bp_cat_source(hol_project)
share_bps(bp_source,hol_project)


###########################################  
## API calls below as holuser
###########################################  

access_key = get_token("holuser","VMware1!")
headers1 = {'Content-Type': 'application/json',
           'Authorization': 'Bearer {0}'.format(access_key)}


print('Deploying vSphere VM')
catalog_item = get_cat_id()
deploy_cat_item(catalog_item, hol_project)
