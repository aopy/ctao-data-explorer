from prometheus_client import Counter

TOKEN_REFRESH_FAILURES = Counter(
    "auth_token_refresh_failures_total",
    "Number of failed IAM access-token refresh attempts",
    ["reason"],
)
