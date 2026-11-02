#!/bin/bash
# Re-convert all raw cached files to UTF-8 by detecting the declared charset
cd "$(dirname "$0")/.."
find cache/raw -type f -name '*.htm*' -not -path 'cache/raw/fc2/*' | while read raw; do
  u8="cache/utf8/${raw#cache/raw/}"
  mkdir -p "$(dirname "$u8")"
  cs=$(grep -io 'charset=[a-z0-9_-]*' "$raw" | head -1 | cut -d= -f2 | tr 'A-Z' 'a-z')
  case "$cs" in
    utf-8|utf8) cp "$raw" "$u8" ;;
    euc-jp) iconv -f EUC-JP -t UTF-8 -c "$raw" > "$u8" ;;
    *) iconv -f CP932 -t UTF-8 -c "$raw" > "$u8" ;;
  esac
done
