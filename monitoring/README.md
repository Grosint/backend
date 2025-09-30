# Grosint Backend Monitoring Stack

This directory contains a production-ready observability stack for the Grosint Backend using Grafana, Loki, Prometheus, and Promtail. It provides logs, metrics, dashboards, and alerting primitives with minimal operational overhead.

## Architecture

- **Grafana**: Visualization and dashboards (view both metrics and logs)
- **Loki**: Log aggregation and storage (queried via LogQL)
- **Prometheus**: Metrics collection and storage (queried via PromQL)
- **Promtail**: Log shipping agent (tails files, parses, labels, ships to Loki)
- **Node Exporter**: System metrics (CPU, memory, disk, network)
- **Nginx Exporter**: Nginx reverse proxy metrics (connections, requests)

Flow:

- Backend/Nginx → logs → Promtail → Loki → Grafana (Explore)
- Backend/Nginx/Node Exporter → metrics → Prometheus → Grafana (Dashboards)

## Services

### Grafana (Port 3000)

- **URL**: <http://localhost:3000>
- **Credentials**: admin/[password from GRAFANA_ADMIN_PASSWORD environment variable]
- **Purpose**: Visualize metrics and logs from Prometheus and Loki
- Use Dashboards for metrics, Explore for ad-hoc metrics/logs queries
- **Security**: Password is set via environment variable for security

### Prometheus (Port 9090)

- **URL**: <http://localhost:9090>
- **Purpose**: Collect and store metrics from various sources; raw query UI, target status

### Loki (Port 3100)

- **URL**: <http://localhost:3100>
- **Purpose**: Store and query logs from Promtail; no UI (use Grafana Explore)

### Promtail

- **Purpose**: Ship logs from application and Nginx to Loki
- Reads:
  - Application: `/opt/grosint-backend/logs/app-*.log` (text in dev, JSON in prod)
  - Nginx access: `/var/log/nginx/access*.log` (JSON via log_format)
  - Nginx error: `/var/log/nginx/error*.log` (parsed via regex stages)
- Adds useful labels (`job`, `host`, `log_type`, `status`, `request_method`, etc.)

## Log Sources

1. **Application Logs**: `/opt/grosint-backend/logs/app-*.log`
   - Text in development; JSON in production for better parsing
   - Contains timestamp, level, logger, message, client_ip, etc.

2. **Nginx Access Logs**: `/var/log/nginx/access*.log`
   - JSON format with request details, status codes, response times

3. **Nginx Error Logs**: `/var/log/nginx/error*.log`
   - Standard Nginx error format; Promtail extracts client/server/request/host fields

## Metrics Sources

1. **FastAPI Application**: <http://localhost:8000/metrics>
   - Request rates, response times, error rates
   - Custom application metrics

2. **System Metrics**: Node Exporter
   - CPU, memory, disk usage
   - Network statistics

3. **Nginx Metrics**: Nginx Exporter
   - Request rates, active connections
   - Upstream server status

## Deployment

The monitoring stack is automatically deployed during the CI/CD pipeline deployment phase.

### Manual Deployment

```bash
# Start the monitoring stack
sudo systemctl start grosint-monitoring

# Check status
sudo systemctl status grosint-monitoring

# View logs
monitoring-logs

# Stop the monitoring stack
sudo systemctl stop grosint-monitoring
```

### Docker Compose Commands

```bash
cd /opt/grosint-monitoring

# Start all services
docker-compose -f docker-compose.logs.yml up -d

# View logs
docker-compose -f docker-compose.logs.yml logs -f

# Stop all services
docker-compose -f docker-compose.logs.yml down

# Restart specific service
docker-compose -f docker-compose.logs.yml restart grafana
```

## Configuration Files

- `prometheus/prometheus.yml`: Prometheus configuration
- `loki/loki.yml`: Loki configuration
- `promtail/promtail.yml`: Promtail log shipping configuration
- `grafana/provisioning/`: Grafana datasources and dashboards
- `docker-compose.logs.yml`: Docker Compose configuration

## Useful Queries

### Grafana Log Queries (Loki)

```logql
# Application errors
{job="grosint-app"} |= "ERROR"

# Nginx 4xx/5xx errors
{job="nginx", log_type="access"} | json | status >= 400

# All logs from specific client IP
{job="grosint-app"} | json | client_ip="192.168.1.100"

# Logs from specific module
{job="grosint-app"} | json | module="auth"

# Nginx error logs by host or method
{job="nginx", log_type="error"} | host="your-domain.com"
{job="nginx", log_type="error"} | req_method="GET"
```

### Prometheus Queries

```promql
# Request rate
rate(nginx_http_requests_total[5m])

# CPU usage
100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memory usage
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100

# FastAPI request duration
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Nginx active connections (from exporter)
nginx_connections_active

# Scrape targets up
up
```

## Troubleshooting

### Check Service Status

```bash
grosint-status
```

### View Service Logs

```bash
# Application logs
grosint-logs

# Monitoring stack logs
monitoring-logs

# Specific service logs
grafana-logs
prometheus-logs
loki-logs
promtail-logs
```

### Common Issues

1. **Port conflicts**: Ensure ports 3000, 9090, 3100, 9100, 9113 are available
2. **Permission issues**: Check file permissions on log directories
3. **Docker issues**: Ensure Docker service is running and user is in docker group
4. **Memory issues**: Monitor system resources, especially for Loki storage

### Health Checks

```bash
# Application health
curl http://localhost:8000/api/health

# Grafana health
curl http://localhost:3000/api/health

# Prometheus health
curl http://localhost:9090/-/healthy

# Loki health
curl http://localhost:3100/ready
```

## Security Notes

- **Grafana password is now set via environment variable** (`GRAFANA_ADMIN_PASSWORD`)
- Use a strong, unique password for production environments
- Consider restricting access to monitoring ports
- Use HTTPS for external access
- Regular backup of Grafana dashboards and configurations

## Environment Setup

1. **Copy the environment template**:
   ```bash
   cp monitoring/env.example monitoring/.env
   ```

2. **Set a secure Grafana password**:
   ```bash
   # Generate a secure password
   openssl rand -base64 32

   # Or using Python
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

3. **Start the monitoring stack**:
   ```bash
   cd monitoring
   source .env
   docker compose -f ../docker-compose.logs.yml up -d
   ```

## Retention and disk management

- Application and Nginx logs rotate daily and keep 30 days (compressed) via logrotate.
- Loki retention is set to 30 days in `loki.yml` (`limits_config.retention_period`).
- Prometheus retention is set to 30 days via `--storage.tsdb.retention.time=30d`.
- Use `grosint-logs-status` to inspect sizes and rotation status.

## How to view everything (quick guide)

- Dashboards: Grafana → Dashboards → “Grosint Backend Monitoring”.
- Metrics ad-hoc: Grafana → Explore → Data source: Prometheus → write PromQL.
- Logs ad-hoc: Grafana → Explore → Data source: Loki → run LogQL queries.
- Raw Prometheus UI: <http://localhost:9090> (targets, rules, queries).

## Typical workflows

- Investigate spike in 5xx:
  1) Grafana dashboard → Nginx request rate/5xx panels
  2) Drill down to logs: Explore → Loki → `{job="nginx", log_type="access"} | json | status >= 500`
  3) Correlate with app errors: `{job="grosint-app"} |= "ERROR"`

- Check VM pressure:
  1) Dashboard → Node exporter panels (CPU, memory, disk)
  2) If high CPU, correlate with app latency metrics and Nginx connections
