# This file is part of BenchExec, a framework for reliable benchmarking:
# https://github.com/sosy-lab/benchexec
#
# SPDX-FileCopyrightText: 2007-2020 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import benchexec.tools.chc


class Tool(benchexec.tools.chc.ChcTool):
    """
    Tool info for LoAT.
    """

    REQUIRED_PATHS = [
        "lib",
        "solvers",
        "specification-transformation",
        "theta-smtlib.jar",
        "theta.jar",
        "chc",
    ]

    def cmdline(self, executable, options, task, rlimits):
        return [executable, task.single_input_file] + options

    def executable(self, tool_locator):
        return tool_locator.find_executable("chc")

    def version(self, executable):
        return self._version_from_tool(executable)

    def name(self):
        return "ThetaCHC"
