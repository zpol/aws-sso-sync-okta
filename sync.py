#!/usr/bin/python

## This script is intended to syncronize all or some selected users from Okta to AWS SSO
## depending on a query filtering by group name.
##
## Workflow:
##  0. Get okts_groups from SSM (Parameter Store) convertis into a list and iterates over it.
##  1. It asks to OKTA API for groups matching "okta_groups" variable (okta may show more than one match since the search is regexp based )
##  2. Get all Group_Id's for the matching groups
##  3. Then for each group found asks for all the users inside those groups
##  4. Compare all the users (email) from Okta against AWS SSO and chekcks if the user exists or not in AWS SSO.
##  5. If the user exists does nothing, if doesn't creates it.
##  6. Then on a second phase asks AWS for groups matching "aws_groups" variable ( exact match )
##  7. And search for every user in that groups
##  8. If the user does not exists in that group creates it.

## WARNING: Since this software is not tested enough I would strongly suggest
## to run it carefully by syncing the groups from OKTA to AWSSSO one by one!!
## this was you only can screw up one group at time :)
##
## Also be sure to launch this script being authenticatd via CLI against the Root Account!!
## Otherwise the script won't be able to find the access credentials for both API's.
##
## v0.8


import requests
import json
import boto3
import sys
import time


aws_scim_endpoint = 'https://scim.eu-west-1.amazonaws.com/xxxxxxxxx-xxxx-xxxx-xxxxxx/scim/v2/Users'
aws_scim_groups_endpoint = 'https://scim.eu-west-1.amazonaws.com/xxxxxxxxx-xxxxx-xxxx-xxxxx/scim/v2/Groups'
okta_domain="xxxxxx.okta.com"
#okta_groups=list(sys.argv[1].split(' ')) if len(sys.argv) > 1 else "xxxxxxxxxx"# Source group in Okta
pagination=100


def get_okta_groups():
     ssm = boto3.client('ssm',region_name='eu-west-1') # put the proper AWS region if needed
     aws_parameter = ssm.get_parameter(Name='groups_to_sync',WithDecryption=True)
     okta_groups_raw = aws_parameter['Parameter']['Value']
     global okta_groups
     global aws_groups
     okta_groups = okta_groups_raw.split(",") # source group in Okta
     aws_groups=okta_groups # Destination group in AWS SSO
     print("Getting groups list from SSM (Parameter Store): " + okta_groups_raw)
     return okta_groups


def get_api_tokens():
    ssm = boto3.client('ssm',region_name='eu-west-1') # put the proper AWS region if needed

    aws_parameter = ssm.get_parameter(Name='amz_sso_api_token', WithDecryption=True)
    aws_sso_token = aws_parameter['Parameter']['Value']
    #print(aws_token)

    okta_parameter = ssm.get_parameter(Name='okta_api_token', WithDecryption=True)
    okta_api_token = okta_parameter['Parameter']['Value']
    #print(okta_api_token)

    global okta_headers
    global scim_headers

    scim_headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + aws_sso_token
        }

    okta_headers = {
        "Content-Type": "application/json",
        "Authorization": "SSWS " + okta_api_token,
        "Accept": "application/json"
        }


get_api_tokens()
get_okta_groups()




def okta_get_group_id(group_name):
   list_group_ids = []

   print(">> Retrieving Group ID's from Okta.........")
   print(group_name)
   okta_url = "https://xxxxxxxx.okta.com/api/v1/groups?q=" + group_name + "&limit=" + str(pagination)
   group_ids = requests.get(okta_url, params="",headers=okta_headers)
   print(group_ids.url)
   id=group_ids.json()
   for i in id:
       print("  " + i['id'] + " - [ " + i['profile']['name'] + " ]")
       list_group_ids.append(i["id"])
   return list_group_ids




def read_users_from_okta_groups(list_group_ids):
    list_user_ids = []

    print(">> Getting users from retrieved group ID's .........")
    for group_id in list_group_ids:
        okta_url = "https://xxxxxxxxx.okta.com/api/v1/groups/" + group_id + "/users?limit=" + str(pagination)
        get_users = requests.get(okta_url, params="",headers=okta_headers)

        user_login = get_users.json()
        for u_email in user_login:

            user_dict={
                    "first_name": u_email['profile']['firstName'],
                    "last_name": u_email['profile']['lastName'],
                    "email": u_email['profile']['login']
            }
            if user_dict not in list_user_ids:
                list_user_ids.append(user_dict)


    #print(json.dumps(list_user_ids, indent=2))
    print(">> Got " + str(len(list_user_ids)) + " users from Okta")
    if len(list_user_ids) < 1:
        print("No users to sync...aborting...")
        exit()

    print(">> Checking AWS SSO users list.....")
    return list_user_ids



def get_aws_user_id(email):
    x = requests.get(aws_scim_endpoint, params={ "filter": 'userName eq "' + email + '"' }, headers=scim_headers)
    ou = x.json()
    #print(ou)
    aws_uid = ou['Resources'][0]['id']
    return aws_uid



def get_aws_group_id(group_name):
    x = requests.get(aws_scim_groups_endpoint, params={ "filter": 'displayName eq "' + group_name + '"' }, headers=scim_headers)
    gid = x.json()
    group_id = gid['Resources'][0]['id']
    print(">> Created group name: " + group_name + " [ " + group_id + " ]")
    return group_id



def check_if_aws_sso_user_exists(list_user_ids):
    # aws_login = []
    for okta_user in list_user_ids:

        x = requests.get(aws_scim_endpoint, params={ "filter": 'userName eq "' + okta_user['email'] + '"' }, headers=scim_headers)
        ou = x.json()

        user_exists = ou['totalResults']

        if user_exists != 0:
            aws_uid = ou['Resources'][0]['id']
            print(">> User [ " + ou['Resources'][0]['userName'] + " ] "+ aws_uid + " already exists...")
        else:
            print(">> User [ " + okta_user['email'] + " ] creating user into AWS SSO")

            # Comment the line below to "dry run" mode
            create_user_in_aws_sso(okta_user)



def create_user_in_aws_sso(username):

    data_set={
      "schemas": [
        "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User"
      ],
      "userName": username['email'],
      "name": {
        "familyName": username['last_name'],
        "givenName": username['first_name'],
      },
      "displayName": username['first_name'] + " " + username['last_name'],
      "emails": [{
        "value": username['email'],
        "type": "work",
        "primary": True
      }],
      "active": True
    }

    ds=json.dumps(data_set, indent=2)
    #print(ds)


    x = requests.post(aws_scim_endpoint, json=data_set, headers=scim_headers )
    y = x.json()
    #print(y)



def create_aws_group(group_name):
    data_set={
      "displayName": group_name
    }

    ds=json.dumps(data_set, indent=2)
    x = requests.post(aws_scim_groups_endpoint, json=data_set, headers=scim_headers )
    y = x.json()




def search_awssso_group(aws_group_name):
    group_id = ""
    print(">> Searching Groups matching: [ " + aws_group_name + " ]")
    x = requests.get(aws_scim_groups_endpoint, params={ "filter": 'displayName eq "' + aws_group_name + '"' }, headers=scim_headers)
    gid = x.json()
    print(gid)
    print(">> Results found: "  + str(gid['totalResults']) )
    total_res = gid['totalResults']
    if total_res == 0:
        print(">> Can't find group name: " + aws_group_name + " in AWS SSO, creating group,... ")
        # Comment the line below to DRY RUN mode
        create_aws_group(aws_group_name)
        group_id = get_aws_group_id(aws_group_name)
        return group_id
    else:
        group_id = gid['Resources'][0]['id']
        print('>> Group ID: ' + group_id)
        return group_id



def add_user_to_aws_sso_group(userid,groupid):

    data_set={
        "schemas":[
            "urn:ietf:params:scim:api:messages:2.0:PatchOp"
        ],
        "Operations":[
        {
            "op":"add",
            "path":"members",
            "value":[
            {
                "value":userid
                }
            ]
        }
        ]
    }

    ds=json.dumps(data_set, indent=2)
    # print(ds)

    x = requests.patch(aws_scim_groups_endpoint + "/" + groupid, data=json.dumps(data_set), headers=scim_headers )
    # y = x.json()
    # print(x.content)



def patch_aws_sso_group(aws_group_id, users):
    for user in users:
        #print(user['email'])
        aws_uid = get_aws_user_id(user['email'])
        x = requests.get(aws_scim_groups_endpoint , params={ "filter": 'id eq "' + aws_group_id + '"' + ' and members eq "' + aws_uid + '"'}, headers=scim_headers)
        ou = x.json()

        user_exists_in_group = ou['totalResults']
        if user_exists_in_group != 0:
            print(">> User [ " + user['email'] + " ] already exists in group" + aws_group_id)
        else:
            print(">> Adding [ " + user['email'] + " ] to group " + aws_group_id)
            # Comment the line below for DRY RUN MODE
            add_user_to_aws_sso_group(aws_uid,aws_group_id)



print(">> Syncing users from Okta to AWS SSO")
print("==========================================")

for group in okta_groups:

    print("Migrating group: " + group)

    list_user_ids = read_users_from_okta_groups(okta_get_group_id(group))
    check_if_aws_sso_user_exists(list_user_ids)
    print(aws_groups)
    patch_aws_sso_group(search_awssso_group(group),list_user_ids)
