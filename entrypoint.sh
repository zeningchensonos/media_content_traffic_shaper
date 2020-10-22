#!/bin/bash

# Add frame buffer kernel module from host
ip link add ifb0 type ifb

# Limit uplink and downlink traffic to 4 Mbps
python /python/entrypoint.py