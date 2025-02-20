from locust import HttpUser, between, events
from datetime import datetime
import sys
from locust.runners import MasterRunner
from dotenv import load_dotenv
import os
import threading
from prometheus_metrics import start_prometheus_metrics_server
from rpc_funds_transfer import BlockchainTaskSet
from wallet_utils import initialize_transaction_log, rename_transaction_log_file
from emailable_report import send_email, remove_old_report

# Load environment variables
load_dotenv()
RPC_HOST = os.getenv('RPC_HOST')

test_start_time = None

# Check if running as master, worker, or standalone
is_master = "--master" in sys.argv
is_worker = "--worker" in sys.argv
is_process_mode = any(arg.startswith("--processes") for arg in sys.argv)

if is_worker:
    print("\n[INFO] This is a Locust worker node. No email will be sent from this node.\n")
elif is_process_mode:
    print(
        "\n[INFO] Load testing will run successfully, but Prometheus will NOT start "
        "because it may cause conflicts with the same port.\n"
        "To use Prometheus, run in master-worker mode:\n"
        "  locust --master -f main_locust_load_testing_script.py\n"
        "Or run Locust in single-core mode with Prometheus enabled:\n"
        "  locust -f main_locust_load_testing_script.py --html=locust_report.html\n"
    )
else:
    # Start Prometheus only in master or standalone mode
    if is_master or not is_worker:
        print("[INFO] Starting Prometheus metrics server...")
        prometheus_thread = threading.Thread(target=start_prometheus_metrics_server, daemon=True)
        prometheus_thread.start()

# Event Listeners
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    global test_start_time
    test_start_time = datetime.now()
    initialize_transaction_log()
    remove_old_report()  # Delete old report before starting
    print("[INFO] Load test started.")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    global test_start_time

    if test_start_time is None:
        print("[WARNING] Test never started.")
        return

    # Ensure only the master node renames the transaction log file
    if isinstance(environment.runner, MasterRunner) or (not is_worker and not is_process_mode):
        print("[INFO] Renaming transaction log file...")
        rename_transaction_log_file(test_start_time)

    if is_master or (not is_worker and not is_process_mode) or (is_process_mode and os.getpid() == min(os.getpid(), *os.sched_getaffinity(0))):
        print("[INFO] Checking for Locust report before sending email...")
        send_email()
        

    print("[INFO] Stopped Load Testing !!!")


# User Class
class BlockchainUser(HttpUser):
    tasks = [BlockchainTaskSet]
    wait_time = between(1, 5)
    host = RPC_HOST
