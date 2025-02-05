from locust import HttpUser, between, events
from datetime import datetime
import sys
from locust.runners import MasterRunner
from dotenv import load_dotenv
import os
import threading
from prometheus_metrics import start_prometheus_metrics_server  # Import Prometheus function
from rpc_funds_transfer import BlockchainTaskSet  # Import BlockchainTaskSet
from wallet_utils import initialize_transaction_log, rename_transaction_log_file

# Load environment variables
load_dotenv()
RPC_HOST = os.getenv('RPC_HOST')

test_start_time = None

# Check if the script is running as a master or worker
is_master = "--master" in sys.argv

# Start Prometheus server only if running as master
if is_master:
    print("Starting Prometheus on Master Node...")
    prometheus_thread = threading.Thread(target=start_prometheus_metrics_server, daemon=True)
    prometheus_thread.start()

# Event Listeners
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    global test_start_time
    test_start_time = datetime.now()
    initialize_transaction_log()
    print("Test started.")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    if test_start_time is None:
        print("Test never started.")
        return

    if isinstance(environment.runner, MasterRunner):  # Ensure it runs only on master
        rename_transaction_log_file(test_start_time)

    print("Stopped Load Testing !!!")

# User Class
class BlockchainUser(HttpUser):
    tasks = [BlockchainTaskSet]
    wait_time = between(1, 5)
    host = RPC_HOST
