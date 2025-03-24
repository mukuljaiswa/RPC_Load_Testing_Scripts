from locust import TaskSet, task, events
from web3 import Web3
import json
import time
import os
from wallet_utils import load_wallets, transaction_log, transaction_counter, nonce_tracker, save_transaction_log
from dotenv import load_dotenv
import multiprocessing
import sys
from threading import Lock

# Load environment variables
load_dotenv()
CHAIN_ID = int(os.getenv('CHAIN_ID'))
ETHER_VALUE = os.getenv('ETHER_VALUE')
GAS_PRICE = os.getenv('GAS_PRICE')
GAS = int(os.getenv('GAS'))
SENDER_WALLET_PATH = os.getenv('SENDER_WALLET_PATH')
RECEIVER_WALLET_PATH = os.getenv('RECEIVER_WALLET_PATH')

# Load wallets
sender_wallets = load_wallets(SENDER_WALLET_PATH)
receiver_wallets = load_wallets(RECEIVER_WALLET_PATH)

# Get available CPU cores
available_cores = multiprocessing.cpu_count()
worker_count = available_cores
use_multiprocessing = False

# Global indices for wallet rotation
global_sender_index = 0
global_receiver_index = 0
index_lock = Lock()

# Strict validation of worker count
for i, arg in enumerate(sys.argv):
    if arg == "--processes":
        use_multiprocessing = True
        if i + 1 < len(sys.argv):
            try:
                user_input = int(sys.argv[i + 1])
                if user_input == 0:
                    print("ERROR: You cannot run with 0 worker processes.")
                    sys.exit(1)
                elif user_input == -1:
                    worker_count = available_cores  # Use all available cores
                elif user_input > available_cores:
                    print(f"ERROR: Your system only has {available_cores} CPU cores. You cannot use more than this.")
                    sys.exit(1)
                elif user_input > 0:
                    worker_count = user_input
            except ValueError:
                print(f"ERROR: Invalid value for --processes. Using default {worker_count} workers.")
        break

def partition_wallets(wallets, worker_count, worker_id):
    if not wallets:
        return []
    total = len(wallets)
    base = total // worker_count
    extra = total % worker_count
    start = worker_id * base + min(worker_id, extra)
    end = start + base + (1 if worker_id < extra else 0)
    return wallets[start:end]

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    global global_sender_index, global_receiver_index
    with index_lock:
        global_sender_index = 0
        global_receiver_index = 0

class BlockchainTaskSet(TaskSet):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.worker_id = self._get_worker_id()
        self.sender_index = 0  # Initialize for all workers
        self.receiver_index = 0
        
        # Assign wallets based on mode
        if use_multiprocessing:
            self.sender_wallets = partition_wallets(sender_wallets, worker_count, self.worker_id)
            self.receiver_wallets = partition_wallets(receiver_wallets, worker_count, self.worker_id)
        else:
            self.sender_wallets = sender_wallets
            self.receiver_wallets = receiver_wallets
    def _get_worker_id(self):
        """Get worker ID with proper fallbacks"""
        if not use_multiprocessing:
            return 0
        if not hasattr(self.user.environment, "runner"):
            return 0
        return self.user.environment.runner.worker_index % worker_count

    @task
    def transfer(self):
        global global_sender_index, global_receiver_index

        if not self.sender_wallets or not self.receiver_wallets:
            print(f"[Worker {self.worker_id}] No wallets assigned, skipping transaction.")
            return
            
        start_time = time.time()

        # Get current wallet indices
        if use_multiprocessing:
            sender_wallet = self.sender_wallets[self.sender_index % len(self.sender_wallets)]
            receiver_wallet = self.receiver_wallets[self.receiver_index % len(self.receiver_wallets)]
            self.sender_index += 1
            self.receiver_index += 1
        else:
            with index_lock:
                sender_wallet = self.sender_wallets[global_sender_index % len(self.sender_wallets)]
                receiver_wallet = self.receiver_wallets[global_receiver_index % len(self.receiver_wallets)]
                global_sender_index += 1
                global_receiver_index += 1

        sender_address = sender_wallet['address']
        receiver_address = receiver_wallet['address']
        web3 = Web3(Web3.HTTPProvider(self.user.host))

        print(f"[Worker {self.worker_id}] Sender Address: {sender_address} --> Receiver Address: {receiver_address}")

        try:
            # Prepare and send transaction
            transaction_counter["total_attempted"] += 1
            nonce = nonce_tracker.get(sender_address, web3.eth.get_transaction_count(sender_address, 'pending'))
            
            txn = {
                'to': receiver_address,
                'value': web3.to_wei(ETHER_VALUE, 'ether'),
                'gas': GAS,
                'gasPrice': web3.to_wei(GAS_PRICE, 'gwei'),
                'nonce': nonce,
                'chainId': CHAIN_ID
            }
            
            signed_txn = web3.eth.account.sign_transaction(txn, sender_wallet['privateKey'])
            
            data = {
                "jsonrpc": "2.0",
                "method": "eth_sendRawTransaction",
                "params": [f"0x{signed_txn.raw_transaction.hex()}"],
                "id": 1
            }
            
            with self.client.post("/", 
                               headers={'Content-Type': 'application/json'},
                               json=data,
                               catch_response=True) as response:
                time_taken = time.time() - start_time
                
                try:
                    response_json = response.json()
                    if "error" in response_json:
                        error_msg = response_json["error"]["message"]
                        response.failure(f"[Worker {self.worker_id}] Transaction failed: {error_msg}")
                        transaction_log.append([sender_address, "N/A", "Failed", time_taken])
                    else:
                        tx_hash = response_json.get("result")
                        status = "Success"
                        transaction_log.append([
                            sender_address,
                            tx_hash or "N/A",
                            status,
                            f"{time_taken:.2f}s"
                        ])
                        nonce_tracker[sender_address] = nonce + 1
                        transaction_counter["total_successful"] += 1
                        response.success()
                        print(f"[Worker {self.worker_id}] \033[93mTransaction sent\033[0m: {status} {response.text}, | \033[92mStatus: {status} \033[0m| Time Taken: {time_taken:.2f}s | Sender_Address: {sender_address}")
                        
                except json.JSONDecodeError:
                    response.failure(f"[Worker {self.worker_id}] Error parsing JSON response")
            
            save_transaction_log()
            
        except Exception as e:
            print(f"[Worker {self.worker_id}] Error occurred: {e}")