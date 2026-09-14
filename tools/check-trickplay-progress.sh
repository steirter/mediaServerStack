#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf 'Usage: %s <shows-directory>\n' "${0##*/}" >&2
  printf '\nReports MKV files with and without a matching .trickplay directory.\n' >&2
}

if (($# == 1)) && [[ $1 == --help || $1 == -h ]]; then
  usage
  exit 0
fi

if (($# != 1)); then
  usage
  exit 2
fi

case $1 in
  --*)
    printf 'Unknown option: %s\n' "$1" >&2
    usage
    exit 2
    ;;
esac

shows_dir=$1

if [[ ! -d $shows_dir ]]; then
  printf 'Shows directory does not exist or is not a directory: %s\n' "$shows_dir" >&2
  exit 1
fi

printf 'Scanning MKV trickplay progress under: %s\n' "$shows_dir"

total_count=0
done_count=0
left_count=0
current_folder=''
folder_total=0
folder_done=0
folder_left=0

print_folder_summary() {
  if ((folder_total == 0)); then
    return
  fi

  printf 'Folder: %s\n' "$current_folder"
  printf '  Done:      %d\n' "$folder_done"
  printf '  Total:     %d\n' "$folder_total"
  printf '  Remaining: %d\n\n' "$folder_left"
}

while IFS= read -r -d '' media_path; do
  media_dir=${media_path%/*}

  if [[ $media_dir != "$current_folder" ]]; then
    print_folder_summary
    current_folder=$media_dir
    folder_total=0
    folder_done=0
    folder_left=0
  fi

  ((total_count += 1))
  ((folder_total += 1))

  trickplay_path=${media_path%.mkv}.trickplay
  if [[ -d $trickplay_path ]]; then
    ((done_count += 1))
    ((folder_done += 1))
  else
    ((left_count += 1))
    ((folder_left += 1))
  fi
done < <(find "$shows_dir" -type f -iname '*.mkv' -print0 | sort -z)

print_folder_summary

if ((total_count == 0)); then
  printf 'No MKV files found.\n'
  exit 0
fi

completion_percent=$((done_count * 100 / total_count))
printf '\nOverall: %d/%d done (%d%%), %d left.\n' \
  "$done_count" "$total_count" "$completion_percent" "$left_count"