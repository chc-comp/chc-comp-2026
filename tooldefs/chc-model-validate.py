import benchexec.result as result
import benchexec.tools.chc


class Tool(benchexec.tools.chc.ChcTool):
    """
    Tool info for chc-model-validate.
    """

    REQUIRED_PATHS = [
        "validate.sh"
    ]

    def determine_result(self, run):
        status = None

        for line in run.output:
            line = line.strip()
            if line == "unsat":
                status = result.RESULT_TRUE_PROP
            elif line == "sat":
                status = result.RESULT_FALSE_PROP
            elif "Expected result unsat but got sat" in line:
                status = result.RESULT_FALSE_PROP

        if not status:
            status = result.RESULT_UNKNOWN

        return status

    def cmdline(self, executable, options, task, rlimits):
        return [executable] + options + [task.single_input_file]

    def executable(self, tool_locator):
        return tool_locator.find_executable("validate.sh")

    def name(self):
        return "chc-model-validate"