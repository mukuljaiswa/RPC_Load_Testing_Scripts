from locust import HttpUser, between, events
from datetime import datetime
import sys
from locust.runners import MasterRunner
from rpc_funds_transfer import BlockchainTaskSet
from wallet_utils import initialize_transaction_log, rename_transaction_log_file
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
RPC_HOST = os.getenv('RPC_HOST')

test_start_time = None

# Determine if --processes is used
is_multi_process = any(arg.startswith("--processes") for arg in sys.argv)

# Events for start and stop
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    global test_start_time
    test_start_time = datetime.now()
    initialize_transaction_log()

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    if test_start_time is None:
        print("Test never started.")
        return
    
    if is_multi_process:
        if isinstance(environment.runner, MasterRunner):
                rename_transaction_log_file(test_start_time)                
    else:
        if environment.runner:
            rename_transaction_log_file(test_start_time)     
    print("Stopped Load Testing !!!")

# User Class
class BlockchainUser(HttpUser):
    tasks = [BlockchainTaskSet]
    wait_time = between(1, 5)
    host = RPC_HOST

