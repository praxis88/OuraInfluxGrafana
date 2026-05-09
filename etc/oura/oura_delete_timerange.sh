#!/bin/bash

# ── Config ────────────────────────────────────────────────
INFLUX_HOST="http://influxdb2:8086"
INFLUX_TOKEN="${INFLUXDB_TOKEN}"
INFLUX_ORG="${INFLUXDB_ORG}"
INFLUX_BUCKET="${INFLUXDB_BUCKET}"
# ─────────────────────────────────────────────────────────

usage() {
  echo "Usage: $0 -s <start> -e <end> [-p <predicate>]"
  echo ""
  echo "  -s  Start datetime (RFC3339, e.g. 2024-01-01T00:00:00Z)"
  echo "  -e  End datetime   (RFC3339, e.g. 2024-06-01T00:00:00Z)"
  echo "  -p  Predicate      (optional, e.g. '_measurement=\"cpu\"')"
  echo ""
  echo "Examples:"
  echo "  $0 -s 2024-01-01T00:00:00Z -e 2024-06-01T00:00:00Z"
  echo "  $0 -s 2024-01-01T00:00:00Z -e 2024-06-01T00:00:00Z -p '_measurement=\"cpu\"'"
  exit 1
}

# ── Parse args ────────────────────────────────────────────
START=""
STOP=""
PREDICATE=""

while getopts "s:e:p:" opt; do
  case $opt in
    s) START="$OPTARG" ;;
    e) STOP="$OPTARG" ;;
    p) PREDICATE="$OPTARG" ;;
    *) usage ;;
  esac
done

# ── Validate ──────────────────────────────────────────────
if [[ -z "$START" || -z "$STOP" ]]; then
  echo "Error: start and end are required."
  usage
fi

# ── Build JSON body ───────────────────────────────────────
if [[ -n "$PREDICATE" ]]; then
  BODY=$(printf '{"start":"%s","stop":"%s","predicate":"%s"}' "$START" "$STOP" "$PREDICATE")
else
  BODY=$(printf '{"start":"%s","stop":"%s"}' "$START" "$STOP")
fi

# ── Send request ──────────────────────────────────────────
echo "Deleting data from $START to $STOP..."
[[ -n "$PREDICATE" ]] && echo "Predicate: $PREDICATE"

HTTP_STATUS=$(curl --silent --output /dev/null --write-out "%{http_code}" \
  --request POST \
  "${INFLUX_HOST}/api/v2/delete?org=${INFLUX_ORG}&bucket=${INFLUX_BUCKET}" \
  --header "Authorization: Token ${INFLUX_TOKEN}" \
  --header "Content-Type: application/json" \
  --data "$BODY")

# ── Result ────────────────────────────────────────────────
if [[ "$HTTP_STATUS" == "204" ]]; then
  echo "Success — data deleted (HTTP 204)"
else
  echo "Error — HTTP status: $HTTP_STATUS"
  exit 1
fi