#!/bin/bash

# 啟動 robot.py 並將其輸出重定向到 log 文件
python robot.py > robot.log 2>&1 &

# 啟動 json_receive.py 並將其輸出重定向到 log 文件
python json_receive.py > json_receive.log 2>&1 &

# 使用 tail -f 合併 log 文件並輸出到 stdout
tail -f robot.log json_receive.log
