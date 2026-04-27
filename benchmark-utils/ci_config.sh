#!/bin/bash
export BENCHMARK="timeout -k 60 360 benchexec/bin/benchexec"
export BENCHMARK_PARAMS="--read-only-dir=/ \
                         --overlay-dir=/home \
                         --limitCores '-1' \
                         --memorylimit '-1' \
                         --timelimit '-1' \
                         --walltimelimit 30"
export VCLOUD=0
