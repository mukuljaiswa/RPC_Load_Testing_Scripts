from locust import TaskSet, task, events
import requests
from web3 import Web3
import json
import time
import os
from wallet_utils import load_wallets, transaction_log, transaction_counter, nonce_manager, save_transaction_log
import multiprocessing
import sys
from threading import Lock
from dotenv import load_dotenv

load_dotenv()

# Environment variables
CHAIN_ID = int(os.getenv('CHAIN_ID'))
ETHER_VALUE = os.getenv('ETHER_VALUE')
GAS_PRICE = os.getenv('GAS_PRICE')
GAS = int(os.getenv('GAS'))
SENDER_WALLET_PATH = os.getenv('SENDER_WALLET_PATH')
RECEIVER_WALLET_PATH = os.getenv('RECEIVER_WALLET_PATH')
CYCLE_DELAY = int(os.getenv('CYCLE_DELAY', '5'))  # Default 5 second delay between cycles

print("\nLoading wallets...")
sender_wallets = load_wallets(SENDER_WALLET_PATH)
receiver_wallets = load_wallets(RECEIVER_WALLET_PATH)
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
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.initialize()
        return cls._instance

    def initialize(self):
        self.sender_lock = Lock()
        self.receiver_lock = Lock()
        self.worker_assignments = {}  # Track wallet ranges for each worker
        self.worker_index = 0  # Current position for each worker
        self.cycle_complete = False
        self.cycle_count = 0
        self.cycle_delay = CYCLE_DELAY
        print("[WALLET_DISTRIBUTOR] Initialized wallet distributor with cycle delay")

    def _calculate_worker_range(self, worker_id):
        """Calculate the wallet range for a worker"""
        total_wallets = len(sender_wallets)
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
        with self.sender_lock:
            # Initialize worker assignments if not exists
            if worker_id not in self.worker_assignments:
                start, end = self._calculate_worker_range(worker_id)
                self.worker_assignments[worker_id] = {
                    'start': start,
                    'end': end,
                    'current': start,
                    'initial_range': (start, end)
                }
                print(f"[ASSIGNMENT] Worker {worker_id} assigned wallets {start}-{end-1}")

            worker_data = self.worker_assignments[worker_id]
            
            # If we've reached the end of our range
            if worker_data['current'] >= worker_data['end']:
                if not self.cycle_complete:
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
                        self.cycle_complete = True
                        # Reset all workers to their initial ranges
                        for wd in self.worker_assignments.values():
                            wd['current'] = wd['initial_range'][0]
                            wd['end'] = wd['initial_range'][1]
                    else:
                        print(f"[WAITING] Worker {worker_id} waiting for others to complete cycle")
                        return None, None
                else:
                    # In subsequent cycles, just reset to start of range
                    worker_data['current'] = worker_data['initial_range'][0]
                    worker_data['end'] = worker_data['initial_range'][1]
                    print(f"[CYCLE] Worker {worker_id} reset to start of range")

            # Get the current wallet
            sender_wallet = sender_wallets[worker_data['current']]
            worker_data['current'] += 1

            # Get receiver wallet (round-robin)
            with self.receiver_lock:
                receiver_wallet = receiver_wallets[self.worker_index % len(receiver_wallets)]
                self.worker_index += 1

            print(f"[ASSIGNMENT] Worker {worker_id} using sender {sender_wallet['address'][:8]}... "
                  f"(index {worker_data['current']-1} of {len(sender_wallets)})")
            
            return sender_wallet, receiver_wallet

wallet_distributor = WalletDistributor()

def reset_global_wallet_indices():
    """Reset all wallet counters"""
    wallet_distributor.initialize()
    nonce_manager.reset_all_nonces()
    print("[RESET] Wallet counters and nonces reset to zero")

class BlockchainTaskSet(TaskSet):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.worker_id = self._get_worker_id()
        self.session = requests.Session()
        print(f"[INFO] Worker {self.worker_id} initialized")

    def _get_worker_id(self):
        if not use_multiprocessing:
            return 0
        if not hasattr(self.user.environment, "runner"):
            return 0
        return self.user.environment.runner.worker_index % worker_count

    @task
    def transfer(self):
        sender_wallet, receiver_wallet = wallet_distributor.get_next_wallet_pair(self.worker_id)
        if not sender_wallet or not receiver_wallet:
            return

        start_time = time.time()
        sender_address = sender_wallet['address']
        receiver_address = receiver_wallet['address']
        web3 = Web3(Web3.HTTPProvider(self.user.host))

        try:
            nonce = nonce_manager.get_next_nonce(web3, sender_address)
            
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
                        self._handle_transaction_result(
                            sender_address, None, "Failed", nonce, time_taken, error_msg
                        )
                        response.failure(error_msg)
                    else:
                        tx_hash = response_json.get("result")
                        self._handle_transaction_result(
                            sender_address, tx_hash, "Success", nonce, time_taken, ""
                        )
                        response.success()
                except json.JSONDecodeError:
                    error_msg = "Invalid JSON response"
                    self._handle_transaction_result(
                        sender_address, None, "Failed", nonce, time_taken, error_msg
                    )
                    response.failure(error_msg)
                
                save_transaction_log()
                
        except Exception as e:
            error_msg = str(e)
            self._handle_transaction_result(
                sender_address, None, "Failed", nonce, time.time() - start_time, error_msg
            )
            nonce_manager.reset_address(sender_address)
            save_transaction_log()
            raise

    def _handle_transaction_result(self, sender, tx_hash, status, nonce, time_taken, error_msg):
        transaction_counter["total_attempted"] += 1
        if status == "Success":
            transaction_counter["total_successful"] += 1
            nonce_manager.update_nonce(sender, nonce + 1)
        
        transaction_log.append([
            sender,
            tx_hash or "N/A",
            status,
            f"{time_taken:.2f}s",
            nonce
        ])
        
        color = "\033[92m" if status == "Success" else "\033[91m"
        print(f"{color}[Worker {self.worker_id}] {status}\033[0m: "
              f"Address: {sender} | "
              f"Tx Hash: {tx_hash or 'N/A'} | "
              f"Nonce: {nonce} | "
              f"Time: {time_taken:.2f}s | "
              f"{error_msg}")