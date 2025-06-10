# OnlyOffice Monitoring Stack

This docker-compose file provides comprehensive monitoring for your OnlyOffice deployment with health monitoring, metrics collection, and alerting.

## 🚀 Quick Start

```bash
# Start the full stack with monitoring
docker-compose -f docker-compose.workspace-managed.yml up -d

# View logs
docker-compose -f docker-compose.workspace-managed.yml logs -f onlyoffice-monitor
```

## 📊 Access Points

| Service | URL | Purpose |
|---------|-----|---------|
| **OnlyOffice** | http://localhost:1180 | Main application |
| **Grafana** | http://monitoring.local:3000 | Dashboards & Visualization |
| **Prometheus** | http://prometheus.local:9090 | Metrics & Queries |
| **Monitor API** | http://monitor.local:8090 | Custom monitoring service |
| **Traefik** | http://traefik.local:8080 | Load balancer dashboard |
| **Alertmanager** | http://alerts.local:9093 | Alert management |

**Default Credentials:**
- Grafana: `admin` / `onlyoffice123`

## 🏗️ Architecture

### Core OnlyOffice Services
- **Community Server** - Main application (with CRM auto-linking)
- **Document Server** - Document editing
- **Mail Server** - Email functionality  
- **MySQL** - Database
- **Elasticsearch** - Search & indexing
- **Control Panel** - Management interface

### Monitoring Stack
- **Prometheus** - Metrics collection & storage
- **Grafana** - Visualization dashboards
- **Loki** - Log aggregation
- **Promtail** - Log collection
- **Alertmanager** - Alert routing & management
- **Traefik** - Reverse proxy & load balancing

### Exporters & Collectors
- **Node Exporter** - Host system metrics
- **cAdvisor** - Container metrics  
- **MySQL Exporter** - Database metrics
- **Elasticsearch Exporter** - Search engine metrics
- **Custom Monitor** - OnlyOffice-specific monitoring

## 🔍 Custom Monitoring Features

### Health Monitoring
- Container status and health checks
- Service availability monitoring
- Resource usage tracking (CPU, memory, disk)
- Database connection monitoring

### CRM Auto-Linking Oversight
- **Email processing metrics** - Track emails processed for CRM linking
- **Error detection** - Monitor CRM auto-linking failures
- **Duplication detection** - Alert on duplicate email processing
- **Service status** - Monitor WebCrmMonitoringService health

### API Endpoints

```bash
# Basic health check
curl http://localhost:8090/health

# Detailed system overview
curl http://localhost:8090/health/detailed

# CRM-specific metrics
curl http://localhost:8090/metrics/crm

# Container status
curl http://localhost:8090/api/containers

# Container logs
curl http://localhost:8090/api/logs/onlyoffice-community-server
```

## 🚨 Alerting

### Pre-configured Alerts
- **Container Down** - Any monitored container stops
- **High Resource Usage** - CPU/Memory thresholds exceeded
- **Database Issues** - MySQL connectivity or performance problems
- **CRM Auto-linking Failures** - Email processing errors
- **Email Duplication** - Duplicate email detection
- **Service Health** - OnlyOffice service availability

### Alert Channels
- **Webhook** - Sent to custom monitor service
- **Email** - Configure SMTP in alertmanager/config.yml

## 📈 Key Metrics

### System Metrics
- `container_status` - Container running status
- `onlyoffice_health_status` - Service health status
- `mysql_connections_active` - Database connections
- `elasticsearch_health_score` - Search engine health

### CRM Metrics
- `crm_autolink_emails_total` - Total emails processed
- `crm_autolink_errors_total` - Auto-linking errors
- `crm_autolink_service_up` - Service availability
- `email_duplication_events_total` - Duplicate emails detected

## 🛠️ Configuration

### Environment Variables
```env
# MySQL connection
MYSQL_HOST=onlyoffice-mysql-server
MYSQL_USER=root
MYSQL_PASSWORD=my-secret-pw
MYSQL_DATABASE=onlyoffice

# Monitoring settings
CHECK_INTERVAL=30
CRM_AUTO_LINK_MONITORING=true
```

### Host File Setup
Add to `/etc/hosts` for local access:
```
127.0.0.1 monitoring.local
127.0.0.1 prometheus.local
127.0.0.1 traefik.local
127.0.0.1 alerts.local
127.0.0.1 monitor.local
127.0.0.1 onlyoffice.local
```

## 🔧 Customization

### Adding New Metrics
1. Edit `monitoring/custom/monitor.py`
2. Add Prometheus metrics definitions
3. Implement collection logic
4. Rebuild custom monitor: `docker-compose build onlyoffice-monitor`

### Custom Dashboards
1. Access Grafana at http://monitoring.local:3000
2. Create new dashboards
3. Export JSON and save to `monitoring/grafana/dashboards/`

### Alert Rules
1. Edit `monitoring/prometheus/alert_rules.yml`
2. Add new alert conditions
3. Restart Prometheus: `docker-compose restart prometheus`

## 📋 Maintenance

### Backup
```bash
# Backup monitoring configuration
tar -czf monitoring-backup.tar.gz monitoring/

# Backup Grafana dashboards
docker exec onlyoffice-grafana grafana-cli admin export-dashboard
```

### Cleanup
```bash
# Remove monitoring stack only
docker-compose -f docker-compose.workspace-managed.yml stop prometheus grafana loki
docker-compose -f docker-compose.workspace-managed.yml rm prometheus grafana loki

# Clean up volumes
docker volume prune
```

## 🐛 Troubleshooting

### Common Issues

**Grafana not loading dashboards:**
```bash
docker-compose restart grafana
docker logs onlyoffice-grafana
```

**Prometheus not scraping targets:**
```bash
# Check configuration
curl http://localhost:9090/api/v1/targets
```

**Custom monitor errors:**
```bash
docker logs onlyoffice-monitor
```

**Permission issues:**
```bash
# Fix monitoring directory permissions
sudo chown -R $(id -u):$(id -g) monitoring/
```

This monitoring stack provides comprehensive oversight of your OnlyOffice deployment with special focus on the CRM auto-linking functionality!