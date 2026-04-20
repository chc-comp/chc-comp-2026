# This file is part of BenchExec, a framework for reliable benchmarking:
# https://github.com/sosy-lab/benchexec
#
# SPDX-FileCopyrightText: 2007-2020 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import benchexec.tools.chc


class Tool(benchexec.tools.chc.ChcTool):
    """
    Tool info for Z3/Spacer.
    """
    def executable(self, tool_locator):
        return tool_locator.find_executable("z3")

    def version(self, executable):
        return self._version_from_tool(executable, line_prefix="Z3 version")

    def name(self):
        return "Z3"
