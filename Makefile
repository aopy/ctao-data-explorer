###
# TODO: duplicate in config?
export CHART_NAME=ctao-data-explorer
export CHART_LOCATION=chart

include aiv-toolkit/Makefile

# TODO: move this to kit
export TEST_ARTIFACTS_PATH ?= $(PWD)
export TEST_REPORT_CONFIG ?= $(PWD)/aiv-config.yml
export TEX_CONTENT_PATH ?= $(PWD)/report
