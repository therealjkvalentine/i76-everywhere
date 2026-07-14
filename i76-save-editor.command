#!/bin/sh
# Double-click to open the Interstate '76 save editor with your saves loaded.
cd "$(dirname "$0")"
exec python3 i76-save-editor-server.py
