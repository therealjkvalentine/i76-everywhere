#!/bin/bash
# deploy-probe.sh <i76probe.exe> : copy the probe + probe3.sh to /tmp/i76mp on the laptop, Andrew's and Michael's Macs
here=$(cd "$(dirname "$0")" && pwd); . "$here/hosts.sh"
scp -q $SSHO "$1" $LAPTOP:/tmp/i76mp/i76probe3.exe && scp -q $SSHO "$here/probe3.sh" $LAPTOP:/tmp/i76mp/probe3.sh
on L <<EOS
chmod +x /tmp/i76mp/probe3.sh; echo "laptop \$(md5 -q /tmp/i76mp/i76probe3.exe)"
for u in $ANDREW $MICHAEL; do ssh $SSHO \$u 'mkdir -p /tmp/i76mp' && scp -q /tmp/i76mp/i76probe3.exe /tmp/i76mp/probe3.sh \$u:/tmp/i76mp/ && echo "\$u \$(ssh $SSHO \$u 'chmod +x /tmp/i76mp/probe3.sh; md5 -q /tmp/i76mp/i76probe3.exe')"; done
EOS
