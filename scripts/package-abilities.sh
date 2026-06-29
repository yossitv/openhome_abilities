#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/package-abilities.sh [ABILITY ...]
  ./scripts/package-abilities.sh --all
  ./scripts/package-abilities.sh --list

Packages ability directories from abilities/ into zip files.

With no ABILITY arguments, all abilities are packaged.

Options:
  -o, --output-dir DIR  Write zip files to DIR. Defaults to dist/.
  -h, --help            Show this help.
      --list            List available abilities.
      --all             Package all abilities.

Examples:
  ./scripts/package-abilities.sh
  ./scripts/package-abilities.sh simple-hello
  ./scripts/package-abilities.sh youtube-live-companion -o /tmp/openhome-zips
USAGE
}

fail() {
  echo "error: $*" >&2
  exit 1
}

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"
abilities_dir="$repo_root/abilities"
output_dir="$repo_root/dist"
package_all=0
abilities=()

list_abilities() {
  find "$abilities_dir" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort
}

validate_ability_name() {
  local ability_name="$1"

  case "$ability_name" in
    "" | "." | ".." | */* | /*)
      fail "invalid ability name: $ability_name"
      ;;
  esac
}

validate_zip() {
  local zip_path="$1"
  local expected_top_level="$2"
  local top_levels

  top_levels="$(unzip -Z1 "$zip_path" | awk -F/ 'NF && $1 != "" {print $1}' | sort -u)"

  if [[ "$top_levels" != "$expected_top_level" ]]; then
    fail "$zip_path must contain a single top-level directory named $expected_top_level"
  fi
}

package_ability() {
  local ability_name="$1"
  local ability_path="$abilities_dir/$ability_name"
  local zip_path="$output_dir/$ability_name.zip"

  validate_ability_name "$ability_name"
  [[ -d "$ability_path" ]] || fail "ability not found: $ability_name"

  mkdir -p "$output_dir"
  rm -f "$zip_path"

  (
    cd "$abilities_dir"
    zip -qr "$zip_path" "$ability_name" \
      -x "*/__pycache__/" \
      -x "*/__pycache__/*" \
      -x "*.pyc" \
      -x "*.pyo" \
      -x "*/.DS_Store" \
      -x "*.DS_Store"
  )

  validate_zip "$zip_path" "$ability_name"
  printf 'wrote %s\n' "$zip_path"
}

while (($# > 0)); do
  case "$1" in
    -h | --help)
      usage
      exit 0
      ;;
    --list)
      [[ -d "$abilities_dir" ]] || fail "abilities directory not found: $abilities_dir"
      list_abilities
      exit 0
      ;;
    --all)
      package_all=1
      shift
      ;;
    -o | --output-dir)
      shift
      [[ $# -gt 0 ]] || fail "--output-dir requires a directory"
      output_dir="$1"
      shift
      ;;
    --output-dir=*)
      output_dir="${1#*=}"
      shift
      ;;
    --)
      shift
      while (($# > 0)); do
        abilities+=("$1")
        shift
      done
      ;;
    -*)
      fail "unknown option: $1"
      ;;
    *)
      abilities+=("$1")
      shift
      ;;
  esac
done

if [[ "$output_dir" != /* ]]; then
  output_dir="$repo_root/$output_dir"
fi

command -v zip >/dev/null 2>&1 || fail "zip command not found"
command -v unzip >/dev/null 2>&1 || fail "unzip command not found"
[[ -d "$abilities_dir" ]] || fail "abilities directory not found: $abilities_dir"

if [[ $package_all -eq 1 && ${#abilities[@]} -gt 0 ]]; then
  fail "use --all or explicit ability names, not both"
fi

if [[ $package_all -eq 1 || ${#abilities[@]} -eq 0 ]]; then
  while IFS= read -r ability_name; do
    abilities+=("$ability_name")
  done < <(list_abilities)
fi

[[ ${#abilities[@]} -gt 0 ]] || fail "no abilities found in $abilities_dir"

for ability_name in "${abilities[@]}"; do
  package_ability "$ability_name"
done
