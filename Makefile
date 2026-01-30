###
# TODO: duplicate in config?
export CHART_NAME=ctao-data-explorer
export CHART_LOCATION=chart

include aiv-toolkit/Makefile

# TODO: move this to kit
export TEST_ARTIFACTS_PATH ?= $(PWD)
export TEST_REPORT_CONFIG ?= $(PWD)/aiv-config.yml
export TEX_CONTENT_PATH ?= $(PWD)/report



# - dockerfile_path: Dockerfile.backend
#   repository: harbor.cta-observatory.org/suss/ctao-data-explorer-backend
# - dockerfile_path: Dockerfile.frontend
#   repository: harbor.cta-observatory.org/suss/ctao-data-explorer-frontend
# - dockerfile_path: Dockerfile.playwright
#   repository: harbor.cta-observatory.org/suss/ctao-data-explorer-playwright


build-dev: setup-k8s-cluster
	docker build -f Dockerfile.backend -t harbor.cta-observatory.org/suss/ctao-data-explorer-backend:dev .
	docker build -f Dockerfile.frontend -t harbor.cta-observatory.org/suss/ctao-data-explorer-frontend:dev .
	docker build -f Dockerfile.playwright -t harbor.cta-observatory.org/suss/ctao-data-explorer-playwright:dev .
	${KIND} -n ${KUBECLUSTER} load docker-image \
		harbor.cta-observatory.org/suss/ctao-data-explorer-backend:dev \
		harbor.cta-observatory.org/suss/ctao-data-explorer-frontend:dev \
		harbor.cta-observatory.org/suss/ctao-data-explorer-playwright:dev
