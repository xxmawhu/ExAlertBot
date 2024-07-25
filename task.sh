#!/bin/bash
PYTHON="/miniconda/bin/python3.9"
current_dir=$(cd $(dirname ${BASH_SOURCE[0]}) && pwd)
cd ${current_dir}
mkdir -p log
taskset -c 1 $PYTHON -Wignore static_notification_forward_bot.py
