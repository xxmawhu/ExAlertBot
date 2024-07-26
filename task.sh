#!/bin/bash
PYTHON="/miniconda/bin/python3.9"
current_dir=$(cd $(dirname ${BASH_SOURCE[0]}) && pwd)
cd ${current_dir}
exec >>./log/$(basename ${BASH_SOURCE[0]}).$(date +"%Y%m%d" && mkdir -p log) 2>&1
mkdir -p log
find ./log/ -type f -mtime +7 -exec rm -rf {} +
taskset -c 1 $PYTHON -Wignore static_notification_forward_bot.py
