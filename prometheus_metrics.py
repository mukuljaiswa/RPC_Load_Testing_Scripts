import threading
import requests
from prometheus_client import start_http_server, Gauge
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
LOCUST_MASTER_IP_URL = os.getenv('LOCUST_MASTER_IP_URL')
PROMETHEUS_RUNNING_PORT = int(os.getenv('PROMETHEUS_RUNNING_PORT'))

# Prometheus Metrics
SUCCESSFUL_TRANSACTIONS = Gauge('successful_transactions', 'Current number of successful transactions')
FAILED_TRANSACTIONS = Gauge('failed_transactions', 'Current number of failed transactions')

def fetch_locust_metrics():
    """Fetch metrics from Locust API continuously."""
    while True:
        try:
            response = requests.get(LOCUST_MASTER_IP_URL)
            data = response.json()
            for stat in data.get("stats", []):
                if stat["name"] == "/":
                    SUCCESSFUL_TRANSACTIONS.set(stat["num_requests"] - stat["num_failures"])
                    FAILED_TRANSACTIONS.set(stat["num_failures"])
        except Exception as e:
            print(f"Error fetching Locust metrics: {e}")

        time.sleep(5)  # Fetch every 5 seconds

def start_prometheus_metrics_server():
    """Starts the Prometheus metrics server only for the master."""
    start_http_server(PROMETHEUS_RUNNING_PORT)
    print(f"Prometheus metrics server started on port {PROMETHEUS_RUNNING_PORT}")

    metrics_thread = threading.Thread(target=fetch_locust_metrics, daemon=True)
    metrics_thread.start()


