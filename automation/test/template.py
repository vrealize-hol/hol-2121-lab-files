import urllib3
import requests
import json
import sys
import argparse
import re
import inspect
import yaml
from deepdiff import DeepDiff
urllib3.disable_warnings()

api_url_base = "https://vr-automation.corp.local/"
apiVersion = "2019-01-15"
user_name = "vcapadmin"
pass_word = "VMware1!"
script_location = "C:/hol-2121-lab-files/automation/test/"

### FUNCTIONS
def getarg():
    parser = argparse.ArgumentParser()
    parser.add_argument('-q', '--examquestion',
                        required=True,
                        action='store'
    )
    arg = parser.parse_args()
    return arg

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

def get_token():
    api_url = '{0}csp/gateway/am/api/login?access_token'.format(api_url_base)
    data = {
        "username": user_name,
        "password": pass_word
    }
    try:
        response = requests.post(api_url, headers={'Content-Type': 'application/json'},
                                data=json.dumps(data), verify=False)
    except:
        return('error')   # could not reach vRA API
    if response.status_code == 200:
        json_data = response.json()
        key = json_data['access_token']
        return(key)
    else:
        return('not ready')

def get_cloud_zones(match):
    api_url = '{0}iaas/api/zones'.format(api_url_base)
    response = requests.get(api_url, headers=headers, verify=False)
    zones = []  # array of all defined cloud zones
    czid = []   # array of matched cloud zone IDs
    match_count = 0
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        count = json_data["totalElements"]
        for x in range(count):      # Iterate through all cloud zones
            zone_name = content[x]["name"]
            zone_id = content[x]["id"]
            zones.append(zone_name) # add to list of zone names
            #if re.match(match, zone_name, re.IGNORECASE):   # see if zone name matches what we are looking for
            if match.lower() in zone_name.lower():   # see if zone name matches what we are looking for
                match_count += 1  # increment counter
                czid.append(zone_id)
        return zones, czid, match_count
    else:   # API call failed
        return zones, czid, 999 

def get_cloud_zone_details(id, policy, tags):
    fcnlog = ''
    api_url = '{0}iaas/api/zones/{1}'.format(api_url_base,id)
    response = requests.get(api_url, headers=headers, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        zone_name = json_data["name"]
        placement_policy = json_data["placementPolicy"]
        capability_tags = json_data["tags"]
        fcnlog += f'Cloud zone name is {zone_name}\n'
        if placement_policy == policy:
            fcnlog += f'Cloud zone placment policy {placement_policy} matches {policy}\n'
            policy_test = True
        else:
            fcnlog += f'*** Cloud zone placment policy {placement_policy} DOES NOT MATCH {policy}\n'
            policy_test = False
        if capability_tags == tags:
            fcnlog += f'Cloud zone capability tags {capability_tags} matches {tags}\n'
            tag_test = True
        else: 
            fcnlog += f'*** Cloud zone capability tags {capability_tags} DOES NOT MATCH {tags}\n'
            tag_test = False
        if (policy_test and tag_test):
            fcnlog += 'Cloud zone is configured correctly'
            fcn_test = True
        else:
            fcnlog += 'Cloud zone is NOT configured correctly'
            fcn_test = False
        return fcn_test, fcnlog
    else:   # API call failed
        fcnlog += 'ERROR: API call failed'
        return False, fcnlog 

def get_projects(match):
    api_url = '{0}iaas/api/projects'.format(api_url_base)
    response = requests.get(api_url, headers=headers, verify=False)
    projects = []  # array of all defined projects
    projid = []   # array of matched project IDs
    match_count = 0
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        count = json_data["totalElements"]
        for x in range(count):      # Iterate through all projects
            proj_name = content[x]["name"]
            proj_id = content[x]["id"]
            projects.append(proj_name) # add to list of project names
            #if re.match(match, proj_name, re.IGNORECASE):   # see if project name matches what we are looking for
            if match.lower() in proj_name.lower():   # see if project name matches what we are looking for
                match_count += 1  # increment counter
                projid.append(proj_id)
        return projects, projid, match_count
    else:   # API call failed
        return projects, projid, 999 

def get_project_details(id, members, admins, zones):
    fcnlog = ''
    api_url = '{0}iaas/api/projects/{1}'.format(api_url_base,id)
    response = requests.get(api_url, headers=headers, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        project_name = json_data["name"]
        project_members = json_data["members"]
        project_admins = json_data["administrators"]
        project_zones = extract_values(json_data, 'zoneId')
        fcnlog += f'Project name is {project_name}\n'
        if project_members == members:
            fcnlog += f'Project members {project_members} matches {members}\n'
            member_test = True
        else:
            fcnlog += f'*** Project members {project_members} DOES NOT MATCH {members}\n'
            member_test = False
        if project_admins == admins:
            fcnlog += f'Project admins {project_admins} matches {admins}\n'
            admin_test = True
        else: 
            fcnlog += f'*** Project admins {project_admins} DOES NOT MATCH {admins}\n'
            admin_test = False
        zones.sort()
        project_zones.sort()
        if project_zones == zones:
            fcnlog += f'Project zones {project_zones} matches {zones}\n'
            cz_test = True
        else:
            fcnlog += f'*** Project zones {project_zones} DOES NOT MATCH {zones}\n'
            cz_test = False
        if (member_test and admin_test and cz_test):
            fcnlog += 'Project is configured correctly'
            fcn_test = True
        else:
            fcnlog += 'Project is NOT configured correctly'
            fcn_test = False
        return fcn_test, fcnlog
    else:   # API call failed
        fcnlog += 'ERROR: API call failed'
        return False, fcnlog 

def get_pricing_cards(match):
    api_url = '{0}price/api/private/pricing-cards'.format(api_url_base)
    response = requests.get(api_url, headers=headers, verify=False)
    pcs = []    # list of all pricing card names
    pcids = []  # list of all pricing card Ids
    match_count = 0
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        count = json_data["totalElements"]
        for x in range(count):
            pc_name = content[x]["name"]
            pc_id = content[x]["id"]
            pcs.append(pc_name) # add name to list of pricing card names
            if match.lower() in pc_name.lower():
                match_count += 1
                pcids.append(pc_id)
        return pcs, pcids, match_count
    else:   # API call failed
        return pcs, pcids, 999

def get_pricing_card_details(id, cpu, mem, storage, match):
    fcnlog = ''
    # check that the pricing card it assigned to the project
    fcnlog += f'Getting projects and looking for a match with: {match}\n'
    proj_list, proj_ids, proj_count = get_projects(match)
    if proj_count ==1: # found one match - proceed
        fcnlog += f'Found a project name match in {proj_list}\n'
        url_filter = "pricingCardId eq '" + id + "'"
        api_url = '{0}price/api/private/pricing-card-assignments?$filter={1}'.format(api_url_base, url_filter)
        response = requests.get(api_url, headers=headers, verify=False)
        if response.status_code == 200:
            json_data = response.json()
            if json_data["content"][0]["entityType"] != 'ALL':  # 'ALL' means it is the Default card
                pc_card_proj = json_data["content"][0]["entityId"]  # project id that pricing card is assigned to
                fcnlog += 'Got the project ID associated with the pricing card. Compare to expected\n'
            else:
                fcnlog += '*** the pricing card is set as default'
                return False, fcnlog
        else:
            fcnlog += 'ERROR: API call failed\n'
            return False, fcnlog
        # verify that the pricing card it associated with the correct project
        if proj_ids[0] == pc_card_proj:
            fcnlog += f'Pricing card project id {pc_card_proj} matches the {match} project id {proj_ids[0]}\n'
        else:
            fcnlog += f'*** Pricing card project id {pc_card_proj} DOES NOT MATCH the {match} project id {proj_ids[0]}\n'
            return False, fcnlog
    elif proj_count == 999:   # API call returned an error
        fcnlog += '*** API call returned an error\n'
        return False, fcnlog
    else:   # multiple matches
        fcnlog += '*** Multiple matches\n'
        return False, fcnlog
    # verify that the pricing card rates are configured correctly
    api_url = '{0}price/api/private/pricing-cards/{1}'.format(api_url_base, id)
    response = requests.get(api_url, headers=headers, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        pc_name = json_data["name"]
        pc_items = json_data["meteringItems"]
        item_count = len(pc_items)
        for x in range(item_count):
            item = pc_items[x]
            metering = item["metering"]
            if item["itemName"] == 'vcpu':
                if metering == cpu:
                    fcnlog += f'vCPU pricing configuration {metering} matches {cpu}\n'
                    cpu_config = True
                else:
                    fcnlog += f'*** vCPU pricing configuration {metering} DOES NOT MATCH {cpu}\n'
                    cpu_config = False
            if item["itemName"] == 'memory':
                if metering == mem:
                    fcnlog += f'Memory pricing configuration {metering} matches {mem}\n'
                    mem_config = True
                else:
                    fcnlog += f'*** Memory pricing configuration {metering} DOES NOT MATCH {mem}\n'
                    mem_config = False
            if item["itemName"] == 'storage':
                if metering == storage:
                    fcnlog += f'Storage pricing configuration {metering} matches {storage}\n'
                    storage_config = True
                else:
                    fcnlog += f'*** Storage pricing configuration {metering} DOES NOT MATCH {storage}\n'
                    storage_config = False
        if (cpu_config and mem_config and storage_config):
            fcnlog += 'Pricing card is configured correctly\n'
            card_test = True
        else:
            fcnlog += 'Pricing card is NOT configured correctly\n'
            card_test = False
        return card_test, fcnlog
    else:   # API call failed
        return False, fcnlog

def get_blueprint_id(bpName):
    # finds the ID of the blueprint matching the passed name
    api_url = '{0}blueprint/api/blueprints'.format(api_url_base)
    response = requests.get(api_url, headers=headers, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        bp_count = len(content)
        fcn_log = f'Looking for a blueprint name matching: {bpName.lower()}\n'
        for x in range(bp_count):
            if bpName.lower() in content[x]["name"].lower():
                fcn_log += f'Found blueprint named: {content[x]["name"]} with ID {content[x]["id"]}\n'
                return(content[x]["id"], fcn_log)
    fcn_log += f'*** Failed to find a blueprint name matching: {bpName.lower()}\n'
    return('no match', fcn_log)

def get_bp_content(bp_id):
    # returns the blueprint yaml based on the blueprint ID
    api_uri = '{0}blueprint/api/blueprints/{1}'.format(api_url_base, bp_id)
    response = requests.get(api_uri, headers=headers, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        return json_data["content"]

def log_diffs(diffs):
    is_changed = False
    is_missing = False
    is_extra = False
    fcnlog = '    Enumerating differences\n'
    try:
        changed_items = diffs['values_changed']
        for key in changed_items:
            found = changed_items[key]['new_value']
            expected = changed_items[key]['old_value']
            fcnlog += f'\tChanged: For {key}, expected {expected} but found {found}\n'
            is_changed = True
    except:
        fcnlog += '\tNo changed values found\n'
    try:
        missing_items = diffs['dictionary_item_removed']
        missing_count = len(missing_items)
        for key in range(missing_count):
            missing = missing_items[key]
            fcnlog += f'\tMissing: {missing}\n'
            is_missing = True
    except:
        fcnlog += '\tNo items missing\n'
    try:
        extra_items = diffs['dictionary_item_added']
        extra_count = len(extra_items)
        msg = '\tNo added items\n'
        for key in range(extra_count):
            extra = extra_items[key]
            if 'metadata' not in extra:     # don't care about metadata that vRA adds
                fcnlog += f'\tExtra (not expected): {extra}\n'
                msg = ''
                is_extra = True
    except:
        fcnlog += '\tNo added items\n'
    fcnlog += msg
    is_diff = is_changed or is_missing or is_extra
    return is_diff, fcnlog

def scratch():
    url_filter = "pricingCardId eq '23f28fff-cda4-4d5d-9ece-baf16b14c537'"
    #api_url = '{0}price/api/private/pricing-card-assignments?$filter={1}'.format(api_url_base, url_filter)
    fcnlog = ''
    api_url = '{0}iaas/api/images'.format(api_url_base, url_filter)
    response = requests.get(api_url, headers=headers, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        region_count = len(content)
        for x in range(region_count):
            item = content[x]
            if item["externalRegionId"] == 'Datacenter:datacenter-21': # This is the Private Cloud region
                mapping = item["mapping"]
                for key in mapping.keys():
                    if "windows server 2019" in key.lower():  # Image has correct name
                        if mapping[key]["name"] == 'windows2019':   # Image is mapped to correct vSphere template
                            fcnlog += f'Found image named {key} mapped to the vSphere windows2019 template\n'
                            return True, fcnlog
                        else:
                            fcnlog += f'*** Found image named {key} but it IS NOT mapped to the vSphere windows2019 template\n'
                            return False, fcnlog
                else:
                    fcnlog += f'*** Did not find an image named Windows Server 2019\n'
                    return False, fcnlog

### One function per exam point is defined below
def q_4_5_1_1():
    cz_match_name = 'mercury aws'  # name of the cloud zone that user should have created
    cz_placement_policy = 'DEFAULT'
    cz_capability_tags = [{'key': 'region', 'value': 'us-west2'}]
    log = f'Function {inspect.stack()[0][3]} started\n'
    log += f'Getting cloud zones and looking for a match with: {cz_match_name}\n'
    zone_list, cz_ids, cz_count = get_cloud_zones(cz_match_name)
    if cz_count == 1:  # we found one match - proceed
        log += f'Found one match in {zone_list}\n'
        zone_config, logs = get_cloud_zone_details(cz_ids[0], cz_placement_policy, cz_capability_tags)
        log += logs
        if zone_config: # the zone was configured correctly
            return('PASS', log)
        else:
            return('FAIL', log)
    elif cz_count == 999:   # API call returned an error
        log += 'returning error to PowerShell'
        return('ERROR: API call for cloud zones did not succeed', log)
    else:   # multiple matches
        log += 'returning error to PowerShell'
        return('ERROR: There are multiple cloud zones matching the name', log)

def q_4_6_1_2():
    proj_match_name = 'mercury'  # match string in name of the project that user should have created
    proj_members = [{'email': 'Project Mercury Users@corp.local@corp.local'}]
    proj_admins = [{'email': 'Project Mercury Admins@corp.local@corp.local'}]
    proj_zones = []  # list of zones expected to be attached to the project
    log = f'Function {inspect.stack()[0][3]} started\n'
    log += f'Getting projects and looking for a match with: {proj_match_name}\n'
    proj_list, proj_ids, proj_count = get_projects(proj_match_name)
    if proj_count ==1: # found one match - proceed
        log += f'Found a project name match in {proj_list}\n'
        # get the cloud zone IDs for expected zones
        cz_match_name = 'mercury aws'  # name of the cloud zone that user should have created
        zone_list, cz_ids, cz_count = get_cloud_zones(cz_match_name)
        if cz_count == 1:  # we found one match - proceed
            log += f'Found one cloud zone match to {cz_match_name} in {zone_list}\n'
            proj_zones.append(cz_ids[0])
        else:
            log += f'MULTIPLE CLOUD ZONE MATCHES OR NO MATCH FOUND FOR {cz_match_name} in {zone_list}\n'
            return('ERROR: An expected cloud zone was not configured on the project', log)
        cz_match_name = 'private cloud'  # name of the cloud zone that user should have created
        zone_list, cz_ids, cz_count = get_cloud_zones(cz_match_name)
        if cz_count == 1:  # we found one match - proceed
            log += f'Found one cloud zone match to {cz_match_name} in {zone_list}\n'
            proj_zones.append(cz_ids[0])
        else:
            log += f'MULTIPLE CLOUD ZONE MATCHES OR NO MATCH FOUND FOR {cz_match_name} in {zone_list}\n'
            return('ERROR: An expected cloud zone was not configured on the project', log)
        proj_config, logs = get_project_details(proj_ids[0], proj_members, proj_admins, proj_zones)
        log += logs
        if proj_config: # the zone was configured correctly
            return('PASS', log)
        else:
            return('FAIL', log)
    elif proj_count == 999:   # API call returned an error
        log += 'returning error to PowerShell'
        return('ERROR: API call for projects did not succeed', log)
    else:   # multiple matches
        log += 'returning error to PowerShell'
        return('ERROR: There are multiple projects matching the name', log)

def q_4_11_1_3():
    match_name = 'mercury'  # name of the project and pricing card that user should have created
    pc_cpu = {'baseRate': 10.0, 'chargeBasedOn': 'USAGE', 'chargeOnPowerState': 'ONLY_WHEN_POWERED_ON', 'chargePeriod': 'MONTHLY'}
    pc_mem = {'baseRate': 5.0, 'chargeBasedOn': 'USAGE', 'chargeOnPowerState': 'ONLY_WHEN_POWERED_ON', 'chargePeriod': 'MONTHLY', 'unit': 'gb'}
    pc_storage = {'baseRate': 1.0, 'chargeBasedOn': 'USAGE', 'chargeOnPowerState': 'ALWAYS', 'chargePeriod': 'MONTHLY', 'unit': 'gb'}
    log = f'Function {inspect.stack()[0][3]} started\n'
    log += f'Getting pricing cards and looking for a match with: {match_name}\n'
    pc_list, pc_ids, pc_count = get_pricing_cards(match_name)
    if pc_count == 1: # found one match - proceed
        log += f'Found one match match in {pc_list}\n'
        pc_config, logs = get_pricing_card_details(pc_ids[0], pc_cpu, pc_mem, pc_storage, match_name)
        log += logs
        if pc_config:   # the pricing card looks good
            return('PASS', log)
        else:
            return('FAIL', log)
    elif pc_count == 999:   # API call returned an error
        log += 'returning error to PowerShell'
        return('ERROR: API call for pricing cards did not succeed', log)
    else:   # multiple matches
        log += 'returning error to PowerShell'
        return('ERROR: There are multiple pricing cards matching the name', log)

def q_4_7_3_1():
    # Checks that an image mapping was created per the instructions
    log = f'Function {inspect.stack()[0][3]} started\n'
    log += 'Getting image mappings\n'
    api_url = '{0}iaas/api/images'.format(api_url_base)
    response = requests.get(api_url, headers=headers, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        region_count = len(content)
        for x in range(region_count):
            item = content[x]
            if item["externalRegionId"] == 'Datacenter:datacenter-21': # This is the Private Cloud region
                log += 'Checking the image mappings for the Private Cloud region\n'
                mapping = item["mapping"]
                for key in mapping.keys():
                    if "windows server 2019" in key.lower():  # Image has correct name
                        log += f'Image Mapping named {key} was found\n'
                        if mapping[key]["name"] == 'windows2019':   # Image is mapped to correct vSphere template
                            log += f'Mapped to the template named {mapping[key]["name"]}\n'
                            return('PASS', log)
                        else:
                            log += f'*** Image Mapping IS NOT mapped to the vSphere windows2019 template\n'
                            return ('FAIL', log)
    log += f'*** Did not find an image mapping named Windows Server 2019 mapped to the Private Cloud region\n'
    return ('FAIL', log)

def q_4_8_3_2():
    # Checks that a flavor mapping was created per the instructions
    log = f'Function {inspect.stack()[0][3]} started\n'
    log += 'Getting flavor mappings\n'
    api_url = '{0}iaas/api/flavors'.format(api_url_base)
    response = requests.get(api_url, headers=headers, verify=False)
    if response.status_code == 200:
        json_data = response.json()
        content = json_data["content"]
        region_count = len(content)
        for x in range(region_count):
            item = content[x]
            if item["externalRegionId"] == 'Datacenter:datacenter-21': # This is the Private Cloud region
                log += 'Checking the flavor mappings for the Private Cloud region\n'
                mapping = item["mapping"]
                for key in mapping.keys():
                    if "extra large" in key.lower():  # Flavor has correct name
                        log += f'Flavor Mapping named {key} was found\n'
                        if mapping[key]["cpuCount"] == 4:   
                            log += f'Flavor has 4 CPUs\n'
                        else:
                            log += f'*** Flavor DOES NOT have 4 CPUs. It is configured with {mapping[key]["cpuCount"]}.\n'
                            return ('FAIL', log)
                        if mapping[key]["memoryInMB"] == 16384:
                            log += f'Flavor has 16 GB of memory\n'
                            return('PASS', log)
                        else:
                            log += f'*** Flavor DOES NOT have 16384 MB of memory. It is configured with {mapping[key]["memoryInMB"]}.\n'
                            return ('FAIL', log)
    log += f'*** Did not find a flavor mapping named extra large mapped to the Private Cloud region\n'
    return ('FAIL', log)

def q_7_3_3_3():
    # multiple checks required for this point
    # 1). check that the base blueprint was imported
    bp_match_name = 'Jupiter Ubuntu'
    base_bp_file = script_location + 'q3_base_bp.yml'     # location of the refrence yaml for the base blueprint
    log = f'Function {inspect.stack()[0][3]} started\n'
    log += '\nTest #1 check that base blueprint was imported\n'
    log += 'Getting matching bluerint ID\n'
    bpId, fcnlog = get_blueprint_id(bp_match_name)
    log += fcnlog
    if bpId == 'no match':   # No blueprint was found matching the name
        return('FAIL', log)
    log += f'Getting the yaml for blueprint ID: {bpId}\n'
    bp_content = get_bp_content(bpId)   # yaml for the matched blueprint
    bp = yaml.safe_load(bp_content)
    # open the reference file
    log += f'Opening the reference yaml file: {base_bp_file}\n'
    with open(base_bp_file, 'r') as stream:
        temp = stream.read()
        ref_bp = yaml.safe_load(temp)
    log += 'Comparing the base blueprint with the reference yaml file\n'
    bp_diff = DeepDiff(ref_bp, bp, ignore_order=True)
    if bp_diff != {}:    # the yaml does not match but it might just be added metadata
        changed, msg = log_diffs(bp_diff)
        if changed:
            log += f'*** The imported base blueprint DOES NOT match the base reference yaml\n'
            log += msg
            return('FAIL', log)
    log += f'The imported blueprint matches the base reference yaml\n'
    log += 'Test #1 successful\n\n'
    return('PASS', log)

### MAIN
message = 'Beginning the Python Script\n'
#arg = getarg().examquestion  # parse the arguemnt passed to the script - this is the exam question being tested
arg = '7.3.3.3'
message += f'{arg} was passed to Python as the question to test\n'

# table of question number input to the function object for that question point identifier
functions = {       
    '4.5.1.1': q_4_5_1_1,
    '4.6.1.2': q_4_6_1_2,
    '4.11.1.3': q_4_11_1_3,
    '4.7.3.1': q_4_7_3_1,
    '4.8.3.2': q_4_8_3_2,
    '7.3.3.3': q_7_3_3_3
    }

# find out if vRA is ready. if not ready we can't make API calls
access_key = get_token()
if access_key == 'error':  # Couldn't reach vRA
    message += f'ERROR: Could not contact the vRA API\n'
    sys.exit()
elif access_key == 'not ready':  # we are not even getting an auth token from vRA so we can't auth to the API
    message += (f'ERROR: Could not get API token from vRA\n')
    sys.exit()
else:
    # build the API header content
    headers = {'Content-Type': 'application/json',
                'Authorization': 'Bearer {0}'.format(access_key)}
    message += f'Got API token from vRA\n'

try:
    # call the function based on the question number
    # put results of the test in 'result' variable
    fcn = functions[(arg)]  # reference to the Python function object
    message += f'Calling function {fcn.__name__}\n'
    result, func_msg = fcn()
    message = f'{result}\n' + message  # prepend the result to the message to be returned
    message += func_msg  # append messages from the function
except:
    message += f'ERROR: No function was found matching the question\n'

print(message) # send message through the pipeline back to PowerShell

