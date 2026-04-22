# This file is part of BenchExec, a framework for reliable benchmarking:
# https://github.com/sosy-lab/benchexec
#
# SPDX-FileCopyrightText: 2007-2020 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import benchexec.tools.chc


class Tool(benchexec.tools.chc.ChcTool):
    """
    Tool info for sampletool.
    The filename must match the declared tool name in the benchmark definition XML file.
    """

    def cmdline(self, executable, options, task, rlimits):
        return [executable, task.single_input_file] + options

    def executable(self, tool_locator):
        return tool_locator.find_executable("sample-tool-binary")

    def version(self, executable):
        # If the tool does not support the `--version` flag, overwrite this method.
        return self._version_from_tool(executable)

    def name(self):
        return "Sample Tool"
