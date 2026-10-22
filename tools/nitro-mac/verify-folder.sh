#!/bin/bash
# verify-folder.sh MD5LIST DIR : compare every file of DIR with MD5LIST ("md5  ./path" lines); Strlkup.dll is reported, not counted
L="$1"; D="$2"; n=0; bad=0
while IFS= read -r line; do h=${line%%  *}; f=${line#*  }; n=$((n+1))
  m=$(md5 -q "$D/$f" 2>/dev/null)
  if [ "$m" != "$h" ]; then case "$f" in ./Strlkup.dll|./glide2x.dll|./OpenGLid.INI) echo "expected change $f: $m";; *) bad=$((bad+1)); echo "BAD $f";; esac; fi
done < "$L"
echo "checked $n, mismatches $bad"
