#!/bin/bash

for requiredoption in BENCHMARK_PARAMS BENCHMARK VCLOUD
do
  if [ -z "${!requiredoption}" ]
  then
    >&2 echo -e "$requiredoption not set! You need to source a config first, for example by runnning:\n\n source benchmark-utils/config.sh\n"
    exit 1
  fi
done
