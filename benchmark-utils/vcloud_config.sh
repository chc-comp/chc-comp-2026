#!/bin/bash

# parameters for benchexec/vcloud-benchmark.py; change these if necessary:
export BENCHMARK_PARAMS="--vcloudPriority URGENT \
                   --overlay-dir=/home/ \
                   --read-only-dir=/ \
                   --vcloudClientHeap 4000 --no-ivy-cache"

export BENCHMARK="./benchexec/contrib/vcloud-benchmark.py"

export VCLOUD=1
