# Grosint Backend Monitoring Stack

This directory contains the monitoring stack configuration for the Grosint Backend application using Grafana, Loki, Prometheus, and Promtail.

## Architecture

- **Grafana**: Visualization and dashboards
- **Loki**: Log aggregation and storage
- **Prometheus**: Metrics collection and storage
- **Promtail**: Log shipping agent
- **Node Exporter**: System metrics
- **Nginx Exporter**: Nginx metrics

## Services

### Grafana (Port 3000)

- **URL**: <http://localhost:3000>
- **Default Credentials**: admin/admin123
- **Purpose**: Visualize metrics and logs from Prometheus and Loki

### Prometheus (Port 9090)

- **URL**: <http://localhost:9090>
- **Purpose**: Collect and store metrics from various sources

### Loki (Port 3100)

- **URL**: <http://localhost:3100>
- **Purpose**: Store and query logs from Promtail

### Promtail

- **Purpose**: Ship logs from application and Nginx to Loki

## Log Sources

1. **Application Logs**: `/opt/grosint-backend/logs/app-*.log`
   - JSON format in production
   - Structured with timestamp, level, logger, message, client_ip, etc.

2. **Nginx Access Logs**: `/var/log/nginx/access.log`
   - JSON format with request details, status codes, response times

3. **Nginx Error Logs**: `/var/log/nginx/error.log`
   - Standard Nginx error format

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

- Change default Grafana password in production
- Consider restricting access to monitoring ports
- Use HTTPS for external access
- Regular backup of Grafana dashboards and configurations
