#!/bin/bash
pkill -9 -f ucp-profile-builder/server.py || true
sleep 1
nohup python3 -u /usr/local/google/home/gcaroline/profile_github/ucp-profile-builder/server.py > /tmp/ucp_profile_server.log 2>&1 &
echo $! > /tmp/ucp_profile_server.pid
sleep 1
cat /tmp/ucp_profile_server.log
