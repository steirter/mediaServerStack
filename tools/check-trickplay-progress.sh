#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf 'Usage: %s <media-directory>\n' "${0##*/}" >&2
  printf '\nReports video files with and without a matching .trickplay directory.\n' >&2
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

media_dir=$1

if [[ ! -d $media_dir ]]; then
  printf 'Media directory does not exist or is not a directory: %s\n' "$media_dir" >&2
  exit 1
fi

media_dir=$(cd -- "$media_dir" && pwd -P)

printf 'Scanning video trickplay progress under: %s\n' "$media_dir"

total_count=0
done_count=0
left_count=0
current_title=''
title_total=0
title_done=0
title_left=0

find_video_files() {
  find "$@" -type f \( \
    -iname '*.mkv' -o -iname '*.mp4' -o -iname '*.m4v' -o \
    -iname '*.avi' -o -iname '*.mov' -o -iname '*.wmv' -o \
    -iname '*.webm' -o -iname '*.mpg' -o -iname '*.mpeg' -o \
    -iname '*.ts' -o -iname '*.m2ts' -o -iname '*.mts' -o \
    -iname '*.vob' -o -iname '*.ogv' -o -iname '*.3gp' -o -iname '*.flv' \
  \) -print0
}

print_title_summary() {
  if ((title_total == 0)); then
    return
  fi

  printf 'Title: %s\n' "$current_title"
  printf '  Done:      %d\n' "$title_done"
  printf '  Total:     %d\n' "$title_total"
  printf '  Remaining: %d\n\n' "$title_left"
}

while IFS= read -r -d '' media_path; do
  relative_path=${media_path#"$media_dir"/}
  title=${relative_path%%/*}
  if [[ $relative_path == "$title" ]]; then
    title=${title%.*}
  fi

  if [[ $title != "$current_title" ]]; then
    print_title_summary
    current_title=$title
    title_total=0
    title_done=0
    title_left=0
  fi

  ((total_count += 1))
  ((title_total += 1))

  trickplay_path=${media_path%.*}.trickplay
  has_trickplay=false
  if [[ -d $trickplay_path ]]; then
    has_trickplay=true
  else
    media_parent=${media_path%/*}
    sibling_trickplay=$(find "$media_parent" -mindepth 1 -maxdepth 1 -type d -iname '*.trickplay' -print -quit)
    if [[ -n $sibling_trickplay ]]; then
      parent_video_count=0
      while IFS= read -r -d '' parent_video; do
        ((parent_video_count += 1))
        if ((parent_video_count > 1)); then
          break
        fi
      done < <(find_video_files "$media_parent" -maxdepth 1)
      if ((parent_video_count == 1)); then
        has_trickplay=true
      fi
    fi
  fi

  if $has_trickplay; then
    ((done_count += 1))
    ((title_done += 1))
  else
    ((left_count += 1))
    ((title_left += 1))
  fi
done < <(find_video_files "$media_dir" | sort -z)

print_title_summary

if ((total_count == 0)); then
  printf 'No MKV files found.\n'
  exit 0
fi

completion_percent=$((done_count * 100 / total_count))
printf '\nOverall: %d/%d done (%d%%), %d left.\n' \
  "$done_count" "$total_count" "$completion_percent" "$left_count"