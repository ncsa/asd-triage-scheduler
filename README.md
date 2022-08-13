# asd-triage-scheduler
Create events on the shared outlook calendar from CSV input

# Quick start
## Linux
```
d_username=andylytical
d_image=asd-triage-scheduler
d_tag=main

docker run --rm -it --pull always \
  --mount type=bind,src=$HOME,dst=/home \
  -e NETRC=/home/.ssh/netrc \
  -e OAUTH_CONFIG_FILE='/home/.ssh/exchange_oauth.yaml' \
  -e OAUTH_TOKEN_FILE='/home/.ssh/exchange_token' \
  -e TRIAGE_LOCATION='https://illinois.zoom.us/j/....' \
  ${d_username}/${d_image}:${d_tag}
```

## Inside Docker container
* Copy rows from [Ticket Triage Duty Planner](https://docs.google.com/spreadsheets/d/1AwVikVzHB_vQhgJDqYxeVkVVNgeNhGsvWTV5L9mxcGg) into a file
* `./run.sh -f csvfile`

# OAUTH Supporting files
## oauth config file
```
---
tenant_id: UofI tenant ID (from azure active directory)
client_id: client_id of custom app, registered in azure active directory)
client_secret: client_secret of custom app, registered in azure active directory)
scope:
  - 'https://outlook.office365.com/Calendars.ReadWrite.Shared'
  - 'https://outlook.office365.com/EWS.AccessAsUser.All'
```

## Exchange token file
Any path to a local, private file.

# Azure active directory
* https://portal.azure.com
* Login with UofI credentials
* App Registrations
  * New Registration
    * Supported account types
      * Single tenant
* View the new app
  * Overview
    * Copy "Client id" and "Tenant id" into "oauth config file" (above)
  * API Permissions
    * Microsoft Graph
      * Calendars.ReadWrite.Shared
      * EWS.AccessAsUser.All
  * Authentication
    * Redirect URIs
      * `https://login.microsoftonline.com/common/oauth2/nativeclient`
  * Certificates & Secrets
    * New client secret
      * Copy the secret into "oauth config file" (above)
