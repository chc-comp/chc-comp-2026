# This file is part of BenchExec, a framework for reliable benchmarking:
# https://github.com/sosy-lab/benchexec
#
# SPDX-FileCopyrightText: 2007-2020 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import benchexec.tools.chc


class Tool(benchexec.tools.chc.ChcTool):
    """
    Tool info for Eldarica.
    """

    REQUIRED_PATHS = [
        "eld",
        "yices"
    ]

    def executable(self, tool_locator):
        return tool_locator.find_executable("eld")

    def version(self, executable):
        return self._version_from_tool(executable, "-h", line_prefix="Eldarica")

    def name(self):
        return "Eldarica"
