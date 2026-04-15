###
export CHART_NAME=ctao-data-explorer
export CHART_LOCATION=chart

include aiv-toolkit/Makefile

export TEST_ARTIFACTS_PATH ?= $(PWD)
export TEST_REPORT_CONFIG ?= $(PWD)/aiv-config.yml
export TEX_CONTENT_PATH ?= $(PWD)/report

build-dev: setup-k8s-cluster
	docker build -f Dockerfile.backend -t harbor.cta-observatory.org/suss/ctao-data-explorer-backend:dev .
	docker build -f Dockerfile.auth -t harbor.cta-observatory.org/suss/ctao-data-explorer-auth:dev .
	docker build -f Dockerfile.frontend -t harbor.cta-observatory.org/suss/ctao-data-explorer-frontend:dev .
	docker build -f Dockerfile.playwright -t harbor.cta-observatory.org/suss/ctao-data-explorer-playwright:dev .
	${KIND} -n ${KUBECLUSTER} load docker-image \
		harbor.cta-observatory.org/suss/ctao-data-explorer-backend:dev \
		harbor.cta-observatory.org/suss/ctao-data-explorer-auth:dev \
		harbor.cta-observatory.org/suss/ctao-data-explorer-frontend:dev \
		harbor.cta-observatory.org/suss/ctao-data-explorer-playwright:dev


###################
# Debug
###################

# Helper: get the release-suffixed deployment name
FRONTEND_DEPLOY = $(shell kubectl get deployment -n default -o name | grep frontend | head -1 | sed 's|deployment.apps/||')
BACKEND_DEPLOY  = $(shell kubectl get deployment -n default -o name | grep backend  | head -1 | sed 's|deployment.apps/||')
INGRESS_NAME    = $(shell kubectl get ingress -n default -o name | head -1 | sed 's|ingress.networking.k8s.io/||')
HAPROXY_DEPLOY  = $(shell kubectl get deployment -n haproxy-controller -o name | head -1 | sed 's|deployment.apps/||')
HAPROXY_SVC_PORT = 30080

dev-debug-network:
	@echo "=== POD IPs ==="
	@kubectl get pods -n default -o wide
	@kubectl get pods -n haproxy-controller -o wide
	@echo ""
	@echo "=== SERVICE IPs ==="
	@kubectl get svc -n default
	@echo ""
	@echo "=== INGRESS ROUTING ==="
	@kubectl describe ingress $(INGRESS_NAME) -n default | grep -A 10 "Rules:" || echo "❌ No ingress found"
	@echo ""
	@echo "=== TEST CONNECTIVITY ==="
	@echo "Frontend → Backend (using Python):"
	@kubectl exec -n default deployment/$(BACKEND_DEPLOY) -- \
		python3 -c "import httpx; r = httpx.get('http://$(BACKEND_DEPLOY):8000/api/v1/health', timeout=5); print(f'HTTP {r.status_code}: {r.text}')" \
		|| echo "❌ Frontend cannot reach backend"
	@echo ""
	@echo "Ingress → Frontend (curl from haproxy controller):"
	@kubectl exec -n haproxy-controller deployment/$(HAPROXY_DEPLOY) -- \
		curl -s -o /dev/null -w "HTTP %{http_code}\n" \
		http://$(FRONTEND_DEPLOY).default.svc.cluster.local:80/health \
		|| echo "❌ Ingress cannot reach frontend"
	@echo ""
	@echo "Browser → Frontend (via Ingress):"
	@curl -s -o /dev/null -w "HTTP %{http_code}\n" \
		-H "Host: ctao-data-explorer.test.example" \
		http://ctao-data-explorer.test.example:$(HAPROXY_SVC_PORT)/ \
		|| echo "❌ Cannot reach via ingress"
	@echo "✅ Network check complete."

dev-trace-request:
	@echo "Tracing a request from browser to backend..."
	@echo ""
	@echo "1. Browser → Ingress Controller (port $(HAPROXY_SVC_PORT))"
	@curl -v -H "Host: ctao-data-explorer.test.example" \
		http://ctao-data-explorer.test.example:$(HAPROXY_SVC_PORT)/ 2>&1 | grep "< HTTP" || echo "❌ No response"
	@echo ""
	@echo "2. HAProxy controller logs (last request):"
	@kubectl logs -n haproxy-controller deployment/$(HAPROXY_DEPLOY) --tail=5 | grep -i "ctao\|error\|warn" || echo "No relevant log entries"
	@echo ""
	@echo "3. Frontend Pod logs (last 5 lines):"
	@kubectl logs -n default deployment/$(FRONTEND_DEPLOY) --tail=5
	@echo ""
	@echo "4. Backend Pod logs (last 5 lines):"
	@kubectl logs -n default deployment/$(BACKEND_DEPLOY) --tail=5

dev-debug-setup:
	@echo "=== VERIFYING SETUP ==="
	@echo ""
	@echo "1️⃣  Pod IPs:"
	@kubectl get pods -n default -o wide | grep ctao-data-explorer
	@echo ""
	@echo "2️⃣  Ingress resources:"
	@kubectl get ingress -A
	@echo ""
	@echo "3️⃣  Ingress configuration:"
	@kubectl get ingress $(INGRESS_NAME) -n default -o yaml | grep -A 20 "spec:" | grep -A 10 "paths:" || echo "❌ Ingress not found"
	@echo ""
	@echo "4️⃣  Backend health (from within cluster):"
	@kubectl exec -n default deployment/$(FRONTEND_DEPLOY) -- \
		python3 -c "import httpx; r = httpx.get('http://$(BACKEND_DEPLOY):8000/api/v1/health', timeout=5); print(f'Status: {r.status_code}'); print(f'Body: {r.text}')" \
		|| echo "❌ Cannot reach backend"
	@echo ""
	@echo "5️⃣  Frontend health (local to pod):"
	@kubectl exec -n default deployment/$(FRONTEND_DEPLOY) -- \
		curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:80/health \
		|| echo "❌ Frontend pod not serving /health locally"
	@echo ""
	@echo "6️⃣  Backend probes:"
	@kubectl get deployment $(BACKEND_DEPLOY) -n default -o yaml | grep -A 5 "livenessProbe\|readinessProbe" || echo "   No probes configured"
	@echo ""
	@echo "7️⃣  Frontend probes:"
	@kubectl get deployment $(FRONTEND_DEPLOY) -n default -o yaml | grep -A 5 "livenessProbe\|readinessProbe" || echo "   No probes configured"

kind-status-all:
	@echo ""
	@echo "=== KIND CLUSTER ==="
	@kind get clusters || echo "No Kind clusters running"
	@echo ""
	@echo "=== KUBERNETES NODES ==="
	@kubectl get nodes 2>/dev/null || echo "Cluster not accessible"
	@echo ""
	@echo "=== PODS ==="
	@kubectl get pods -A 2>/dev/null || echo "Cluster not accessible"
	@echo ""
	@echo "=== SERVICES ==="
	@kubectl get svc -A 2>/dev/null || echo "Cluster not accessible"
	@echo ""
	@echo "=== INGRESS ==="
	@kubectl get ingress -A 2>/dev/null || echo "Cluster not accessible"