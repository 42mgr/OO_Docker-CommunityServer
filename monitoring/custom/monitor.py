#!/usr/bin/env python3
"""
OnlyOffice Custom Monitoring Service
Provides health monitoring, metrics collection, and CRM auto-linking oversight
"""

import os
import time
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import threading
import schedule

import docker
import pymysql
import requests
from flask import Flask, jsonify, request
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from elasticsearch import Elasticsearch

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter('monitor_requests_total', 'Total requests', ['method', 'endpoint'])
HEALTH_STATUS = Gauge('onlyoffice_health_status', 'Health status of services', ['service'])
CONTAINER_STATUS = Gauge('container_status', 'Container status', ['container'])
CRM_AUTOLINK_EMAILS = Counter('crm_autolink_emails_total', 'Total emails processed for CRM auto-linking')
CRM_AUTOLINK_ERRORS = Counter('crm_autolink_errors_total', 'Total CRM auto-linking errors')
CRM_AUTOLINK_SERVICE_UP = Gauge('crm_autolink_service_up', 'CRM auto-linking service status')
EMAIL_DUPLICATION_EVENTS = Counter('email_duplication_events_total', 'Total email duplication events detected')
MYSQL_CONNECTIONS = Gauge('mysql_connections_active', 'Active MySQL connections')
ELASTICSEARCH_HEALTH = Gauge('elasticsearch_health_score', 'Elasticsearch health score (0-100)')

class OnlyOfficeMonitor:
    def __init__(self):
        self.config = self.load_config()
        self.docker_client = docker.from_env()
        self.mysql_config = {
            'host': os.getenv('MYSQL_HOST', 'onlyoffice-mysql-server'),
            'user': os.getenv('MYSQL_USER', 'root'),
            'password': os.getenv('MYSQL_PASSWORD', 'my-secret-pw'),
            'database': os.getenv('MYSQL_DATABASE', 'onlyoffice'),
            'port': int(os.getenv('MYSQL_PORT', '3306'))
        }
        self.es_client = Elasticsearch([f"http://{os.getenv('ELASTICSEARCH_HOST', 'onlyoffice-elasticsearch:9200')}"])
        
    def load_config(self) -> Dict[str, Any]:
        """Load monitoring configuration"""
        return {
            'check_interval': int(os.getenv('CHECK_INTERVAL', '30')),
            'crm_monitoring': os.getenv('CRM_AUTO_LINK_MONITORING', 'true').lower() == 'true',
            'containers_to_monitor': [
                'onlyoffice-community-server',
                'onlyoffice-mysql-server', 
                'onlyoffice-document-server',
                'onlyoffice-mail-server',
                'onlyoffice-elasticsearch',
                'onlyoffice-control-panel'
            ]
        }

    def check_container_health(self) -> Dict[str, Any]:
        """Check health status of all containers"""
        results = {}
        
        try:
            containers = self.docker_client.containers.list(all=True)
            
            for container in containers:
                name = container.name
                if name in self.config['containers_to_monitor']:
                    status = container.status
                    health = container.attrs.get('State', {}).get('Health', {})
                    health_status = health.get('Status', 'unknown') if health else 'no-healthcheck'
                    
                    # Update Prometheus metrics
                    CONTAINER_STATUS.labels(container=name).set(1 if status == 'running' else 0)
                    HEALTH_STATUS.labels(service=name).set(
                        1 if health_status == 'healthy' or (health_status == 'no-healthcheck' and status == 'running') else 0
                    )
                    
                    results[name] = {
                        'status': status,
                        'health': health_status,
                        'uptime': container.attrs.get('State', {}).get('StartedAt'),
                        'restart_count': container.attrs.get('RestartCount', 0)
                    }
                    
        except Exception as e:
            logger.error(f"Error checking container health: {e}")
            
        return results

    def check_mysql_health(self) -> Dict[str, Any]:
        """Check MySQL database health and metrics"""
        try:
            connection = pymysql.connect(**self.mysql_config)
            cursor = connection.cursor()
            
            # Check basic connectivity
            cursor.execute("SELECT 1")
            
            # Get connection count
            cursor.execute("SHOW GLOBAL STATUS LIKE 'Threads_connected'")
            connections = int(cursor.fetchone()[1])
            MYSQL_CONNECTIONS.set(connections)
            
            # Check recent emails for CRM monitoring
            if self.config['crm_monitoring']:
                self.check_crm_autolink_status(cursor)
            
            cursor.close()
            connection.close()
            
            return {
                'status': 'healthy',
                'connections': connections,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"MySQL health check failed: {e}")
            return {'status': 'unhealthy', 'error': str(e)}

    def check_crm_autolink_status(self, cursor):
        """Check CRM auto-linking functionality"""
        try:
            # Check if WebCrmMonitoringService is mentioned in recent logs
            # This is a proxy for checking if the service is running
            cursor.execute("""
                SELECT COUNT(*) as email_count
                FROM mail_mail 
                WHERE date_received >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
            """)
            recent_emails = cursor.fetchone()[0]
            
            # Check for CRM links created in last hour
            cursor.execute("""
                SELECT COUNT(*) as linked_count
                FROM mail_chain_x_crm_entity mcxe
                JOIN mail_mail mm ON mcxe.id_chain = mm.chain_id
                WHERE mm.date_received >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
            """)
            linked_emails = cursor.fetchone()[0]
            
            # Check for potential duplicates
            cursor.execute("""
                SELECT mm.subject, mm.from_text, COUNT(*) as duplicate_count
                FROM mail_mail mm
                WHERE mm.date_received >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
                GROUP BY mm.subject, mm.from_text, DATE(mm.date_received)
                HAVING COUNT(*) > 1
            """)
            duplicates = cursor.fetchall()
            
            # Update metrics
            CRM_AUTOLINK_EMAILS._value._value += recent_emails
            if duplicates:
                EMAIL_DUPLICATION_EVENTS._value._value += len(duplicates)
                logger.warning(f"Detected {len(duplicates)} potential email duplications")
            
            # Assume service is up if we can query successfully
            CRM_AUTOLINK_SERVICE_UP.set(1)
            
            logger.info(f"CRM Status: {recent_emails} recent emails, {linked_emails} linked, {len(duplicates)} duplicates")
            
        except Exception as e:
            logger.error(f"CRM auto-link check failed: {e}")
            CRM_AUTOLINK_ERRORS.inc()
            CRM_AUTOLINK_SERVICE_UP.set(0)

    def check_elasticsearch_health(self) -> Dict[str, Any]:
        """Check Elasticsearch health"""
        try:
            health = self.es_client.cluster.health()
            status = health['status']
            
            # Convert status to numeric score
            score_map = {'green': 100, 'yellow': 50, 'red': 0}
            score = score_map.get(status, 0)
            ELASTICSEARCH_HEALTH.set(score)
            
            return {
                'status': status,
                'score': score,
                'nodes': health['number_of_nodes'],
                'active_shards': health['active_shards'],
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Elasticsearch health check failed: {e}")
            ELASTICSEARCH_HEALTH.set(0)
            return {'status': 'unhealthy', 'error': str(e)}

    def get_system_overview(self) -> Dict[str, Any]:
        """Get comprehensive system overview"""
        return {
            'timestamp': datetime.now().isoformat(),
            'containers': self.check_container_health(),
            'mysql': self.check_mysql_health(),
            'elasticsearch': self.check_elasticsearch_health(),
            'config': self.config
        }

# Global monitor instance
monitor = OnlyOfficeMonitor()

# Flask routes
@app.route('/health')
def health_check():
    """Basic health check endpoint"""
    REQUEST_COUNT.labels(method='GET', endpoint='/health').inc()
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/health/detailed')
def detailed_health():
    """Detailed health check with all services"""
    REQUEST_COUNT.labels(method='GET', endpoint='/health/detailed').inc()
    return jsonify(monitor.get_system_overview())

@app.route('/health/docker')
def docker_health():
    """Docker containers health check"""
    REQUEST_COUNT.labels(method='GET', endpoint='/health/docker').inc()
    return jsonify(monitor.check_container_health())

@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint"""
    REQUEST_COUNT.labels(method='GET', endpoint='/metrics').inc()
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@app.route('/metrics/crm')
def crm_metrics():
    """CRM-specific metrics"""
    REQUEST_COUNT.labels(method='GET', endpoint='/metrics/crm').inc()
    
    try:
        connection = pymysql.connect(**monitor.mysql_config)
        cursor = connection.cursor()
        
        # Get CRM statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_emails,
                COUNT(CASE WHEN mcxe.entity_id IS NOT NULL THEN 1 END) as linked_emails,
                COUNT(CASE WHEN mm.date_received >= DATE_SUB(NOW(), INTERVAL 24 HOUR) THEN 1 END) as recent_emails
            FROM mail_mail mm
            LEFT JOIN mail_chain_x_crm_entity mcxe ON mm.chain_id = mcxe.id_chain
            WHERE mm.date_received >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        """)
        
        stats = cursor.fetchone()
        cursor.close()
        connection.close()
        
        return jsonify({
            'total_emails_week': stats[0],
            'linked_emails_week': stats[1], 
            'recent_emails_24h': stats[2],
            'linking_rate': (stats[1] / stats[0] * 100) if stats[0] > 0 else 0
        })
        
    except Exception as e:
        logger.error(f"CRM metrics error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/alerts', methods=['POST'])
def handle_alerts():
    """Handle Prometheus alerts"""
    REQUEST_COUNT.labels(method='POST', endpoint='/webhook/alerts').inc()
    
    try:
        alerts = request.get_json()
        logger.info(f"Received {len(alerts.get('alerts', []))} alerts")
        
        for alert in alerts.get('alerts', []):
            alertname = alert.get('labels', {}).get('alertname')
            status = alert.get('status')
            logger.info(f"Alert: {alertname} - Status: {status}")
            
        return jsonify({'status': 'received'})
        
    except Exception as e:
        logger.error(f"Alert handling error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/containers')
def list_containers():
    """List all monitored containers with detailed info"""
    REQUEST_COUNT.labels(method='GET', endpoint='/api/containers').inc()
    return jsonify(monitor.check_container_health())

@app.route('/api/logs/<container_name>')
def get_container_logs(container_name):
    """Get recent logs for a specific container"""
    REQUEST_COUNT.labels(method='GET', endpoint='/api/logs').inc()
    
    try:
        container = monitor.docker_client.containers.get(container_name)
        logs = container.logs(tail=100, timestamps=True).decode('utf-8')
        
        return jsonify({
            'container': container_name,
            'logs': logs.split('\n'),
            'timestamp': datetime.now().isoformat()
        })
        
    except docker.errors.NotFound:
        return jsonify({'error': 'Container not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def run_scheduled_checks():
    """Run scheduled monitoring checks"""
    def job():
        try:
            logger.info("Running scheduled health checks...")
            monitor.get_system_overview()
        except Exception as e:
            logger.error(f"Scheduled check error: {e}")
    
    schedule.every(monitor.config['check_interval']).seconds.do(job)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    # Start scheduled checks in background thread
    scheduler_thread = threading.Thread(target=run_scheduled_checks, daemon=True)
    scheduler_thread.start()
    
    logger.info("Starting OnlyOffice Monitor Service...")
    logger.info(f"Monitoring {len(monitor.config['containers_to_monitor'])} containers")
    logger.info(f"CRM monitoring: {monitor.config['crm_monitoring']}")
    
    # Run Flask app
    app.run(host='0.0.0.0', port=8080, debug=False)