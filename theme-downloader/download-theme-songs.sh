#!/bin/sh
set -eu

shows_dir=${SHOWS_DIR:-/shows}
movies_dir=${MOVIES_DIR:-/movies}
interval=${DOWNLOAD_INTERVAL_SECONDS:-86400}
archive_file=${ARCHIVE_FILE:-/data/download-archive.txt}

mkdir -p "$(dirname "$archive_file")"

download_missing_themes() {
  library_dir=$1
  query_suffix=$2
  library_label=$3

  if [ ! -d "$library_dir" ]; then
    echo "$library_label directory does not exist: $library_dir"
    return
  fi

  for media_dir in "$library_dir"/*; do
    [ -d "$media_dir" ] || continue
    [ -f "$media_dir/theme.mp3" ] && continue

    media_name=$(basename "$media_dir")
    query="$media_name $query_suffix"
    echo "Searching for: $query"

    yt-dlp \
      --default-search "ytsearch1" \
      --no-playlist \
      --download-archive "$archive_file" \
      --extract-audio \
      --audio-format mp3 \
      --audio-quality 5 \
      --no-overwrites \
      --output "$media_dir/theme.%(ext)s" \
      "$query" || echo "Download failed for: $media_name"
  done
}

echo "Theme downloader started; checking shows and movies every $interval seconds"

while :; do
  download_missing_themes "$shows_dir" "theme song" "Shows"
  download_missing_themes "$movies_dir" "movie theme song" "Movies"

  sleep "$interval"
done
