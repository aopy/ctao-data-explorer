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


###################
# Debug
###################

# Manual dev-forward, not needed normally, just fallback for debugging
dev-forward:
	@echo "⚠️  WARNING: This is not needed with extraPortMappings in kind-dev-config.yml"
	@echo "⚠️  Use this only if extraPortMappings fails or for debugging"
	@echo ""
	@echo "Starting manual port-forward..."
	@echo "Frontend: http://localhost:8080/home"
	@echo "Backend:  http://localhost:8080/api/docs"
	@echo ""
	@echo "Press Ctrl+C to stop"
	kubectl port-forward -n ingress-nginx service/ingress-nginx-controller 8080:80

# Debug network topology and connectivity
dev-debug-network:
	echo "=== POD IPs ==="; \
	kubectl get pods -n default -o wide; \
	kubectl get pods -n ingress-nginx -o wide; \
	echo ""; \
	echo "=== SERVICE IPs ==="; \
	kubectl get svc -n default; \
	echo ""; \
	echo "=== INGRESS ROUTING ==="; \
	kubectl describe ingress ctao-data-explorer-ingress -n default | grep -A 10 "Rules:"; \
	echo ""; \
	echo "=== TEST CONNECTIVITY ==="; \
	echo "Frontend → Backend (using Python):"; \
	kubectl exec -n default deployment/ctao-data-explorer-frontend -- \
		python3 -c "import httpx; r = httpx.get('http://ctao-data-explorer-backend:8000/api/v1/health', timeout=5); print(f'HTTP {r.status_code}: {r.text}')" 2>/dev/null; \
	echo ""; \
	echo "Ingress → Frontend (using curl from ingress controller):"; \
	kubectl exec -n ingress-nginx deployment/ingress-nginx-controller -- \
		curl -s -o /dev/null -w "HTTP %{http_code}\n" http://ctao-data-explorer-frontend.default.svc.cluster.local:8001/health 2>/dev/null; \
	echo ""; \
	echo "Browser → Frontend (via Ingress):"; \
	curl -s -o /dev/null -w "HTTP %{http_code}\n" http://ctao-data-explorer.local:8080/health 2>/dev/null; \
	echo "✅ Network is correctly set up."

dev-trace-request:
	@echo "Tracing a request from browser to backend..."
	@echo ""
	@echo "1. Browser → Ingress Controller (localhost:8080)"
	@curl -v http://ctao-data-explorer.local:8080/health 2>&1 | grep "< HTTP"
	@echo ""
	@echo "2. Ingress → Frontend Pod"
	@kubectl logs -n ingress-nginx deployment/ingress-nginx-controller --tail=1 | grep ctao-data-explorer-nginx || echo "No recent requests"
	@echo ""
	@echo "3. Frontend Pod logs (last 5 lines):"
	@kubectl logs -n default deployment/ctao-data-explorer-frontend --tail=5
	@echo ""
	@echo "4. Backend Pod logs (last 5 lines):"
	@kubectl logs -n default deployment/ctao-data-explorer-backend --tail=5

dev-debug-setup:
	@echo "\n=== VERIFYING SETUP ==="
	@echo ""
	@echo "1️⃣  Pod IPs:"
	@kubectl get pods -n default -o wide | grep ctao-data-explorer
	@echo ""
	@echo "2️⃣  All Pods in cluster (looking for 10.244.0.7):"
	@kubectl get pods -A -o wide | grep "10.244.0.7" || echo "   No pod with IP 10.244.0.7"
	@echo ""
	@echo "3️⃣  Ingress configuration:"
	@kubectl get ingress ctao-data-explorer-ingress -n default -o yaml | grep -A 20 "spec:" | grep -A 10 "paths:"
	@echo ""
	@echo "4️⃣  Check for multiple Ingress resources:"
	@kubectl get ingress -A
	@echo ""
	@echo "5️⃣  Backend health endpoint test (Backend reachability from Frontend):"
	@kubectl exec -n default deployment/ctao-data-explorer-frontend -- \
		python3 -c "import httpx; r = httpx.get('http://ctao-data-explorer-backend:8000/v1/health'); print(f'Status: {r.status_code}'); print(f'Body: {r.text}')" 2>/dev/null || \
		echo "   ❌ Cannot reach backend /v1/health"
	@echo ""
	@echo "6️⃣ a Frontend health endpoint test (local to frontend):"
	@kubectl exec -n default deployment/ctao-data-explorer-frontend -- \
		python3 -c "import httpx; r = httpx.get('http://127.0.0.1:8001/health'); print(f'Status: {r.status_code}'); print(f'Body: {r.text}')" 2>/dev/null || \
		echo "   ❌ Frontend pod can't serve /health locally"
	@echo ""
	@echo "6️⃣ b Frontend health endpoint test (from backend -> frontend service):"
	@kubectl exec -n default deployment/ctao-data-explorer-backend -- \
		python3 -c "import urllib.request; r = urllib.request.urlopen('http://ctao-data-explorer-frontend:8001/health', timeout=5); print('Status:', r.getcode()); print('Body:', r.read().decode())" 2>&1 || \
		echo "   ❌ Backend cannot reach frontend"
	@echo ""
	@echo "7️⃣  Backend probes configuration:"
	@kubectl get deployment ctao-data-explorer-backend -n default -o yaml | grep -A 5 "livenessProbe\|readinessProbe" || echo "   No probes configured"
	@echo ""
	@echo "8️⃣  Frontend probes configuration:"
	@kubectl get deployment ctao-data-explorer-frontend -n default -o yaml | grep -A 5 "livenessProbe\|readinessProbe" || echo "   No probes configured"
	@echo ""

kind-status-all:
	echo "\n=== STATUS: ==="
	echo "\n=== Kind Cluster ==="
	kind get clusters || echo "No Kind clusters running"
	echo ""
	echo "=== Docker Containers ==="
	docker ps --filter "name=dpps-local" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" || echo "No Docker containers running"
	echo ""
	echo "=== Kubernetes Nodes ==="
	kubectl get nodes 2>/dev/null || echo "Cluster node not accessible"
	echo ""
	echo "=== Pods ==="
	kubectl get pods -A 2>/dev/null || echo "Cluster pods not accessible"
	echo ""
	echo "=== Services ==="
	kubectl get svc -A 2>/dev/null || echo "Cluster service not accessible"
	echo ""
	echo "=== Ingress ==="
	kubectl get ingress -A 2>/dev/null || echo "Cluster ingress pods not accessible"
