# asd-triage-scheduler
Create events on the shared outlook calendar from CSV input


# Quick start
1. `curl -o go_asd_triage.sh https://raw.githubusercontent.com/ncsa/asd-triage-scheduler/main/go.sh`
1. `bash ./go_asd_triage.sh`
1. `./run.sh --help`

#### List duty teams with index numbers:
`./run.sh --list_teams`

#### List duty teams rotated 7 positions:
`./run.sh --list_teams --start_at 7`

#### Make triage meetings for work days between 1st Mar and 1st Apr:
`./run.sh --mktriage --start 2023-03-01 --end 2023-04-01`

(Note: existing triage meetings are maintained. This
allows manual triage duty swaps directly in Outlook.)

#### Schedule triage meetings starting with the 13th duty team:
`./run.sh --mktriage --start 2023-04-01 --end 2023-05-01 --start_at 13`

#### Make triage handoff meetings for work days from 1st Mar through 1st May:
`./run.sh --mkhandoff --start 2023-03-01 --end 2023-05-01`

(Note: required attendees are imported from triage meetings.)

(Note: existing handoff meetings will be updated if membership doesn't
match existing triage meetings.)


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
