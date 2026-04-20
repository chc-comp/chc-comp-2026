# This file is part of BenchExec, a framework for reliable benchmarking:
# https://github.com/sosy-lab/benchexec
#
# SPDX-FileCopyrightText: 2007-2020 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import benchexec.tools.chc


class Tool(benchexec.tools.chc.ChcTool):
    """
    Tool info for Ultimate TreeAutomizer.
    """

    REQUIRED_PATHS = [
        "Ultimate",
        "TreeAutomizer.xml",
        "chc-comp-wrapper.sh",
        "TreeAutomizerHopcroftMinimization.epf",
    ]

    def executable(self, tool_locator):
        return tool_locator.find_executable("chc-comp-wrapper.sh")

    def cmdline(self, executable, options, task, rlimits):
        return [executable, *options, task.single_input_file, "."]

    def version(self, executable):
        return "(unknown version)"

    def name(self):
        return "Ultimate TreeAutomizer"
