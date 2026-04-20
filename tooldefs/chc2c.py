# This file is part of BenchExec, a framework for reliable benchmarking:
# https://github.com/sosy-lab/benchexec
#
# SPDX-FileCopyrightText: 2007-2020 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import benchexec.tools.chc


class Tool(benchexec.tools.chc.ChcTool):
    """
    Tool info for CHC2C.
    """

    REQUIRED_PATHS = [
        "chc_verif",
        "cvt-cache",
        "lib",
        "resources",
        "chc-comp25.sh",
        "start",
    ]

    def executable(self, tool_locator):
        return tool_locator.find_executable("chc-comp25.sh")

    def version(self, executable):
        executable = executable.replace("chc-comp25.sh", "start")
        return self._version_from_tool(executable, line_prefix="chc_verif.py ")

    def name(self):
        return "CHC2C"
