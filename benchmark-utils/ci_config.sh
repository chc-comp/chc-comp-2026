#!/bin/bash
export BENCHMARK="timeout 60s benchexec/bin/benchexec"
export BENCHMARK_PARAMS="--read-only-dir=/ \
                         --overlay-dir=/home \
                         --limitCores '-1' \
                         --memorylimit '-1' \
                         --timelimit '-1' \
                         --walltimelimit 30"
export VCLOUD=0