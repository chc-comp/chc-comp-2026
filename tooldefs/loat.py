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
        "loat_chc_comp.sh",
        "loat-static",
    ]

    def executable(self, tool_locator):
        return tool_locator.find_executable("loat_chc_comp.sh")

    def version(self, executable):
        # executable = tool_locator.find_executable("loat-static")
        # XXX: this is done because the main executable blocks when no input files are given
        executable = executable.replace("loat_chc_comp.sh", "loat-static")
        return self._version_from_tool(executable, line_prefix="LoAT:  ")

    def name(self):
        return "LoAT"
