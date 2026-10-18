#!/bin/bash
# wait-unlock.sh (runs ON a Mac) MIN : poll every 3 s for up to MIN minutes; as soon as the screen is unlocked, hold the
# display awake (caffeinate -d -i -u, 90 min, pid in /tmp/i76mp/caff.pid) so it does not lock again, take a screenshot
# (/tmp/i76mp/unlocked.png) and print the front app.
end=$(( $(date +%s) + ${1:-30}*60 ))
while [ $(date +%s) -lt $end ]; do
  if ! ioreg -n Root -d1 | grep -q '"CGSSessionScreenIsLocked"=Yes'; then
    nohup caffeinate -d -i -u -t 5400 >/dev/null 2>&1 & echo $! > /tmp/i76mp/caff.pid
    sleep 1; screencapture -x /tmp/i76mp/unlocked.png; echo "UNLOCKED $(date +%T) screencapture rc $? front $(lsappinfo info -only name $(lsappinfo front))"; exit 0
  fi; sleep 3; done
echo "still locked $(date +%T)"; exit 1
