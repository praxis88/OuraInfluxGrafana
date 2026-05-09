#!/bin/bash
docker exec ourainjector bash -c 'python /etc/oura/oura_post_to_influxdb.py > /proc/1/fd/1'
