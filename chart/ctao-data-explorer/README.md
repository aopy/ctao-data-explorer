# CTAO Data Explorer Helm Chart

This Helm chart deploys the CTAO Data Explorer application on a Kubernetes cluster.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.0+
- PV provisioner support in the underlying infrastructure (for PostgreSQL persistence)

## Components

This chart deploys the following components:

- **Backend**: FastAPI application (port 8000)
- **Frontend**: React/Node.js application (port 3000)
- **PostgreSQL**: Database server (port 5432)
- **Redis**: Cache server (port 6379)

## Installing the Chart

### Build Docker Images

Before installing, build the required Docker images:

```bash
# Build backend image
docker build -t ctao-data-explorer-backend:latest -f Dockerfile .

# Build frontend image
docker build -t ctao-data-explorer-frontend:latest -f Dockerfile.frontend .
```

### Install the Chart

To install the chart with the release name `my-release`:

```bash
helm install my-release ./helm/ctao-data-explorer
```

### Install with Custom Values

Create a `custom-values.yaml` file with your configuration:

```yaml
backend:
  image:
    repository: your-registry.com/ctao-data-explorer-backend
    tag: "v1.0.0"
  
  env:
    POSTGRES_PASSWORD: "secure-password"

frontend:
  image:
    repository: your-registry.com/ctao-data-explorer-frontend
    tag: "v1.0.0"

ingress:
  enabled: true
  hosts:
    - host: data-explorer.yourdomain.com
      paths:
        - path: /api
          pathType: Prefix
          backend: backend
        - path: /
          pathType: Prefix
          backend: frontend
  tls:
    - secretName: data-explorer-tls
      hosts:
        - data-explorer.yourdomain.com

postgresql:
  primary:
    persistence:
      enabled: true
      size: 20Gi
      storageClass: "standard"
```

Then install with:

```bash
helm install my-release ./helm/ctao-data-explorer -f custom-values.yaml
```

## Upgrading the Chart

To upgrade an existing release:

```bash
helm upgrade my-release ./helm/ctao-data-explorer -f custom-values.yaml
```

## Uninstalling the Chart

To uninstall/delete the `my-release` deployment:

```bash
helm uninstall my-release
```

## Configuration

The following table lists the configurable parameters of the chart and their default values.

### Global Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `global.imagePullSecrets` | Global Docker registry secret names | `[]` |

### Backend Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `backend.enabled` | Enable backend deployment | `true` |
| `backend.replicaCount` | Number of backend replicas | `1` |
| `backend.image.repository` | Backend image repository | `ctao-data-explorer-backend` |
| `backend.image.tag` | Backend image tag | `latest` |
| `backend.image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `backend.service.type` | Kubernetes service type | `ClusterIP` |
| `backend.service.port` | Service port | `8000` |
| `backend.resources.limits.cpu` | CPU limit | `1000m` |
| `backend.resources.limits.memory` | Memory limit | `1Gi` |
| `backend.autoscaling.enabled` | Enable HPA | `false` |
| `backend.env` | Environment variables | See values.yaml |

### Frontend Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `frontend.enabled` | Enable frontend deployment | `true` |
| `frontend.replicaCount` | Number of frontend replicas | `1` |
| `frontend.image.repository` | Frontend image repository | `ctao-data-explorer-frontend` |
| `frontend.image.tag` | Frontend image tag | `latest` |
| `frontend.service.type` | Kubernetes service type | `ClusterIP` |
| `frontend.service.port` | Service port | `3000` |

### PostgreSQL Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `postgresql.enabled` | Enable PostgreSQL | `true` |
| `postgresql.auth.username` | PostgreSQL username | `ao` |
| `postgresql.auth.password` | PostgreSQL password | `password` |
| `postgresql.auth.database` | PostgreSQL database name | `fastapi_db` |
| `postgresql.primary.persistence.enabled` | Enable persistence | `true` |
| `postgresql.primary.persistence.size` | PVC size | `8Gi` |

### Redis Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `redis.enabled` | Enable Redis | `true` |
| `redis.master.persistence.enabled` | Enable persistence | `false` |

### Ingress Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ingress.enabled` | Enable ingress | `false` |
| `ingress.className` | Ingress class name | `nginx` |
| `ingress.hosts` | Ingress hosts configuration | See values.yaml |

## Accessing the Application

After installation, follow the instructions in the NOTES output to access your application.

### Port Forwarding (for testing)

```bash
# Access frontend
kubectl port-forward svc/my-release-ctao-data-explorer-frontend 3000:3000

# Access backend API
kubectl port-forward svc/my-release-ctao-data-explorer-backend 8000:8000
```

Then visit:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

## Production Considerations

1. **Security**:
   - Change default passwords in `values.yaml`
   - Use Kubernetes secrets for sensitive data
   - Enable TLS/HTTPS with proper certificates

2. **Persistence**:
   - Enable PostgreSQL persistence for production
   - Configure appropriate storage classes
   - Set up regular database backups

3. **Scaling**:
   - Enable HPA for backend and frontend
   - Configure resource limits appropriately
   - Consider using Redis persistence if needed

4. **Monitoring**:
   - Integrate with Prometheus/Grafana
   - Set up logging aggregation
   - Configure alerting rules

## Troubleshooting

### Check pod status
```bash
kubectl get pods -l app.kubernetes.io/instance=my-release
```

### View logs
```bash
kubectl logs -l app.kubernetes.io/component=backend
kubectl logs -l app.kubernetes.io/component=frontend
```

### Debug backend connection
```bash
kubectl exec -it deployment/my-release-ctao-data-explorer-backend -- sh
```

## License

This project is licensed under the terms specified in the LICENSE file.
