DEBUG=0
REPO=andylytical/asd-triage-scheduler

declare -A DEFAULTS=(
  ['TRIAGE_HOLIDAYS_FILE']='/home/holidays.csv'
  ['TRIAGE_LOCATION_FILE']='/home/asd_triage_location'
  ['TRIAGE_STAFF_FILE']='/home/asd_triage_staff'
)

DOCKER_ENVS=()


function croak {
  echo "FATAL ERROR: ${@}" 1>&2
  kill -SIGPIPE "$$"
}


function continue_or_exit {
    local msg="Continue?"
    [[ -n "$1" ]] && msg="$1"
    echo "$msg"
    select yn in "Yes" "No"; do
        case $yn in
            Yes) return 0;;
            No ) exit 1;;
        esac
    done
}


function assert_jq {
  # Fail if jq is not installed
  which jq &>/dev/null || croak "Program 'jq' is required but not found."
}


function assert_env_vars {
  # Fail if any env vars are not set
  env_names=( "${!DEFAULTS[@]}" )
  missing=()
  for name in "${env_names[@]}"; do
    if [[ -z "${!name}" ]] ; then
      missing+=("$name")
      echo "Name:$name not set, default='${DEFAULTS[$name]}'"
      DOCKER_ENVS+=( '-e' )
      DOCKER_ENVS+=( "${name}=${DEFAULTS[${name}]}" )
		else
      echo "Name:$name is set ('${!name}') OK"
      DOCKER_ENVS+=( '-e' )
      DOCKER_ENVS+=( "${name}=${!name}" )
    fi
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "Following env vars are not set: ${missing[@]}."
    continue_or_exit "Use default values?"
  fi
}


function latest_tag {
  [[ "$DEBUG" -eq 1 ]] && set -x
  local _page=1
  local _pagesize=100
  local _baseurl=https://registry.hub.docker.com/v2/repositories

  curl -L -s "${_baseurl}/${REPO}/tags?page=${_page}&page_size=${_pagesize}" \
  | jq '."results"[]["name"]' \
  | sed -e 's/"//g' \
  | sort -r \
  | head -1
}

[[ "$DEBUG" -eq 1 ]] && set -x

assert_jq
assert_env_vars

tag=$(latest_tag)

docker run --rm -it --pull always \
  --mount type=bind,src=$HOME,dst=/home \
  -e OAUTH_CONFIG_FILE='/home/.ssh/exchange_oauth.yaml' \
  -e OAUTH_TOKEN_FILE='/home/.ssh/exchange_token' \
  "${DOCKER_ENVS[@]}" \
  $REPO:$tag
