# aws-sso-sync-okta
A small script to migrate or synchronize users &amp; groups from Okta to AWS SSO

[![Foo](https://www.androidfreeware.net/img2/com-okta-android-mobile-oktamobile.jpg)](https://okta.com/) ![Foo](https://www.iconsdb.com/icons/preview/green/arrow-32-xxl.png) [![Foo](https://awsvideocatalog.com/images/aws/png/PNG%20Light/Security,%20Identity,%20&%20Compliance/AWS-Single-Sign-On.png)](https://aws.com)


| Changelog  | Version  | 
|---|---|
| Fixed search filtering in okta  + enable dry run mode| 0.6  |

This script is intended to syncronize all or some selected users from Okta to AWS SSO
based on a query filtering by group name on both APIs.

## Workflow:

  0. Connect to AWS SSM to get access credentials for both APIs
  1. It asks to OKTA API for groups matching "okta_groups" variable (okta may show more than one match since the search is regexp based )
  2. Get all Group_Id's for the matching groups (if no groups matching exits)
  3. Then for each group found asks for all the users inside those groups
  4. Compare all the users (email) from Okta against AWS SSO and chekcks if the user exists or not in AWS SSO.
  5. If the user exists does nothing, if doesn't creates it.
  6. Then on a second phase asks AWS for groups matching "aws_groups" variable ( exact match )
  7. And search for every user in that groups
  8. If the user does not exists in that group creates it.

## Configuration

1. Get your AWS SSO Setup ready and collect the necessary values (SCIM URL's for users and groups)
   More info: https://docs.aws.amazon.com/singlesignon/latest/userguide/provision-automatically.html

2. Create an API token to ask AWS API.
3. Create an Okta API token 
4. Save those values into an SSM (Parameter Store) [`okta_api_token` and `amz_sso_api_token`]
5. Put your SCIM URL's into the script
6. Save and quit

## Usage
`sync-users.py <group_name>`

## Considerations
* Okta API when searching for groups (https://developer.okta.com/docs/reference/api/groups/) as they mention in the documentation, currently performs a startsWith match but it should be considered an implementation detail and may change without notice in the future. 
To avoid more than one result I strongly sugget to use prefixes as a naming convention for the group names (I.e.: `xx_groupname`), but for now the script is being modified to do some checks and verify there's only one result. (It's a prevention measeure, of course it can be iterated on a loop if necessary)

## Demo: 

```
me@crashtestdummy[~]> sync-users.py xx_devops

>> Syncing users from Okta to AWS SSO
==========================================
>> Retrieving Group ID's from Okta.........
['xx_devops']
  00g1by6snswq40ERK417 - [ xx_devops ]
>> Getting users from retrieved group ID's .........
>> Got 2 users from Okta
>> Checking AWS SSO users list.....
>> User [ xxxxxxxx1@xxxxxxxxx.com ] 93671e0715-1525f435-9359-4c9b-a2fe-13209d15cff8 already exists...
>> User [ xxxxxxxx2@xxxxxxxxx.com ] 93671e0715-08b298da-4bce-4f2e-a7b2-18433607d07f already exists...
>> Searching Groups matching: [ xx_devops ]
>> Results found: 1
>> Group ID: 93671e0715-b65a0f2f-ds7d-402d-a05c-91441697f9dc
>> User [ xxxxxxxx1@xxxxxxxxx.com ] already exists in group93671e0715-b65a0f2f-ce8b-a05c-a05c-91441687f9dc
>> User [ xxxxxxxx2@xxxxxxxxx.com ] already exists in group93671e0715-b65a0f2f-ce8b-a05c-a05c-914416973fdc
>> User [ xxxxxtest@xxxxxxxxx.com ] creating user into AWS SSO .......OK
>> User [ xxxxtest1@xxxxxxxxx.com ] creating user into AWS SSO .......OK
>> User [ xxxxtest2@xxxxxxxxx.com ] creating user into AWS SSO .......OK
```
---
## TODO/WIP

* Iterate over a list of groups to sync multiple groups
* Get the list of groups from SSM (Parameter Store) instead of passing an argument to the script

## Troubleshooting
(WIP)

WARNING: Since this software is not tested enough I would strongly suggest
to run it carefully by syncing the groups from OKTA to AWS SSO one by one!!
this was you only can screw up one group at time :)

Since the access credentials are stored in Parameter Store (AWS SSM),be sure to launch this script 
being authenticatd via CLI against the Root Account or where you're configuring the AWS SSO and AWS SSM.
Otherwise the script won't be able to find the access credentials for both API's.

