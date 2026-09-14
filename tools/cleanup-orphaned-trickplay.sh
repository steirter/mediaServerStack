#!/usr/bin/env bash
set -euo pipefail

shows_dir=/media/synology_media/shows
delete_mode=false

usage() {
  printf 'Usage: %s [--delete] [shows-directory]\n' "${0##*/}" >&2
  printf '\nWithout --delete, orphaned .trickplay entries are only reported.\n' >&2
}

while (($# > 0)); do
  case $1 in
    --delete)
      delete_mode=true
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --*)
      printf 'Unknown option: %s\n' "$1" >&2
      usage
      exit 2
      ;;
    *)
      if [[ $shows_dir != /media/synology_media/shows ]]; then
        printf 'Only one shows directory may be provided.\n' >&2
        usage
        exit 2
      fi
      shows_dir=$1
      ;;
  esac
  shift
done

if [[ ! -d $shows_dir ]]; then
  printf 'Shows directory does not exist or is not a directory: %s\n' "$shows_dir" >&2
  exit 1
fi

if $delete_mode; then
  printf 'Scanning for orphaned .trickplay entries to delete under: %s\n' "$shows_dir"
else
  printf 'Scanning for orphaned .trickplay entries under: %s\n' "$shows_dir"
  printf 'Dry run: no files or directories will be deleted. Use --delete to remove them.\n'
fi

orphan_count=0

while IFS= read -r -d '' trickplay_path; do
  trickplay_name=${trickplay_path##*/}
  media_name=${trickplay_name%.trickplay}

  case $media_name in
    *.mkv)
      media_path=${trickplay_path%.trickplay}
      ;;
    *)
      media_path=${trickplay_path%.trickplay}.mkv
      ;;
  esac

  if [[ -f $media_path ]]; then
    continue
  fi

  ((orphan_count += 1))

  if $delete_mode; then
    printf 'Deleting: %s\n' "$trickplay_path"
    if [[ -d $trickplay_path && ! -L $trickplay_path ]]; then
      rm -rf -- "$trickplay_path"
    else
      rm -f -- "$trickplay_path"
    fi
  else
    printf 'Orphaned: %s\n' "$trickplay_path"
  fi
done < <(find "$shows_dir" -depth -name '*.trickplay' -print0)

if $delete_mode; then
  printf 'Deleted %d orphaned .trickplay entr%s.\n' "$orphan_count" "$([[ $orphan_count -eq 1 ]] && printf y || printf ies)"
else
  printf 'Found %d orphaned .trickplay entr%s.\n' "$orphan_count" "$([[ $orphan_count -eq 1 ]] && printf y || printf ies)"
fi
