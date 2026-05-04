# This file is part of BenchExec, a framework for reliable benchmarking:
# https://github.com/sosy-lab/benchexec
#
# SPDX-FileCopyrightText: 2007-2020 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import os

import benchexec.tools.chc


class Tool(benchexec.tools.chc.ChcTool):
    """
    Tool info for z4.
    """

    REQUIRED_PATHS = [
        "z4",
        "run_solver.sh",
        "LICENSE",
        "README.md",
    ]

    def executable(self, tool_locator):
        return tool_locator.find_executable("run_solver.sh")

    def name(self):
        return "z4"

    def version(self, executable):
        z4_binary = os.path.join(os.path.dirname(executable), "z4")
        return self._version_from_tool(z4_binary, arg="--version")

    def cmdline(self, executable, options, task, rlimits):
        cmd = [executable] + options
        if not self._has_z4_timeout_option(options):
            timeout_ms = self._z4_timeout_ms(rlimits)
            if timeout_ms is not None:
                cmd += ["--z4-timeout-ms", str(timeout_ms)]
        return cmd + [task.single_input_file]

    def _has_z4_timeout_option(self, options):
        return any(
            opt == "--z4-timeout-ms" or opt.startswith("--z4-timeout-ms=")
            for opt in options
        )

    def _z4_timeout_ms(self, rlimits):
        for key in ("walltime", "cputime"):
            value = getattr(rlimits, key, None)
            if value is None and isinstance(rlimits, dict):
                value = rlimits.get(key)
            timeout_ms = self._limit_to_timeout_ms(value)
            if timeout_ms is not None:
                return timeout_ms
        return None

    def _limit_to_timeout_ms(self, value):
        if value is None:
            return None
        try:
            seconds = value.total_seconds() if hasattr(value, "total_seconds") else float(value)
        except (TypeError, ValueError):
            return None
        if seconds <= 0:
            return None
        ms = int(seconds * 1000)
        reserve = min(30000, max(5000, ms // 10))
        return max(1, ms - reserve)
