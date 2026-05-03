# This file is part of BenchExec, a framework for reliable benchmarking:
# https://github.com/sosy-lab/benchexec
#
# SPDX-License-Identifier: Apache-2.0

import benchexec.tools.chc


class Tool(benchexec.tools.chc.ChcTool):
    """
    Tool info for z4.
    """

    REQUIRED_PATHS = ["z4"]

    def executable(self, tool_locator):
        return tool_locator.find_executable("z4")

    def version(self, executable):
        return self._version_from_tool(executable, arg="--version")

    def name(self):
        return "z4"
