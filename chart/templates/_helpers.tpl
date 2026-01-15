{{/*
Expand the name of the chart.
*/}}
{{- define "ctao-data-explorer.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "ctao-data-explorer.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "ctao-data-explorer.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "ctao-data-explorer.labels" -}}
helm.sh/chart: {{ include "ctao-data-explorer.chart" . }}
{{ include "ctao-data-explorer.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "ctao-data-explorer.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ctao-data-explorer.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "ctao-data-explorer.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "ctao-data-explorer.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
PostgreSQL host
*/}}
{{- define "ctao-data-explorer.postgresql.host" -}}
{{- printf "%s-postgresql" (include "ctao-data-explorer.fullname" .) }}
{{- end }}

{{/*
Redis host
*/}}
{{- define "ctao-data-explorer.redis.host" -}}
{{- printf "%s-redis-master" (include "ctao-data-explorer.fullname" .) }}
{{- end }}

{{/*
Database URL
*/}}
{{- define "ctao-data-explorer.databaseUrl" -}}
{{- printf "postgresql+asyncpg://%s:%s@%s:%d/%s" .Values.backend.env.POSTGRES_USER .Values.backend.env.POSTGRES_PASSWORD (include "ctao-data-explorer.postgresql.host" .) (int .Values.postgresql.service.port) .Values.backend.env.POSTGRES_DB }}
{{- end }}

{{/*
Redis URL
*/}}
{{- define "ctao-data-explorer.redisUrl" -}}
{{- printf "redis://%s:%d/0" (include "ctao-data-explorer.redis.host" .) (int .Values.redis.service.port) }}
{{- end }}
