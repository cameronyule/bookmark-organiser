#! /usr/bin/env nix-shell
#! nix-shell -i bash -p jq

# Check if a file path is provided as an argument
if [ -z "$1" ]; then
    echo "Usage: $0 <path_to_json_file>"
    exit 1
fi

json_file="$1"

# Check if the file exists
if [ ! -f "$json_file" ]; then
    echo "Error: File not found at '$json_file'"
    exit 1
fi

# Run the JQ command and store the output
jq_output=$(jq '
(
  length as $total |
  (map(select(.tags | contains("data:offline"))) | length) as $offline |
  (map(select(.tags | contains("data:redirected"))) | length) as $redirected |
  {
    "total": $total,
    "redirected": $redirected,
    "offline": $offline,
    "online": ($total - $offline)
  }
)
' "$json_file")

# Print the results
echo "$jq_output"
