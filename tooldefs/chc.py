# This file is part of BenchExec, a framework for reliable benchmarking:
# https://github.com/sosy-lab/benchexec
#
# SPDX-FileCopyrightText: 2007-2020 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import benchexec.result as result
import benchexec.tools.template


class ChcTool(benchexec.tools.template.BaseTool2):
    """
    Abstract base class for tool infos for CHC solvers.
    These tools share a common output format, which is implemented here.

    Adapted from Smtlib2Tool, but using BaseTool2 instead of BaseTool
    """

    def determine_result(self, run):
        status = None

        for line in run.output:
            line = line.strip()
            if line == "unsat":
                status = result.RESULT_FALSE_PROP
            elif line == "sat":
                status = result.RESULT_TRUE_PROP
            elif not status and line.startswith("(error "):
                status = "ERROR"

        if not status:
            status = result.RESULT_UNKNOWN

        return status
