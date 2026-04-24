
############# Global Variables

TOOLS_DIRECTORY = tools
MODELS_DIRECTORY = models

############# Utils

# command to create an ISO timestamp
TIMESTAMP = date "+%Y-%m-%dT%H:%M:%S"

# Command to get the latest results
get_latest = $(shell cd $(2) && ls -d $(1) | sort -V | tail -n 1)

############# Auto-discovery from benchmark-defs
#
# Template naming convention:
#   TOOL.xml.template              → Plain verifier (just run, no validation needed)
#   TOOL-model.xml.template        → Model verifier (run + validate with all validators)
#   TOOL-validation.xml.template   → Validator (validates model verifier outputs)

ALL_TEMPLATES := $(notdir $(wildcard benchmark-defs/*.xml.template))

# Validators: templates with -validation suffix
VALIDATOR_TEMPLATES := $(filter %-validation.xml.template, $(ALL_TEMPLATES))
VALIDATORS := $(VALIDATOR_TEMPLATES:-validation.xml.template=)

# All verifier templates (everything except validators)
VERIFIER_TEMPLATES := $(filter-out %-validation.xml.template, $(ALL_TEMPLATES))

# Model verifiers: verifier templates with -model suffix (produce models, need validation)
MODEL_TEMPLATES := $(filter %-model.xml.template, $(VERIFIER_TEMPLATES))
MODEL_VERIFIERS := $(MODEL_TEMPLATES:-model.xml.template=)

# Plain verifiers: verifier templates without -model suffix (just run)
PLAIN_TEMPLATES := $(filter-out %-model.xml.template, $(VERIFIER_TEMPLATES))
PLAIN_VERIFIERS := $(PLAIN_TEMPLATES:.xml.template=)

# All verifier basenames (template name without .xml.template)
ALL_VERIFIER_BASENAMES := $(VERIFIER_TEMPLATES:.xml.template=)

# Cross product of validators × model verifiers
VALIDATE_TARGETS := $(foreach val,$(VALIDATORS),\
    $(foreach ver,$(MODEL_VERIFIERS),\
        $(val)-validate-$(ver)-models))

# Debug target to inspect auto-discovered values
debug-discovery:
	@echo "VALIDATORS:             $(VALIDATORS)"
	@echo "MODEL_VERIFIERS:        $(MODEL_VERIFIERS)"
	@echo "PLAIN_VERIFIERS:        $(PLAIN_VERIFIERS)"
	@echo "ALL_VERIFIER_BASENAMES: $(ALL_VERIFIER_BASENAMES)"
	@echo "VALIDATE_TARGETS:       $(VALIDATE_TARGETS)"

# Audit benchmark-defs templates: DTD validation, model verdicts, participation table
debug-templates: benchexec
	@python3 ./audit_templates.py benchmark-defs

############# Packaging the artifact

package: download-all

# Add targets here to download tools during CI runs or for local setup. 
# Each tool should be placed in a subdirectory of $(TOOLS_DIRECTORY) with the same name
# as the tool (e.g., tools/spacer).	
download-tools: download-verifiers download-validators 

download-verifiers: \
	$(TOOLS_DIRECTORY)/golem \
	$(TOOLS_DIRECTORY)/spacer \
	$(TOOLS_DIRECTORY)/theta \
	$(TOOLS_DIRECTORY)/loat

download-validators: \
	$(TOOLS_DIRECTORY)/z3 \
	$(TOOLS_DIRECTORY)/cvc5 \
	$(TOOLS_DIRECTORY)/princess

download-all: benchexec chc-comp26-benchmarks-full chc-comp26-benchmarks-test download-tools

############# Download Tools

######################## Targets

benchexec:
	git clone https://github.com/sosy-lab/benchexec
	cd benchexec/benchexec/tools/ && \
	for i in ../../../tooldefs/*.py; do \
		ln -sf $$i; \
	done

chc-comp26-benchmarks-full:
	git clone --depth 1 https://github.com/chc-comp/chc-comp26-benchmarks chc-comp26-benchmarks-full
	cd chc-comp26-benchmarks-full && \
	grep -l inconsistent $$(cat *.set) | while read -r badfile; do \
	for set in *.set; do \
		grep -vF "$$badfile" "$$set" > tmp && mv tmp "$$set"; \
	done; done

chc-comp26-benchmarks-test: chc-comp26-benchmarks-full
	cp -r chc-comp26-benchmarks-full chc-comp26-benchmarks-test
	@for i in chc-comp26-benchmarks-test/*.set; do echo $$i; lines=$$(head -n5 "$$i"); rm $$i; for line in $${lines}; do echo $${line} >> $$i; done; done

### Tools: each tool is downloaded, extracted, and placed in a subdirectory of $(TOOLS_DIRECTORY) with
### the same name as the tool (e.g., tools/golem).

$(TOOLS_DIRECTORY)/golem:
	mkdir -p $(TOOLS_DIRECTORY)
	rm -rf $@
	wget https://github.com/usi-verification-and-security/golem/releases/download/v0.9.0/golem-x64-linux.tar.bz2 -O $(TOOLS_DIRECTORY)/golem.tar.bz2
	cd $(TOOLS_DIRECTORY) && mkdir -p golem && cd golem && tar xvjf ../golem.tar.bz2
	rm $(TOOLS_DIRECTORY)/golem.tar.bz2

$(TOOLS_DIRECTORY)/loat:
	mkdir -p $(TOOLS_DIRECTORY)
	rm -rf $@
	wget https://github.com/LoAT-developers/LoAT/releases/download/chc-comp-2026-v1/LoAT.zip
	cd $(TOOLS_DIRECTORY) && mkdir -p loat && cd loat && unzip ../LoAT.zip
	rm $(TOOLS_DIRECTORY)/LoAT.zip

$(TOOLS_DIRECTORY)/theta:
	mkdir -p $(TOOLS_DIRECTORY)
	rm -rf $@
	wget 'https://zenodo.org/records/19692196/files/Theta-chccomp.zip' -O $(TOOLS_DIRECTORY)/theta.zip
	cd $(TOOLS_DIRECTORY) && unzip theta.zip && mv Theta-chccomp theta
	rm $(TOOLS_DIRECTORY)/theta.zip

$(TOOLS_DIRECTORY)/spacer: $(TOOLS_DIRECTORY)/z3
	mkdir -p $(TOOLS_DIRECTORY)
	rm -rf $@
	ln -sf ./z3/bin $(TOOLS_DIRECTORY)/spacer

### TODO: add new verifiers here.

### Below are the validators.

$(TOOLS_DIRECTORY)/princess:
	mkdir -p $(TOOLS_DIRECTORY)
	rm -rf $@
	wget https://github.com/uuverifiers/princess/releases/download/snapshot-2025-11-17/princess-bin-2025-11-17.zip -O $(TOOLS_DIRECTORY)/princess.zip
	cd $(TOOLS_DIRECTORY) && unzip princess.zip && mv princess-bin-2025-11-17 princess
	cd $(TOOLS_DIRECTORY)/princess && echo '#!/bin/bash\ntail -n +7 "$$1" | $$(dirname "$$0")/../validator/validate-model.py $$2 > validate.smt2 && $$(dirname "$$0")/princess validate.smt2' > validate.sh && chmod +x validate.sh
	rm $(TOOLS_DIRECTORY)/princess.zip

$(TOOLS_DIRECTORY)/z3:
	mkdir -p $(TOOLS_DIRECTORY)
	rm -rf $@
	wget https://github.com/Z3Prover/z3/releases/download/z3-4.16.0/z3-4.16.0-x64-glibc-2.39.zip -O $(TOOLS_DIRECTORY)/z3.zip
	cd $(TOOLS_DIRECTORY) && unzip z3.zip && mv z3-4.16.0-x64-glibc-2.39 z3
	cd $(TOOLS_DIRECTORY)/z3 && echo '#!/bin/bash\ntail -n +7 "$$1" | $$(dirname "$$0")/../validator/validate-model.py $$2 > validate.smt2 && $$(dirname "$$0")/bin/z3 validate.smt2' > validate.sh && chmod +x validate.sh
	rm $(TOOLS_DIRECTORY)/z3.zip

$(TOOLS_DIRECTORY)/cvc5:
	mkdir -p $(TOOLS_DIRECTORY)
	rm -rf $@
	wget https://github.com/cvc5/cvc5/releases/download/cvc5-1.3.3/cvc5-Linux-x86_64-libcxx-static.zip -O $(TOOLS_DIRECTORY)/cvc5.zip
	cd $(TOOLS_DIRECTORY) && unzip cvc5.zip && mv cvc5-Linux-x86_64-libcxx-static cvc5
	cd $(TOOLS_DIRECTORY)/cvc5 && echo '#!/bin/bash\ntail -n +7 "$$1" | $$(dirname "$$0")/../validator/validate-model.py $$2 > validate.smt2 && $$(dirname "$$0")/bin/cvc5 validate.smt2' > validate.sh && chmod +x validate.sh
	rm $(TOOLS_DIRECTORY)/cvc5.zip

############## Setup

configured: ./benchmark-utils/check_configured.sh
	@echo "Checking if the shell variables required to run this artifact are configured"
	./benchmark-utils/check_configured.sh
	bash -c '[[ -e chc-comp26-benchmarks ]]'

__setup_tasks: 
	@echo "Setting up tasks..."
	@rm -rf chc-comp26-benchmarks
	@ln -s $(BENCHMARKS) chc-comp26-benchmarks
	@echo "Tasks set up successfully."

setup-benchmark:
	$(MAKE) __setup_tasks BENCHMARKS=chc-comp26-benchmarks-full

setup-test:
	$(MAKE) __setup_tasks BENCHMARKS=chc-comp26-benchmarks-test


############## Verify Programs

verify-all: $(addprefix verification-, $(ALL_VERIFIER_BASENAMES))

# Generic verification rule for all verifier templates.
# For model templates (e.g., eldarica-model), the -model suffix is stripped
# to find the tool directory (e.g., tools/eldarica).
verification-%: configured
	cp benchmark-defs/$*.xml.template $*.xml
	sed -i 's|../chc-comp26-benchmarks|chc-comp26-benchmarks|g' $*.xml
	- $(BENCHMARK) --no-compress-results \
		--tool-directory $(TOOLS_DIRECTORY)/$(patsubst %-model,%,$*) \
		$(if $(filter 1,$(VCLOUD)),--vcloudAdditionalFiles $(TOOLS_DIRECTORY)/$(patsubst %-model,%,$*)) \
		$(BENCHMARK_PARAMS) $*.xml
	rm $*.xml

############## Process Models

process-all-models: $(addprefix process-models-, $(MODEL_VERIFIERS))

process-models-%:
	rm -rf $(MODELS_DIRECTORY)/$*-models
	mkdir -p $(MODELS_DIRECTORY)
	ln -s "../results/$(call get_latest, $*-model.*.logfiles, results)" $(MODELS_DIRECTORY)/$*-models

############## Validate Models

validate-all: $(VALIDATE_TARGETS)

# Per-validator convenience targets (e.g., cvc5-validate-all)
$(foreach val,$(VALIDATORS),$(eval \
    $(val)-validate-all: $(foreach ver,$(MODEL_VERIFIERS),$(val)-validate-$(ver)-models)))

# Generate validation rules for each (validator, model-verifier) pair
define validation_rule
$(1)-validate-$(2)-models: configured
	cp benchmark-defs/$(1)-validation.xml.template $(1)-validate-$(2)-models.xml
	sed -i 's@../||MODELS-DIR||@$$(MODELS_DIRECTORY)/$(2)-models/$$$${rundefinition_name}.$$$${taskdef_name}.log@g' $(1)-validate-$(2)-models.xml
	sed -i 's|../chc-comp26-benchmarks|chc-comp26-benchmarks|g' $(1)-validate-$(2)-models.xml
	- $$(BENCHMARK) --no-compress-results --tool-directory $$(TOOLS_DIRECTORY)/$(1) \
		$$(if $$(filter 1,$$(VCLOUD)),--vcloudAdditionalFiles $$(TOOLS_DIRECTORY)/$(1) $$(TOOLS_DIRECTORY)/validator models/$(2)-models) \
		$$(BENCHMARK_PARAMS) $(1)-validate-$(2)-models.xml
	rm $(1)-validate-$(2)-models.xml
endef

$(foreach val,$(VALIDATORS),\
    $(foreach ver,$(MODEL_VERIFIERS),\
        $(eval $(call validation_rule,$(val),$(ver)))))

############## Process Results

process-results: generate-tables prepare-pages

generate-tables: clean-tables relabel-verdicts model-verifier-tables plain-verifier-tables \
	model-overall-tables plain-overall-tables cross-verifier-tables

clean-tables:
	@mkdir -p results/tables
	@rm -f results/tables/*.html results/tables/*.csv

relabel-verdicts:
	@python3 majority-vote-relabel.py chc-comp26-benchmarks results


# Model verifiers: validate with validate.py, then generate per-verifier tables
model-verifier-tables:
	@for model_verifier in $(MODEL_VERIFIERS); do \
		verifier_any=$$(ls results/$${model_verifier}-model.*results.CHC-COMP2026_check-sat.*.xml 2>/dev/null | sort -V | tail -n 1); \
		if [ -n "$$verifier_any" ]; then \
			base=$$(echo "$$verifier_any" | sed 's/\.results\..*//'); \
			ln -sfn "$$(basename $$base).logfiles" "results/$${model_verifier}-fixed.logfiles"; \
		fi; \
		categories=$$(ls results/$${model_verifier}-model.*results.CHC-COMP2026_check-sat.*.xml 2>/dev/null \
			| sed 's/.*\.CHC-COMP2026_check-sat\.\(.*\)\.xml/\1/' | sort -u); \
		for category in $$categories; do \
			verifier_latest=$$(ls -d results/$${model_verifier}-model.*results.CHC-COMP2026_check-sat.$${category}.xml 2>/dev/null | sort -V | tail -n 1); \
			validator_args=""; \
			for validator in $(VALIDATORS); do \
				val_latest=$$(ls -d results/$${validator}-validate-$${model_verifier}-models.*results.CHC-COMP2026_check-sat.$${category}.xml 2>/dev/null | sort -V | tail -n 1); \
				[ -n "$$val_latest" ] && validator_args="$$validator_args $$val_latest"; \
			done; \
			if [ -z "$$validator_args" ]; then \
				echo "WARNING: No validator results for $${model_verifier} / $${category}, skipping"; \
				continue; \
			fi; \
			echo "Generating table: $${model_verifier} / $${category}"; \
			python3 ./validate.py -o "results/$${model_verifier}-fixed.results.CHC-COMP2026_check-sat.$${category}.xml" \
				"$$verifier_latest" $$validator_args; \
			./benchexec/bin/table-generator --no-diff \
				--name results-$${model_verifier}-model-$${category} \
				--outputpath results/tables \
				"results/$${model_verifier}-fixed.results.CHC-COMP2026_check-sat.$${category}.xml" $$validator_args; \
		done; \
	done

# Plain verifiers: generate per-verifier tables directly from results
plain-verifier-tables:
	@for plain_verifier in $(PLAIN_VERIFIERS); do \
		categories=$$(ls results/$${plain_verifier}.*results.CHC-COMP2026_check-sat.*.xml 2>/dev/null \
			| sed 's/.*\.CHC-COMP2026_check-sat\.\(.*\)\.xml/\1/' | sort -u); \
		for category in $$categories; do \
			verifier_latest=$$(ls -d results/$${plain_verifier}.*results.CHC-COMP2026_check-sat.$${category}.xml 2>/dev/null | sort -V | tail -n 1); \
			echo "Generating table: $${plain_verifier} / $${category}"; \
			./benchexec/bin/table-generator --no-diff \
				--name results-$${plain_verifier}-$${category} \
				--outputpath results/tables \
				"$$verifier_latest"; \
		done; \
	done

# Overall tables for model verifiers (all categories combined)
model-overall-tables:
	@for model_verifier in $(MODEL_VERIFIERS); do \
		verifier_overall=$$(ls -d results/$${model_verifier}-model.*results.CHC-COMP2026_check-sat.xml 2>/dev/null | sort -V | tail -n 1); \
		if [ -z "$$verifier_overall" ]; then continue; fi; \
		validator_args=""; \
		for validator in $(VALIDATORS); do \
			val_overall=$$(ls -d results/$${validator}-validate-$${model_verifier}-models.*results.CHC-COMP2026_check-sat.xml 2>/dev/null | sort -V | tail -n 1); \
			[ -n "$$val_overall" ] && validator_args="$$validator_args $$val_overall"; \
		done; \
		if [ -z "$$validator_args" ]; then \
			echo "WARNING: No validator results for $${model_verifier} overall, skipping"; \
			continue; \
		fi; \
		echo "Generating overall table: $${model_verifier}"; \
		python3 ./validate.py -o "results/$${model_verifier}-fixed.results.CHC-COMP2026_check-sat.xml" \
			"$$verifier_overall" $$validator_args; \
		./benchexec/bin/table-generator --no-diff \
			--name results-$${model_verifier}-model-overall \
			--outputpath results/tables \
			"results/$${model_verifier}-fixed.results.CHC-COMP2026_check-sat.xml" $$validator_args; \
	done

# Overall tables for plain verifiers (all categories combined)
plain-overall-tables:
	@for plain_verifier in $(PLAIN_VERIFIERS); do \
		verifier_overall=$$(ls -d results/$${plain_verifier}.*results.CHC-COMP2026_check-sat.xml 2>/dev/null | sort -V | tail -n 1); \
		if [ -z "$$verifier_overall" ]; then continue; fi; \
		echo "Generating overall table: $${plain_verifier}"; \
		./benchexec/bin/table-generator --no-diff \
			--name results-$${plain_verifier}-overall \
			--outputpath results/tables \
			"$$verifier_overall"; \
	done

# Cross-verifier comparison tables per category (separate model and solver tracks)
cross-verifier-tables:
	@all_categories=""; \
	for f in results/*-fixed.results.CHC-COMP2026_check-sat.*.xml; do \
		[ -e "$$f" ] && all_categories="$$all_categories $$(echo "$$f" | sed 's|results/[^.]*-fixed\.results\.CHC-COMP2026_check-sat\.\(.*\)\.xml|\1|')"; \
	done; \
	for plain_verifier in $(PLAIN_VERIFIERS); do \
		for f in results/$${plain_verifier}.*results.CHC-COMP2026_check-sat.*.xml; do \
			[ -e "$$f" ] && all_categories="$$all_categories $$(echo "$$f" | sed 's/.*\.CHC-COMP2026_check-sat\.\(.*\)\.xml/\1/')"; \
		done; \
	done; \
	for category in $$(echo $$all_categories | tr ' ' '\n' | sort -u); do \
		model_inputs=""; \
		for f in results/*-fixed.results.CHC-COMP2026_check-sat.$${category}.xml; do \
			[ -e "$$f" ] && model_inputs="$$model_inputs $$f"; \
		done; \
		if [ -n "$$model_inputs" ]; then \
			echo "Generating model cross-verifier table: $${category}"; \
			./benchexec/bin/table-generator --no-diff \
				--name results-$${category}-model \
				--outputpath results/tables \
				$$model_inputs; \
		fi; \
		solver_inputs=""; \
		for plain_verifier in $(PLAIN_VERIFIERS); do \
			pv_latest=$$(ls -d results/$${plain_verifier}.*results.CHC-COMP2026_check-sat.$${category}.xml 2>/dev/null | sort -V | tail -n 1); \
			[ -n "$$pv_latest" ] && solver_inputs="$$solver_inputs $$pv_latest"; \
		done; \
		if [ -n "$$solver_inputs" ]; then \
			echo "Generating solver cross-verifier table: $${category}"; \
			./benchexec/bin/table-generator --no-diff \
				--name results-$${category}-solver \
				--outputpath results/tables \
				$$solver_inputs; \
		fi; \
	done

############## Prepare GitHub Pages

prepare-pages:
	@echo "Preparing GitHub Pages deployment..."
	@mkdir -p results/pages/tables
	@# Copy HTML table files
	@cp results/tables/*.html results/pages/tables/ 2>/dev/null || true
	@# Zip logfile directories (following symlinks) and place alongside tables
	@for dir in results/*.logfiles; do \
		if [ -d "$$dir" ]; then \
			echo "Zipping $$(basename $$dir)..."; \
			(cd results && zip -rq "pages/$$(basename $$dir).zip" "$$(basename $$dir)"); \
		fi; \
	done
	@# Generate index.html with grid layout
	python3 ./generate_pages.py \
		--results-dir results \
		--tables-dir results/pages/tables \
		--output results/pages/tables/index.html \
		--model-verifiers $(MODEL_VERIFIERS) \
		--plain-verifiers $(PLAIN_VERIFIERS)
	@echo "Pages ready at results/pages/"
