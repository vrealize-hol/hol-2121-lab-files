#   Python Validation Script Template
#   Using the unittest framework we define a series of tests representing
#   whatever we need to check to validate that the task was completed.   
#   All tests must pass for the test framework to return success.
import unittest
import urllib3
import sys
import re
import subprocess
from time import strftime
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
import yaml
from deepdiff import DeepDiff
urllib3.disable_warnings()

vra_fqdn = "vr-automation.corp.local"
vra_addr = "https://"+vra_fqdn
username="vcapadmin"
password="VMware1!"

headers = {'Content-Type': 'application/json'}

task1BPFile = r"C:\\hol-2121-lab-files\\Automation\\test\\Task1-HOL_Simple_Blueprint.yaml"
task2BPFile = r"C:\\hol-2121-lab-files\\Automation\\test\\Task2-HOL_Simple_Blueprint.yaml"


def get_token(user_name, pass_word):
    api_uri = '{0}/csp/gateway/am/api/login?access_token'.format(vra_addr)
    print(api_uri)
    data = {
        "username": user_name,
        "password": pass_word
    }
    response = requests.post(api_uri, headers=headers,
                             data=json.dumps(data), verify=False)
    if response.status_code == 200:
        json_data = response.json()
        key = json_data['access_token']
        return key
    else:
        return(response.status_code)

def get_blueprint_id(bpName, headers):
    api_uri = '{0}/blueprint/api/blueprints'.format(vra_addr)
    response = requests.get(api_uri, headers=headers, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        count = json_data["totalElements"]
        for x in range(count):
            if bpName.lower() in content[x]["name"].lower():  # Looking to match the blueprint name
                bp_id = (content[x]["id"])
                return bp_id
    else:
        print('- Failed to get the blueprint ID for ' + bpName)
        return None
def get_blueprint_version(bpId, version, headers):
    api_uri = '{0}/blueprint/api/blueprints/{1}/versions'.format(vra_addr, bpId)
    response = requests.get(api_uri, headers=headers, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        count = json_data["totalElements"]
        for x in range(count):
            if version.lower() in content[x]["version"].lower():  # Looking to match the version name
                matchedVersion = content[x]["version"]
                return matchedVersion
    else:
        print('- Failed to get the blueprint version for ' + bpId)
        return None
def get_blueprint_content(bpName, headers):
    bp_id = get_blueprint_id(bpName, headers)
    if bp_id is not None:
        api_uri = '{0}/blueprint/api/blueprints/{1}'.format(vra_addr, bp_id)
        response = requests.get(api_uri, headers=headers, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        return json_data["content"]
    else:
        print('- Failed to get the blueprint content for ' + bpName)
        return None
def get_version_status(bpName, version, headers):
    bp_id = get_blueprint_id(bpName, headers)
    if bp_id is not None:
        api_uri = '{0}/blueprint/api/blueprints/{1}/versions/{2}'.format(vra_addr, bp_id, version)
        response = requests.get(api_uri, headers=headers, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        return json_data["status"]
    else:
        print('- Failed to get the blueprint version status for ' + bpName)
        return None
def get_contentsource_id(contentSrcName, headers):
    projectId = ""
    api_uri = '{0}/catalog/api/admin/sources'.format(vra_addr)
    response = requests.get(api_uri, headers=headers, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        count = json_data["totalElements"]
        for x in range(count):
            if content[x]["typeId"] == "com.vmw.blueprint":
                projectId = content[x]["projectId"]
            if contentSrcName.lower() in content[x]["name"].lower():  
                cSrc_id = (content[x]["id"])
                return cSrc_id, projectId;
    else:
        print('- Failed to get the content source ID for ' + contentSrcName)
        return None, None;
def find_wf_contentsource(contentSrcName, workflowName, headers):
    contentSrc_id, prj_id = get_contentsource_id(contentSrcName, headers)
    api_uri = '{0}/catalog/api/admin/sources/{1}'.format(vra_addr, contentSrc_id)
    response = requests.get(api_uri, headers=headers, verify=False)
    result = False
    if response.status_code == 200:
        json_data = response.json()
        if json_data['typeId'] == "com.vmw.vro.workflow":
            workflows = json_data["config"]["workflows"]
            count = len(json_data["config"]["workflows"])
            for x in range(count):
                if workflowName in workflows[x]["name"]:  
                    result= True
                    return result
    else:
        print('- Failed to get the content source ID for ' + contentSrcName)
        return False
def get_project_id(projectName, headers):
    api_uri = '{0}/iaas/api/projects'.format(vra_addr)
    response = requests.get(api_uri, headers=headers, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        count = json_data["totalElements"]
        for x in range(count):
            if projectName.lower() in content[x]["name"].lower():  
                prj_id = (content[x]["id"])
                return prj_id
    else:
        print('- Failed to get the project ID for ' + projectName)
        return None
def get_entitlement(projectName, contentSrcName, headers):
    prj_id = get_project_id(projectName, headers)
    api_uri = '{0}/catalog/api/admin/entitlements?projectId={1}'.format(vra_addr, prj_id)
    response = requests.get(api_uri, headers=headers, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        content = json_data
        count = len(json_data)
        for x in range(count):
            if contentSrcName.lower() in content[x]["definition"]["name"].lower():
                entitlement_id = (content[x]["id"])
                return entitlement_id
    else:
        print('- Failed to get the entitlement ID for ' + projectName)
        return None
def get_subscription_id(subscriptionName, headers):
    api_uri = "{0}/event-broker/api/subscriptions?$filter=type%20eq%20%27RUNNABLE%27".format(vra_addr)
    response = requests.get(api_uri, headers=headers, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        count = json_data["numberOfElements"]
        for x in range(count):
            if subscriptionName.lower() in content[x]["name"].lower():
                subscription_id = content[x]["id"]
                return subscription_id
    else:
        print('- Failed to get the subscription ID for ' + subscriptionName)
        return None
def get_subscription(subscriptionName, headers):
    subscriptionId = get_subscription_id(subscriptionName, headers)
    api_uri = "{0}/event-broker/api/subscriptions/{1}".format(vra_addr, subscriptionId)
    response = requests.get(api_uri, headers=headers, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        return json_data
    else:
        print('- Failed to get the subscription ID for ' + subscriptionName)
        return None
def get_workflow_id(workflowName, headers):
    api_uri = "{0}/vco/api/workflows?maxResult=2147483647&queryCount=false&conditions=name%3D{1}".format(vra_addr, workflowName)
    response =  requests.get(api_uri, headers=headers, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        wf_attrs = json_data['link'][0]['attributes']
        count = len(wf_attrs)
        for x in range(count):
            if wf_attrs[x]['name'] == '@id':
                return wf_attrs[x]['value']
    else:
        print('- Failed to get the workflow ID for ' + workflowName)
        return None
def get_day2policy_id(policyName, headers):
    api_uri = '{0}/policy/api/policies'.format(vra_addr)
    response = requests.get(api_uri, headers=headers, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        count = json_data["totalElements"]
        for x in range(count):
            if policyName.lower() in content[x]["name"].lower():  
                policy_id = (content[x]["id"])
                return policy_id
    else:
        print('- Failed to get the Day2 Action Policy ID for ' + policyName)
        return None
def get_day2policy(policyName, headers):
    policy_id = get_day2policy_id(policyName, headers)
    api_uri = '{0}/policy/api/policies/{1}'.format(vra_addr, policy_id)
    response = requests.get(api_uri, headers=headers, verify=False)
    if response.status_code == 200:
        return response.json()
    else:
        print('- Failed to fetch details for Day2 Policy Action ' + policyName)
        return None
def get_czid(czName, headers):
    api_uri = '{0}/iaas/api/zones'.format(vra_addr)
    response = requests.get(api_uri, headers=headers, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        cz_id = extract_values(json_data, 'id')
        return cz_id
    else:
        log('- Failed to get the cloud zone IDs')
        return None
class OdysseyTestCases(unittest.TestCase):

    #   the setUp function is executed before any tests
    def setUp(self):
        access_key = get_token(username, password)
        if access_key == 401 or access_key == 400:
            print("Cannot authenticate. Check credentials.")
            sys.exit(1)
        self.headers1 = {'Content-Type': 'application/json',
            'Authorization': 'Bearer {0}'.format(access_key)}
        self.headers2 = {'Content-Type': 'application/x-yaml',
            'Authorization': 'Bearer {0}'.format(access_key)}
        
        self.Task1_Blueprint_Name = "Hol Simple Blueprint"
        self.Task1_Blueprint_Version = "Task1"
        self.Task1BlueprintExistsBool = True
        self.Task1BlueprintMachineExistsBool = True
        self.Task2_Blueprint_Name = "Hol Simple Blueprint"
        self.Task2_Blueprint_Version = "Task2"
        self.Task2BlueprintInputExistsBool = True
        self.Task2BlueprintMachineExistsBool = True
        self.Task3_Blueprint_Name = "Tito Cloud Agnostic"
        self.Task3_Blueprint_Version = "Task3"
        self.Task3_Content_Source = "Task3"
        self.Task3_Version_Status = "RELEASED"
        self.Task3BlueprintExistsBool = True
        self.Task3ContentSrcExistsBool = True
        self.Task3EntitlementExistsBool = True
        self.Task4_Subscription_Name = "Task4"
        self.Task4SubscriptionExistsBool = True
        self.Task4EventTopicId = "compute.provision.pre"
        self.Task4Blocking = True
        self.Task4Criteria = "event.data.blueprintId == "
        self.Task4RunnableType = "extensibility.vro"
        self.Task4WorkflowName = "Logging"
        self.Task5_Content_Source = "Task5"
        self.Task5WorkflowName = "Create a user in an organizational unit"
        self.Task5ContentSrcExistsBool = True
        self.Task5EntitlementExistsBool = True
        self.Task6_Day2Policy_name = "Task6"
        self.Task6PolicyExistsBool = True
        self.Task6criteriaDict = {
            "matchExpression" : [
                {
                    "and" : [
                        {
                            "key" : "blueprintId",
                            "operator" : "eq",
                            "value" : ""
                        } ,
                        {
                            "key" : "createdBy",
                            "operator" : "notEq",
                            "value" : "holuser@corp.local"
                        }
                    ]
                }
            ]
        }
        self.Task6CriteriaMatchesBool = True
        self.Task6TypeId = "com.vmware.policy.deployment.action"
        self.Task6AllowedActions = ["Cloud.Machine.Resize", "Cloud.Machine.Delete"]
        self.Task6Authorities = "administrator"
        self.Task6ActionsMatchBool = True
        self.correct_project = "Odyssey Project"
        self.correct_machineresource_name = "HOL_Machine1"
        self.correct_imagemapping_name = "Ubuntu18"
        self.correct_flavormapping_name = "small"
    



    #   tests are defined as a function beginning with the word "test" 
    #   tests are executed in order of alpha-numeric sort based on the name (yeah...)
    #TASK1
    def testTask1SimpleBlueprintContents1(self):
    
        # Check if blueprint exists
        blueprintExists = True

        bp_id = get_blueprint_id(self.Task1_Blueprint_Name, self.headers1)
        if bp_id is None:
            blueprintExists = False
        
        self.assertEqual(blueprintExists, self.Task1BlueprintExistsBool, "Task1 blueprint does not seem to exist.")

    def testTask1SimpleBlueprintContents3(self):
        #Check if blueprint content for the version is correct
        machineResourceExists = True
        bp_content = get_blueprint_content(self.Task1_Blueprint_Name, self.headers1)
        bp_yaml = yaml.safe_load(bp_content)

        with open(task1BPFile, 'r') as stream:
            temp = stream.read()
            file_yaml = yaml.safe_load(temp)
        if "resources" in bp_yaml:
            if "HOL_Machine1" in bp_yaml["resources"]:
                del bp_yaml["resources"]["HOL_Machine1"]["metadata"]
                machine_diff = DeepDiff(bp_yaml["resources"]["HOL_Machine1"], file_yaml["resources"]["HOL_Machine1"], ignore_order=True)
            else:
                machine_diff = ""
        else:
            machine_diff = ""
        
        if machine_diff == {} or "dictionary_item_added" in machine_diff or "iterable_item_added" in machine_diff:
            machineResourceExists = True
        else:
            machineResourceExists = False
        
        self.assertEqual(machineResourceExists, self.Task1BlueprintMachineExistsBool, "Cannot verify machine component for Task1")
       

if __name__ == '__main__':
    #   using the failfast parameter means it will stop after the first failed test
    unittest.main(failfast=True, verbosity=2)
