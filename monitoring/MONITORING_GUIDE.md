# 📊 Grosint Backend Monitoring & Analysis Tools - Complete Guide

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Tools Overview](#tools-overview)
4. [Grafana - Visualization Platform](#1-grafana---visualization-platform)
5. [Prometheus - Metrics Collection](#2-prometheus---metrics-collection)
6. [Loki - Log Aggregation](#3-loki---log-aggregation)
7. [Promtail - Log Shipper](#4-promtail---log-shipper)
8. [Node Exporter - System Metrics](#5-node-exporter---system-metrics)
9. [Nginx Exporter - Nginx Metrics](#6-nginx-exporter---nginx-metrics)
10. [Dashboards](#dashboards)
11. [Common Workflows](#common-workflows)
12. [Query Reference](#query-reference)
13. [Troubleshooting](#troubleshooting)

---

## Overview

The Grosint Backend monitoring stack provides comprehensive observability for your application, infrastructure, and services. It consists of:

- **Grafana**: Unified visualization platform for metrics and logs
- **Prometheus**: Time-series metrics database
- **Loki**: Log aggregation system
- **Promtail**: Log collection agent
- **Node Exporter**: System resource metrics
- **Nginx Exporter**: Nginx performance metrics

### Architecture Flow

```
┌─────────────────┐
│  Application    │──┐
│  (Port 8000)    │  │
└─────────────────┘  │
                     │
┌─────────────────┐  │    ┌──────────┐    ┌──────────┐
│  Nginx          │──┼───▶│ Promtail │───▶│   Loki   │
│  (Port 80/443)  │  │    └──────────┘    └──────────┘
└─────────────────┘  │                          │
                     │                          │
┌─────────────────┐  │                          ▼
│  System         │  │                    ┌──────────┐
│  (Node Exp.)    │──┼───────────────────▶│ Grafana  │
└─────────────────┘  │                    │  (UI)    │
                     │                    └──────────┘
┌─────────────────┐  │                          ▲
│  Nginx Exporter │──┼──────────────────────────┘
└─────────────────┘  │
                     │
┌─────────────────┐  │
│  Prometheus     │──┘
│  (Metrics DB)   │
└─────────────────┘
```

---

## Quick Start

### 1. Start the Monitoring Stack

```bash
# Using systemd service (recommended)
sudo systemctl start grosint-monitoring
sudo systemctl status grosint-monitoring

# Or using Docker Compose directly
cd /opt/grosint-monitoring
docker-compose -f docker-compose.logs.yml up -d
```

### 2. Access Grafana

- **URL**: `http://your-domain:3000` or `http://localhost:3000`
- **Username**: `admin`
- **Password**: Set via `GRAFANA_ADMIN_PASSWORD` environment variable

### 3. Verify All Services

```bash
# Check all containers are running
docker ps | grep grosint

# Health checks
curl http://localhost:3000/api/health  # Grafana
curl http://localhost:9090/-/healthy  # Prometheus
curl http://localhost:3100/ready       # Loki
```

---

## Tools Overview

| Tool | Port | Access URL | Purpose | When to Use |
|------|------|------------|---------|-------------|
| **Grafana** | 3000 | `http://domain:3000` | Visualization & Dashboards | Daily monitoring, troubleshooting, analysis |
| **Prometheus** | 9090 | `http://domain:9090` | Metrics Database | Query metrics, check targets, debug |
| **Loki** | 3100 | `http://domain:3100` | Log Storage | Query logs via API (use Grafana for UI) |
| **Promtail** | 9080 | N/A (internal) | Log Shipper | Check log collection status |
| **Node Exporter** | 9100 | `http://domain:9100/metrics` | System Metrics | Monitor server resources |
| **Nginx Exporter** | 9113 | `http://domain:9113/metrics` | Nginx Metrics | Monitor web server performance |

---

## 1. Grafana - Visualization Platform

### Access

- **URL**: `http://your-domain:3000` or `http://localhost:3000`
- **Username**: `admin`
- **Password**: From `GRAFANA_ADMIN_PASSWORD` environment variable

### What It Provides

- **Pre-built Dashboards**: System metrics, application performance, Nginx statistics
- **Ad-hoc Queries**: Explore metrics (PromQL) and logs (LogQL) interactively
- **Alerting**: Set up alerts based on metrics or log patterns
- **Data Sources**: Pre-configured Prometheus and Loki connections

### When to Use

- **Daily Monitoring**: Check dashboards for system health
- **Troubleshooting**: Investigate errors, performance issues, or anomalies
- **Analysis**: Understand traffic patterns, resource usage, error rates
- **Alerting**: Set up notifications for critical issues

### How to Use

#### A. View Pre-built Dashboards

1. **Login** to Grafana
2. Navigate to **Dashboards** → **Browse**
3. Open **"Grosint Backend Monitoring"** dashboard
4. **Panels Available**:
   - System CPU, Memory, Disk Usage
   - Nginx Request Rate and Status Codes
   - Application Response Times
   - Error Rates
   - Active Connections

#### B. Explore Metrics (PromQL)

1. Click **Explore** (compass icon) in left sidebar
2. Select **Prometheus** as data source
3. Enter PromQL queries:

```promql
# Request rate per second
rate(nginx_http_requests_total[5m])

# CPU usage percentage
100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memory usage percentage
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100

# Disk usage percentage
(1 - (node_filesystem_avail_bytes / node_filesystem_size_bytes)) * 100

# Error rate (5xx responses)
rate(nginx_http_requests_total{status=~"5.."}[5m])
```

4. Click **Run query** to see results
5. Switch visualization: **Graph**, **Table**, **Stat**, etc.

#### C. Explore Logs (LogQL)

1. Click **Explore** in left sidebar
2. Select **Loki** as data source
3. Enter LogQL queries:

```logql
# All application errors
{job="grosint-app"} |= "ERROR"

# Nginx 4xx/5xx errors
{job="nginx", log_type="access"} | json | status >= 400

# Errors from specific module
{job="grosint-app"} | json | module="auth"

# Logs from specific IP
{job="grosint-app"} | json | client_ip="192.168.1.100"

# Recent errors with context
{job="grosint-app"} |= "ERROR" | json
```

4. Click **Run query** to see log entries
5. Click on log lines to expand details

#### D. Create Custom Dashboards

1. Click **+** → **Create Dashboard**
2. Click **Add visualization**
3. Select **Prometheus** or **Loki** data source
4. Enter query and configure visualization
5. Save dashboard

### Useful Features

- **Time Range Selector**: Top right - select time period (Last 5 minutes, Last 1 hour, etc.)
- **Refresh**: Auto-refresh dashboards (5s, 10s, 30s, 1m, 5m, etc.)
- **Annotations**: Mark events on graphs (deployments, incidents)
- **Variables**: Create dynamic dashboards with dropdown filters

---

## 2. Prometheus - Metrics Collection

### Access

- **URL**: `http://your-domain:9090` or `http://localhost:9090`
- **No authentication** (restrict access via firewall)

### What It Provides

- **Metrics Storage**: Time-series database storing all metrics
- **Query Interface**: PromQL query language
- **Target Status**: Monitor which services are being scraped
- **Alerts**: Alert rule evaluation (if configured)

### When to Use

- **Check Target Health**: Verify all services are being monitored
- **Raw Metrics Query**: Test PromQL queries before adding to Grafana
- **Debug Metrics**: Investigate why metrics aren't appearing
- **Metrics Endpoint**: Direct access to metrics data

### How to Use

#### A. Check Scrape Targets

1. Navigate to **Status** → **Targets**
2. Verify all targets show **State: UP**:
   - `prometheus` (self-monitoring)
   - `node-exporter` (system metrics)
   - `nginx-exporter` (nginx metrics)
   - `grosint-backend` (application metrics)
   - `nginx-status` (nginx direct metrics)

3. If any target is **DOWN**:
   - Check if service is running
   - Verify network connectivity
   - Check firewall rules

#### B. Query Metrics

1. Go to **Graph** tab
2. Enter PromQL query in query box:

```promql
# Check if all targets are up (1 = up, 0 = down)
up

# Request rate
rate(nginx_http_requests_total[5m])

# CPU usage
100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memory available
node_memory_MemAvailable_bytes / 1024 / 1024 / 1024  # GB

# Disk free space
node_filesystem_avail_bytes / 1024 / 1024 / 1024  # GB
```

3. Click **Execute**
4. View results as **Graph** or **Console** (table)

#### C. View Metrics Endpoint

```bash
# Query via API
curl 'http://localhost:9090/api/v1/query?query=up'

# Query range (time series)
curl 'http://localhost:9090/api/v1/query_range?query=rate(nginx_http_requests_total[5m])&start=2024-01-01T00:00:00Z&end=2024-01-01T23:59:59Z&step=15s'
```

### Metrics Sources

Prometheus scrapes metrics from:

1. **FastAPI Application** (`localhost:8000/metrics`)
   - HTTP request metrics
   - Response times
   - Error counts

2. **Node Exporter** (`node-exporter:9100/metrics`)
   - CPU, memory, disk, network

3. **Nginx Exporter** (`nginx-exporter:9113/metrics`)
   - Nginx connections, requests

4. **Prometheus** (self-monitoring)
   - Prometheus performance metrics

---

## 3. Loki - Log Aggregation

### Access

- **API URL**: `http://your-domain:3100` or `http://localhost:3100`
- **No Web UI** - Use Grafana Explore for visualization
- **Query API**: `/loki/api/v1/query` and `/loki/api/v1/query_range`

### What It Provides

- **Centralized Log Storage**: All application and Nginx logs in one place
- **LogQL Query Language**: Powerful log querying similar to PromQL
- **Label-based Indexing**: Fast queries using labels (job, level, status, etc.)
- **30-day Retention**: Logs kept for 30 days automatically

### When to Use

- **Debug Errors**: Find specific error messages and stack traces
- **Track User Activity**: Follow requests from specific IPs or users
- **Performance Analysis**: Analyze slow requests from logs
- **Security Investigation**: Review access patterns and suspicious activity
- **Correlate with Metrics**: Combine log analysis with metric data

### How to Use

#### A. Query Logs via Grafana (Recommended)

1. Open Grafana → **Explore**
2. Select **Loki** data source
3. Enter LogQL queries (see examples below)
4. View results in timeline or table format

#### B. Query Logs via API

```bash
# Query recent logs
curl "http://localhost:3100/loki/api/v1/query_range?query={job=\"grosint-app\"}&limit=100"

# Query with time range
curl "http://localhost:3100/loki/api/v1/query_range?query={job=\"nginx\"}&start=2024-01-01T00:00:00Z&end=2024-01-01T23:59:59Z&limit=1000"

# Query errors only
curl "http://localhost:3100/loki/api/v1/query_range?query={job=\"grosint-app\"} |= \"ERROR\"&limit=50"
```

### Log Sources

Loki stores logs from:

1. **Application Logs** (`/opt/grosint-backend/logs/app-*.log`)
   - JSON format in production
   - Contains: timestamp, level, logger, message, client_ip, module, function

2. **Nginx Access Logs** (`/var/log/nginx/access*.log`)
   - JSON format
   - Contains: time, remote_addr, request, status, response_time, etc.

3. **Nginx Error Logs** (`/var/log/nginx/error*.log`)
   - Standard nginx format
   - Contains: timestamp, level, message, client, server, request

### Log Labels

Logs are automatically labeled for easy filtering:

- `job`: `grosint-app` or `nginx`
- `host`: Server hostname
- `level`: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- `log_type`: `access` or `error` (for nginx)
- `status`: HTTP status code (for nginx access logs)
- `request_method`: `GET`, `POST`, etc. (for nginx)

---

## 4. Promtail - Log Shipper

### Access

- **No Web UI** - Internal service
- **Port 9080**: Internal only (not exposed)

### What It Provides

- **Log Collection**: Reads log files from disk
- **Log Parsing**: Extracts structured data from logs
- **Label Addition**: Adds metadata labels to logs
- **Log Shipping**: Sends logs to Loki

### When to Use

- **Troubleshooting**: Check if logs are being collected
- **Configuration**: Modify log sources or parsing rules
- **Debugging**: Verify Promtail is reading log files correctly

### How to Use

#### A. Check Promtail Status

```bash
# View Promtail container logs
docker logs grosint-promtail

# Or using alias
promtail-logs

# Check if Promtail is running
docker ps | grep promtail
```

#### B. Verify Log Collection

```bash
# Check positions file (tracks where Promtail left off)
docker exec grosint-promtail cat /var/lib/promtail/positions.yaml

# View Promtail configuration
docker exec grosint-promtail cat /etc/promtail/config.yml
```

#### C. Monitor Log Files Being Read

Promtail reads from:

- `/opt/grosint-backend/logs/app-*.log` (application logs)
- `/var/log/nginx/access*.log` (nginx access logs)
- `/var/log/nginx/error*.log` (nginx error logs)

Verify these files exist and are readable:

```bash
# Check log files
ls -lh /opt/grosint-backend/logs/
ls -lh /var/log/nginx/

# Check permissions
sudo ls -ld /opt/grosint-backend/logs
sudo ls -ld /var/log/nginx
```

### Configuration

Promtail configuration: `/opt/grosint-monitoring/monitoring/promtail/promtail.yml`

Key settings:
- **Scrape configs**: Defines which log files to read
- **Pipeline stages**: Parses logs (JSON, regex, labels)
- **Client URL**: Where to send logs (Loki)

---

## 5. Node Exporter - System Metrics

### Access

- **Metrics Endpoint**: `http://your-domain:9100/metrics`
- **No Web UI** - Use Prometheus/Grafana to visualize

### What It Provides

- **CPU Metrics**: Usage per core, idle time, I/O wait
- **Memory Metrics**: Total, available, used, cached, buffers
- **Disk Metrics**: I/O operations, space usage, read/write rates
- **Network Metrics**: Bytes sent/received, packets, errors
- **System Metrics**: Load average, uptime, processes

### When to Use

- **Resource Monitoring**: Track CPU, memory, disk usage
- **Capacity Planning**: Identify resource constraints
- **Performance Analysis**: Correlate system metrics with application performance
- **Alerting**: Set alerts for high CPU, low memory, disk full

### How to Use

#### A. View Raw Metrics

```bash
# Get all metrics
curl http://localhost:9100/metrics

# Filter specific metrics
curl http://localhost:9100/metrics | grep node_cpu
curl http://localhost:9100/metrics | grep node_memory
```

#### B. Query in Prometheus/Grafana

```promql
# CPU usage percentage
100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memory usage percentage
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100

# Memory available in GB
node_memory_MemAvailable_bytes / 1024 / 1024 / 1024

# Disk usage percentage
(1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})) * 100

# Disk I/O read rate (bytes/sec)
rate(node_disk_read_bytes_total[5m])

# Network receive rate (bytes/sec)
rate(node_network_receive_bytes_total{device="eth0"}[5m])
```

### Key Metrics

| Metric | Description | Unit |
|--------|-------------|------|
| `node_cpu_seconds_total` | CPU time spent in each mode | seconds |
| `node_memory_MemTotal_bytes` | Total memory | bytes |
| `node_memory_MemAvailable_bytes` | Available memory | bytes |
| `node_filesystem_size_bytes` | Filesystem size | bytes |
| `node_filesystem_avail_bytes` | Available space | bytes |
| `node_disk_io_time_seconds_total` | Disk I/O time | seconds |
| `node_network_receive_bytes_total` | Network bytes received | bytes |
| `node_network_transmit_bytes_total` | Network bytes transmitted | bytes |

---

## 6. Nginx Exporter - Nginx Metrics

### Access

- **Metrics Endpoint**: `http://your-domain:9113/metrics`
- **No Web UI** - Use Prometheus/Grafana to visualize

### What It Provides

- **Request Metrics**: Total requests, requests per second
- **Connection Metrics**: Active connections, accepted connections
- **Status Codes**: Count of responses by status code
- **Upstream Metrics**: Backend server health and response times

### When to Use

- **Performance Monitoring**: Track request rates and response times
- **Capacity Planning**: Monitor connection counts
- **Error Analysis**: Track 4xx/5xx error rates
- **Load Balancing**: Monitor upstream server health

### Prerequisites

Nginx must have the status module enabled. Add to nginx config:

```nginx
location /nginx_status {
    stub_status on;
    access_log off;
    allow 127.0.0.1;
    deny all;
}
```

### How to Use

#### A. View Raw Metrics

```bash
# Get all nginx metrics
curl http://localhost:9113/metrics

# Filter specific metrics
curl http://localhost:9113/metrics | grep nginx_http_requests
curl http://localhost:9113/metrics | grep nginx_connections
```

#### B. Query in Prometheus/Grafana

```promql
# Request rate (requests per second)
rate(nginx_http_requests_total[5m])

# Active connections
nginx_connections_active

# Total connections accepted
nginx_connections_accepted

# Error rate (5xx responses per second)
rate(nginx_http_requests_total{status=~"5.."}[5m])

# 4xx error rate
rate(nginx_http_requests_total{status=~"4.."}[5m])

# Requests by status code
sum by (status) (rate(nginx_http_requests_total[5m]))
```

### Key Metrics

| Metric | Description | Unit |
|--------|-------------|------|
| `nginx_http_requests_total` | Total HTTP requests | count |
| `nginx_connections_active` | Active connections | count |
| `nginx_connections_accepted` | Total connections accepted | count |
| `nginx_connections_handled` | Total connections handled | count |
| `nginx_connections_reading` | Connections reading | count |
| `nginx_connections_writing` | Connections writing | count |
| `nginx_connections_waiting` | Connections waiting | count |

---

## Dashboards

### Pre-built Dashboard: "Grosint Backend Monitoring"

**Location**: Grafana → Dashboards → "Grosint Backend Monitoring"

#### Panels Included

1. **System Metrics**
   - CPU Usage (%)
   - Memory Usage (%)
   - Disk Usage (%)
   - Network I/O (bytes/sec)

2. **Nginx Metrics**
   - Request Rate (requests/sec)
   - Status Code Distribution (2xx, 4xx, 5xx)
   - Active Connections
   - Response Time (p95, p99)

3. **Application Metrics**
   - Request Rate
   - Error Rate
   - Response Time

4. **Logs Summary**
   - Error Count (from Loki)
   - Recent Errors (log entries)

### Creating Custom Dashboards

1. **Create New Dashboard**
   - Click **+** → **Create Dashboard**
   - Click **Add visualization**

2. **Add Panels**
   - Select data source (Prometheus or Loki)
   - Enter query
   - Configure visualization type (Graph, Stat, Table, etc.)
   - Set panel title and description

3. **Organize Panels**
   - Drag panels to rearrange
   - Resize panels
   - Group related panels in rows

4. **Add Variables** (Optional)
   - Dashboard settings → Variables
   - Create dropdown filters (e.g., select host, environment)

5. **Save Dashboard**
   - Click **Save** (top right)
   - Enter dashboard name
   - Choose folder

### Dashboard Best Practices

- **Group Related Metrics**: Put CPU, memory, disk together
- **Use Appropriate Visualizations**:
  - Time series → Graph
  - Single values → Stat
  - Multiple values → Table
- **Set Thresholds**: Color-code values (green/yellow/red)
- **Add Annotations**: Mark deployments, incidents
- **Set Refresh Intervals**: Auto-refresh for real-time monitoring

---

## Common Workflows

### 1. Investigate High Error Rate

**Scenario**: Dashboard shows spike in 5xx errors

**Steps**:

1. **Check Grafana Dashboard**
   - View "Nginx Status Codes" panel
   - Identify time of spike
   - Note error rate magnitude

2. **Query Error Logs in Grafana Explore (Loki)**
   ```logql
   {job="nginx", log_type="access"} | json | status >= 500
   ```
   - Review error patterns
   - Identify affected endpoints

3. **Correlate with Application Logs**
   ```logql
   {job="grosint-app"} |= "ERROR"
   ```
   - Find application errors at same time
   - Check for exceptions or failures

4. **Check System Resources**
   ```promql
   100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
   ```
   - Verify if high CPU/memory caused errors

5. **Review Request Patterns**
   ```promql
   rate(nginx_http_requests_total[5m])
   ```
   - Check if traffic spike caused overload

### 2. Monitor System Resources

**Scenario**: Ensure server has adequate resources

**Steps**:

1. **View System Dashboard**
   - Open "Grosint Backend Monitoring" dashboard
   - Check CPU, Memory, Disk panels

2. **Set Up Alerts** (Optional)
   - CPU > 80% for 5 minutes
   - Memory < 20% available
   - Disk > 90% full

3. **Track Trends**
   - Review historical data
   - Identify growth patterns
   - Plan capacity upgrades

### 3. Debug Application Issue

**Scenario**: User reports error, need to investigate

**Steps**:

1. **Search Application Logs**
   ```logql
   {job="grosint-app"} |= "ERROR"
   ```
   - Filter by time range
   - Look for error messages

2. **Filter by Module/Function**
   ```logql
   {job="grosint-app"} | json | module="auth" |= "ERROR"
   ```

3. **Check Specific User/IP**
   ```logql
   {job="grosint-app"} | json | client_ip="192.168.1.100"
   ```

4. **Correlate with Metrics**
   - Check response times during error
   - Verify request rates
   - Review error rates

### 4. Analyze Traffic Patterns

**Scenario**: Understand application usage patterns

**Steps**:

1. **View Request Rate**
   ```promql
   rate(nginx_http_requests_total[5m])
   ```
   - Identify peak hours
   - Find traffic patterns

2. **Analyze Status Codes**
   ```promql
   sum by (status) (rate(nginx_http_requests_total[5m]))
   ```
   - Check success vs error rates
   - Monitor 4xx/5xx trends

3. **Review Response Times**
   ```promql
   histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
   ```
   - Identify slow endpoints
   - Track performance over time

### 5. Security Investigation

**Scenario**: Suspicious activity detected

**Steps**:

1. **Review Access Logs**
   ```logql
   {job="nginx", log_type="access"} | json | status >= 400
   ```
   - Find failed requests
   - Identify suspicious IPs

2. **Track Specific IP**
   ```logql
   {job="nginx", log_type="access"} | json | remote_addr="1.2.3.4"
   ```
   - Review all requests from IP
   - Check for patterns

3. **Check Error Logs**
   ```logql
   {job="nginx", log_type="error"}
   ```
   - Review nginx errors
   - Find security-related messages

---

## Query Reference

### PromQL (Prometheus Query Language)

#### Basic Queries

```promql
# All metrics with label
nginx_http_requests_total

# Filter by label
nginx_http_requests_total{status="200"}

# Multiple label filters
nginx_http_requests_total{status=~"5..", method="GET"}

# Rate (per second)
rate(nginx_http_requests_total[5m])

# Increase (total increase over time)
increase(nginx_http_requests_total[1h])

# Sum by label
sum by (status) (nginx_http_requests_total)

# Average
avg(node_cpu_seconds_total)

# Percentile (95th)
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

#### System Metrics

```promql
# CPU usage %
100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memory usage %
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100

# Memory available (GB)
node_memory_MemAvailable_bytes / 1024 / 1024 / 1024

# Disk usage %
(1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})) * 100

# Disk I/O rate
rate(node_disk_io_time_seconds_total[5m])

# Network receive (bytes/sec)
rate(node_network_receive_bytes_total{device="eth0"}[5m])
```

#### Application Metrics

```promql
# Request rate
rate(nginx_http_requests_total[5m])

# Error rate (5xx)
rate(nginx_http_requests_total{status=~"5.."}[5m])

# Success rate (2xx)
rate(nginx_http_requests_total{status=~"2.."}[5m])

# Active connections
nginx_connections_active

# Response time (p95)
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

### LogQL (Loki Query Language)

#### Basic Queries

```logql
# All logs from job
{job="grosint-app"}

# Multiple label filters
{job="nginx", log_type="access", status="500"}

# Text search
{job="grosint-app"} |= "ERROR"

# Exclude text
{job="grosint-app"} != "DEBUG"

# Regex match
{job="grosint-app"} |~ "error|exception|failure"

# JSON parsing
{job="grosint-app"} | json

# Filter by JSON field
{job="grosint-app"} | json | level="ERROR"

# Extract fields
{job="nginx"} | json | status >= 400
```

#### Application Log Queries

```logql
# All errors
{job="grosint-app"} |= "ERROR"

# Errors from specific module
{job="grosint-app"} | json | module="auth" |= "ERROR"

# Errors from specific IP
{job="grosint-app"} | json | client_ip="192.168.1.100" |= "ERROR"

# Recent errors with context
{job="grosint-app"} |= "ERROR" | json

# Count errors
count_over_time({job="grosint-app"} |= "ERROR" [5m])
```

#### Nginx Log Queries

```logql
# All access logs
{job="nginx", log_type="access"}

# 4xx/5xx errors
{job="nginx", log_type="access"} | json | status >= 400

# 5xx errors only
{job="nginx", log_type="access"} | json | status >= 500

# Slow requests (>1 second)
{job="nginx", log_type="access"} | json | request_time > 1.0

# Requests from specific IP
{job="nginx", log_type="access"} | json | remote_addr="1.2.3.4"

# Error logs
{job="nginx", log_type="error"}

# Error logs by level
{job="nginx", log_type="error"} | level="error"
```

#### Advanced Queries

```logql
# Rate of errors (errors per second)
rate({job="grosint-app"} |= "ERROR" [5m])

# Top error messages
topk(10, count_over_time({job="grosint-app"} |= "ERROR" [1h]))

# Errors by module
sum by (module) (count_over_time({job="grosint-app"} | json | level="ERROR" [1h]))
```

---

## Troubleshooting

### Services Not Starting

```bash
# Check service status
sudo systemctl status grosint-monitoring

# Check Docker containers
docker ps -a | grep grosint

# View container logs
docker logs grosint-grafana
docker logs grosint-prometheus
docker logs grosint-loki
docker logs grosint-promtail
```

### Port Conflicts

```bash
# Check if ports are in use
sudo netstat -tlnp | grep -E "3000|9090|3100|9100|9113"

# Or using ss
sudo ss -tlnp | grep -E "3000|9090|3100|9100|9113"

# Kill process on port (if needed)
sudo fuser -k 3000/tcp
```

### Logs Not Appearing

```bash
# Check if log files exist
ls -lh /opt/grosint-backend/logs/
ls -lh /var/log/nginx/

# Check file permissions
sudo ls -ld /opt/grosint-backend/logs
sudo ls -ld /var/log/nginx

# Check Promtail is reading files
docker logs grosint-promtail | grep -i error

# Check Promtail positions
docker exec grosint-promtail cat /var/lib/promtail/positions.yaml
```

### Metrics Not Scraping

```bash
# Check Prometheus targets
# Go to http://localhost:9090/targets

# Verify services are accessible
curl http://localhost:8000/metrics  # Application
curl http://localhost:9100/metrics   # Node Exporter
curl http://localhost:9113/metrics   # Nginx Exporter

# Check Prometheus config
docker exec grosint-prometheus cat /etc/prometheus/prometheus.yml
```

### Grafana Not Accessible

```bash
# Check Grafana container
docker ps | grep grafana

# Check Grafana logs
docker logs grosint-grafana

# Verify password is set
docker exec grosint-grafana env | grep GRAFANA_ADMIN_PASSWORD

# Test Grafana API
curl http://localhost:3000/api/health
```

### High Resource Usage

```bash
# Check container resource usage
docker stats

# Check system resources
htop
free -h
df -h

# Check Loki storage
docker exec grosint-loki du -sh /loki

# Check Prometheus storage
docker exec grosint-prometheus du -sh /prometheus
```

### Reset Monitoring Stack

```bash
# Stop all services
sudo systemctl stop grosint-monitoring
# Or
cd /opt/grosint-monitoring
docker-compose -f docker-compose.logs.yml down

# Remove volumes (WARNING: Deletes all data)
docker volume rm grosint-prometheus_data
docker volume rm grosint-grafana_data
docker volume rm grosint-loki_data

# Restart services
sudo systemctl start grosint-monitoring
```

---

## Quick Reference Commands

### Service Management

```bash
# Start monitoring stack
sudo systemctl start grosint-monitoring

# Stop monitoring stack
sudo systemctl stop grosint-monitoring

# Restart monitoring stack
sudo systemctl restart grosint-monitoring

# Check status
sudo systemctl status grosint-monitoring

# View logs
monitoring-logs
```

### Individual Service Logs

```bash
grafana-logs      # Grafana logs
prometheus-logs   # Prometheus logs
loki-logs         # Loki logs
promtail-logs     # Promtail logs
```

### Health Checks

```bash
# Application
curl http://localhost:8000/api/health

# Grafana
curl http://localhost:3000/api/health

# Prometheus
curl http://localhost:9090/-/healthy

# Loki
curl http://localhost:3100/ready

# Node Exporter
curl http://localhost:9100/metrics | head -5

# Nginx Exporter
curl http://localhost:9113/metrics | head -5
```

### Useful Aliases

All these aliases are available (from setup.sh):

```bash
grosint-status      # Check application status
grosint-logs        # View application logs
monitoring-status   # Check monitoring stack status
monitoring-logs     # View monitoring stack logs
nginx-logs          # View nginx logs
```

---

## Security Best Practices

1. **Grafana Password**: Use strong password via `GRAFANA_ADMIN_PASSWORD`
2. **Firewall Rules**: Restrict access to monitoring ports
3. **HTTPS**: Use HTTPS for external Grafana access
4. **Network Isolation**: Keep monitoring stack on internal network
5. **Regular Updates**: Keep Docker images updated
6. **Backup Dashboards**: Export and backup Grafana dashboards regularly

---

## Support & Resources

- **Grafana Documentation**: https://grafana.com/docs/
- **Prometheus Documentation**: https://prometheus.io/docs/
- **Loki Documentation**: https://grafana.com/docs/loki/
- **LogQL Guide**: https://grafana.com/docs/loki/latest/logql/
- **PromQL Guide**: https://prometheus.io/docs/prometheus/latest/querying/basics/

---

**Last Updated**: 2024-01-05
**Version**: 1.0
