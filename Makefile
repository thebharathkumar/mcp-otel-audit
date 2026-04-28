TARGETS := traceloop fastmcp logfire splunk
WEAVER := $(PWD)/.tools/weaver-x86_64-unknown-linux-gnu/weaver
SEMCONV_REGISTRY := https://github.com/open-telemetry/semantic-conventions.git@v1.40.0[model]

.PHONY: all bootstrap capture-all score-all report report-summary clean clean-captures

all: capture-all score-all report-summary

bootstrap:
	./scripts/bootstrap.sh

capture-all: $(addprefix capture-,$(TARGETS))

capture-%:
	./scripts/capture.sh $*

score-all: $(addprefix score-,$(TARGETS))

score-%:
	./scripts/score.sh $*

report-summary:
	uv run --no-project --with rich python scripts/report_summary.py captures/

# The hand-written report lives in reports/REPORT.md. This target just opens it.
report:
	@echo "Edit reports/REPORT.md by hand using the data in captures/*.weaver.json"
	@echo "Run 'make report-summary' for a tabulated quick-look."

clean-captures:
	rm -f captures/*.json captures/*.weaver.json captures/*.meta.json

clean: clean-captures
	for t in $(TARGETS); do \
	  ( cd targets/$$t && docker compose down -v 2>/dev/null || true ); \
	  rm -rf targets/$$t/capture-out; \
	done
