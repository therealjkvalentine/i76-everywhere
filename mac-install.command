#!/bin/sh
# Double-click on a Mac: the installer itself lives in mac/ (with the other Mac scripts); this hands over to it.
exec sh "$(cd "$(dirname "$0")" && pwd)/mac/mac-install.command" "$@"
