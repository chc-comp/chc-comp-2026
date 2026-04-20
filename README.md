# CHC-COMP Model Validation

## Adding / Editing Solvers

Verifiers, model-producing verifiers, and validators are **auto-discovered** from
`benchmark-defs/` based on template filename conventions:

| Template pattern              | Role             | Example                          |
|-------------------------------|------------------|----------------------------------|
| `TOOL.xml.template`           | Plain verifier   | `eldarica.xml.template`          |
| `TOOL-model.xml.template`     | Model-producing verifier   | `eldarica-model.xml.template`    |
| `TOOL-validation.xml.template`| Validator        | `cvc5-validation.xml.template`   |

* **Plain verifiers** are executed once; they do not produce models and need no validation.
* **Model verifiers** produce models that are validated by every discovered validator.
* **Validators** are paired with every model verifier automatically (full cross-product).

To add a new verifier, do the following three things:

1. **Add a download step in the [Makefile](./Makefile).** Under the `Download Tools` section, add a
   Make target that downloads and unpacks the tool into `tools/TOOL`. Then add
   `$(TOOLS_DIRECTORY)/TOOL` to the `download-tools` prerequisite list.

   > [!CAUTION]
   > All submitted tools must be publicly available and include a LICENSE file that permits unrestricted evaluation by any party. The license must not impose any limitations on the use, distribution, or analysis of the tool’s outputs, including but not limited to log files, generated models, or intermediate results. The tool archive should be ideally hosted on a long-term archival site such as Zenodo, but this is not a requirement.

2. **Add a benchmark definition.** Create the appropriate `.xml.template` file in
   `benchmark-defs/` following one of the naming conventions above. Copy an [existing
   template](./benchmark-defs/spacer.xml.template) as a starting point. Remove the 
   `<tasks> </tasks>` sections to opt out of the evaluation for that category. 
   Specify the options for the tool (can be per-category and global).
   If opting in to the model evaluation category, create a `-model.xml.template` file as well,
   see [example](./benchmark-defs/spacer-model.xml.template).

3. **Add a BenchExec tool definition.** Create `tooldefs/TOOL.py` implementing a
   BenchExec `Tool` class (see existing files for examples). This tells BenchExec
   how to locate the executable, parse the version string, and determine results.

Run `make debug-discovery` to verify that the new tool is auto-discovered correctly.

## Running the Competition

### Prerequisites

```bash
make download-all      # downloads tools, benchexec, and benchmarks
```

### Configure the environment

Source one of the provided configs before running any benchmarks:

* `source benchmark-utils/local_config.sh` — local execution
* `source benchmark-utils/ci_config.sh` — CI execution (restricted resources).
* `source benchmark-utils/vcloud_config.sh` — VCloud execution

### Choose a benchmark set

* `make setup-benchmark` — full competition suite (~30 days CPU time, 2 cores, 16 GiB RAM).
* `make setup-test` — small smoke-test subset (~5 min).

### Run

```bash
make verify-all          # run all verifiers and export models
make process-all-models  # symlink model logs into models/
make validate-all        # validate models with all validators
make process-results     # generate result tables in results/tables/
```

### CI

A GitHub Actions workflow (`.github/workflows/run-competition.yml`) runs the full
competition with `ci_config.sh` and publishes the result tables to GitHub Pages.
Trigger it manually via the Actions tab (`workflow_dispatch`).

## Available Make Targets

| Target                          | Description                                                  |
|---------------------------------|--------------------------------------------------------------|
| `make download-all`             | Download all dependencies (tools, benchexec, benchmarks).    |
| `make setup-benchmark`          | Point benchmarks at the full suite.                          |
| `make setup-test`               | Point benchmarks at a small smoke-test subset.               |
| `make verify-all`               | Run all verifiers (plain + model).                           |
| `make verification-TOOL`        | Run a single verifier (e.g., `verification-eldarica-model`). |
| `make process-all-models`       | Symlink model logs for all model verifiers.                  |
| `make validate-all`             | Run all validators against all model verifiers.              |
| `make VALIDATOR-validate-all`   | Run one validator against all model verifiers (e.g., `cvc5-validate-all`). |
| `make process-results`          | Generate result tables in `results/tables/`.                 |
| `make debug-discovery`          | Print auto-discovered verifiers, validators, and targets.    |