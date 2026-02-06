from locust import TaskSet, task, events
import requests
from web3 import Web3
import json
import time
import os
from wallet_utils import load_wallets, transaction_log, transaction_counter, save_transaction_log
import multiprocessing
import sys
import threading
from dotenv import load_dotenv

# Environment variables
load_dotenv()
CHAIN_ID = int(os.getenv('CHAIN_ID', '0'))
ETHER_VALUE = os.getenv('ETHER_VALUE', '0')
GAS_PRICE = os.getenv('GAS_PRICE', '0')
GAS = int(os.getenv('GAS', '21000'))
SENDER_WALLET_PATH = os.getenv('SENDER_WALLET_PATH')
RECEIVER_WALLET_PATH = os.getenv('RECEIVER_WALLET_PATH')
CYCLE_DELAY = int(os.getenv('CYCLE_DELAY', '2')) 

# Pre-calculate common Web3 values
W3_DUMMY = Web3() # Used for utility functions only
ETHER_VALUE_WEI = W3_DUMMY.to_wei(ETHER_VALUE, 'ether')
GAS_PRICE_WEI = W3_DUMMY.to_wei(GAS_PRICE, 'gwei')

print("\nLoading wallets...")
sender_wallets = load_wallets(SENDER_WALLET_PATH,"sender wallets") 
receiver_wallets = load_wallets(RECEIVER_WALLET_PATH,"receiver wallets")
print(f"Loaded {len(sender_wallets)} sender wallets and {len(receiver_wallets)} receiver wallets\n")
print(f"Configured cycle delay between wallet cycles: {CYCLE_DELAY} seconds\n")

# Worker configuration
available_cores = multiprocessing.cpu_count()
worker_count = available_cores
use_multiprocessing = False

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
                    worker_count = available_cores
                elif user_input > available_cores:
                    print(f"ERROR: Your system only has {available_cores} CPU cores.")
                    sys.exit(1)
                elif user_input > 0:
                    worker_count = user_input
            except ValueError:
                print(f"ERROR: Invalid value for --processes. Using default {worker_count} workers.")
        break

print(f"[INFO] System has {available_cores} CPU cores")
print(f"[INFO] Configured to use {worker_count} workers\n")

class WalletDistributor:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.initialize()
        return cls._instance

    def initialize(self):
        self.worker_assignments = {}  # Track wallet ranges for each worker
        self._receiver_counter = 0  # Atomic counter for receivers
        self.cycle_complete = False
        self.cycle_count = 0
        self.cycle_delay = CYCLE_DELAY
        self._cycle_lock = threading.Lock()  # Only for cycle management
        print("[WALLET_DISTRIBUTOR] Initialized wallet distributor with cycle delay")

    def _calculate_worker_range(self, worker_id):
        """Calculate the wallet range for a worker"""
        total_wallets = len(sender_wallets)

        # Add this block at the start of the method
        if not use_multiprocessing:
            return 0, total_wallets

        wallets_per_worker = total_wallets // worker_count
        remainder = total_wallets % worker_count
        
        start = worker_id * wallets_per_worker
        end = start + wallets_per_worker
        
        # Distribute remainder wallets to first 'remainder' workers
        if worker_id < remainder:
            start += worker_id
            end += worker_id + 1
        else:
            start += remainder
            end += remainder
        
        return start, end

    def get_next_wallet_pair(self, worker_id):
        # Initialize worker assignments if not exists (minimal lock scope)
        if worker_id not in self.worker_assignments:
            with self._cycle_lock:
                if worker_id not in self.worker_assignments:  # Double check
                    start, end = self._calculate_worker_range(worker_id)
                    self.worker_assignments[worker_id] = {
                        'start': start,
                        'end': end,
                        'current': start,
                        'initial_range': (start, end)
                    }
                    mode = "Single worker" if not use_multiprocessing else f"Worker {worker_id}"
                    print(f"[ASSIGNMENT] {mode} assigned wallets {start}-{end-1} (total {len(sender_wallets)})")

        worker_data = self.worker_assignments[worker_id]
        
        # Atomic operation - get current index without lock
        current_index = worker_data['current']
        
        # If we've reached the end of our range
        if current_index >= worker_data['end']:
            return self._handle_cycle_completion(worker_id, worker_data)
        
        # Atomic increment for sender
        worker_data['current'] = current_index + 1
        
        # Atomic increment for receiver (no lock needed)
        receiver_index = self._receiver_counter
        self._receiver_counter = (receiver_index + 1) % len(receiver_wallets)

        sender_wallet = sender_wallets[current_index]
        receiver_wallet = receiver_wallets[receiver_index]

        print(f"[ASSIGNMENT] Worker {worker_id} using sender {sender_wallet['address']} "
              f"(index {current_index} of {len(sender_wallets)})")
        
        return sender_wallet, receiver_wallet

    def _handle_cycle_completion(self, worker_id, worker_data):
        """Handle cycle completion with minimal locking"""
        # Only synchronize when checking cycle completion
        with self._cycle_lock:
            # Check if all workers have completed their ranges
            all_complete = all(
                wd['current'] >= wd['end'] 
                for wd in self.worker_assignments.values()
            )
            
            if all_complete:
                self.cycle_count += 1
                print(f"[CYCLE] Cycle {self.cycle_count} completed. Waiting {self.cycle_delay} seconds...")
                time.sleep(self.cycle_delay)  # Sleep between cycles
                print("[CYCLE] Starting new cycle")
                
                # Reset all workers to their initial ranges
                for wd in self.worker_assignments.values():
                    wd['current'] = wd['initial_range'][0]
                    wd['end'] = wd['initial_range'][1]
                
                # Return first wallet of new cycle
                return self.get_next_wallet_pair(worker_id)
            else:
                print(f"[WAITING] Worker {worker_id} waiting for others to complete cycle")
                return None, None

wallet_distributor = WalletDistributor()

def reset_global_wallet_indices():
    """Reset all wallet counters"""
    wallet_distributor.initialize()
    print("[RESET] Wallet counters and nonces reset to zero")

class BlockchainTaskSet(TaskSet):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.worker_id = self._get_worker_id()
        self.session = requests.Session()
        
        # Reuse Web3 connection
        self._web3 = None
        
        print(f"[INFO] Worker {self.worker_id} initialized")

    def _get_worker_id(self):
        if not use_multiprocessing:
            return 0
        if not hasattr(self.user.environment, "runner"):
            return 0
        return self.user.environment.runner.worker_index % worker_count
    
    @property
    def web3(self):
        if self._web3 is None:
            self._web3 = Web3(Web3.HTTPProvider(self.user.host))
        return self._web3
    
    @task
    def transfer(self):
        result = wallet_distributor.get_next_wallet_pair(self.worker_id)
        if result is None or any(v is None for v in result):
            return
        
        sender_wallet, receiver_wallet = result
        start_time = time.time()
  
        # Addresses are already checksummed during load_wallets
        sender_address = sender_wallet['address']
        receiver_address = receiver_wallet['address']

        nonce = None

        try:
            # Use reused Web3 connection
            nonce = self.web3.eth.get_transaction_count(sender_address, 'pending')
            txn = {
                'to': receiver_address,
                'value': ETHER_VALUE_WEI,
                'gas': GAS,
                'gasPrice': GAS_PRICE_WEI,
                'nonce': nonce,
                'chainId': CHAIN_ID
            }

    
            signed_txn = self.web3.eth.account.sign_transaction(txn, sender_wallet['privateKey'])
                        
            data = {
                "jsonrpc": "2.0",
                "method": "eth_sendRawTransaction",
                "params":[f"0x{signed_txn.raw_transaction.hex()}"],
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
                        self._handle_transaction_result(
                            sender_address, None, "Failed", nonce, time_taken, error_msg, self.worker_id
                        )
                        response.failure(error_msg)
                    else:
                        tx_hash = response_json.get("result")
                        self._handle_transaction_result(
                            sender_address, tx_hash, "Success", nonce, time_taken, "", self.worker_id
                        )
                        response.success()
                except (json.JSONDecodeError, ValueError):
                    error_msg = f"Invalid JSON response: Status Code: {response.status_code}"
                    self._handle_transaction_result(
                        sender_address, None, "Failed", nonce, time_taken, error_msg, self.worker_id
                    )
                    response.failure(error_msg)

                save_transaction_log()
                
        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = str(e)
            print(f"[RETRYABLE ERROR] Worker {self.worker_id}: {error_msg}")

            self._handle_transaction_result(
                sender_address, None, "Failed", nonce, elapsed, error_msg, self.worker_id
            )
              
            # ✅ Record failure in Locust
            events.request.fire(
                    request_type="POST",
                    name="///",
                    response_time=elapsed * 1000,  # ms
                    response_length=0,
                    exception=e,
                    context=None,
                    success=False
            )

            save_transaction_log()
            raise

    def _handle_transaction_result(self, sender, tx_hash, status, nonce,time_taken, error_msg,worker_Id):
        transaction_log.append([
            sender,
            tx_hash or "N/A",
            status,
            f"{time_taken:.2f}s",
            nonce,
            "worker "+str(worker_Id)
        ])
        
        color = "\033[92m" if status == "Success" else "\033[91m"
        print(f"{color}[Worker {self.worker_id}] {status}\033[0m: "
              f"Address: {sender} | "
              f"Tx Hash: {tx_hash or 'N/A'} | "
              f"Nonce: {nonce} | "
              f"Time: {time_taken:.2f}s | "
              f"{error_msg}")