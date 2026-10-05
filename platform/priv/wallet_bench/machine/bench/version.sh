# Runs as the tested account (common.sh as_bench). Prints the harness's version.
# Usage: version.sh <harness_id>
case $1 in
  H05) claude --version ;;
  *) echo "no version command for $1" >&2; exit 2 ;;
esac
