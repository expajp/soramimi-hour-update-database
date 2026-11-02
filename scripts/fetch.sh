#!/bin/bash
# Cached fetch: usage fetch.sh <url>  -> prints local cache path (UTF-8 converted copy in cache/utf8/)
set -e
BASE="https://www7a.biglobe.ne.jp/~soramimiupdate/"
url="$1"
url="${url/http:\/\//https://}"
url="${url//‾/~}"
rel="${url#$BASE}"
raw="cache/raw/$rel"
u8="cache/utf8/$rel"
mkdir -p "$(dirname "$raw")" "$(dirname "$u8")"
if [ ! -s "$raw" ]; then
  curl -sS -f -A "soramimi-db-builder (cached, low-rate)" -o "$raw" "$url" || { echo "FAIL $url" >&2; exit 1; }
  sleep 1
fi
if [ ! -s "$u8" ]; then
  iconv -f CP932 -t UTF-8 -c "$raw" > "$u8" || cp "$raw" "$u8"
fi
echo "$u8"
