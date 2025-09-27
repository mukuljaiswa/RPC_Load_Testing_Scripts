from locust import TaskSet, task, events
import requests
from web3 import Web3
import json
import time
import os
from wallet_utils import load_wallets, transaction_log, transaction_counter, save_transaction_log#,nonce_manager
import multiprocessing
import sys
from threading import Lock
from dotenv import load_dotenv

#gas_tracker = {}
load_dotenv()

# Environment variables
CHAIN_ID = int(os.getenv('CHAIN_ID'))
ETHER_VALUE = os.getenv('ETHER_VALUE')
GAS_PRICE = os.getenv('GAS_PRICE')
GAS = int(os.getenv('GAS'))
SENDER_WALLET_PATH = os.getenv('SENDER_WALLET_PATH')
RECEIVER_WALLET_PATH = os.getenv('RECEIVER_WALLET_PATH')
CYCLE_DELAY = int(os.getenv('CYCLE_DELAY', '2'))  # Default 3 second delay between cycles

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
                mode = "Single worker" if not use_multiprocessing else f"Worker {worker_id}"
                print(f"[ASSIGNMENT] {mode} assigned wallets {start}-{end-1} (total {len(sender_wallets)})")

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
                        print("[CYCLE] Starting new " \
                        "cycle")
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

            print(f"[ASSIGNMENT] Worker {worker_id} using sender {sender_wallet['address']} "
                  f"(index {worker_data['current']-1} of {len(sender_wallets)})")
            
            return sender_wallet, receiver_wallet

wallet_distributor = WalletDistributor()

def reset_global_wallet_indices():
    """Reset all wallet counters"""
    wallet_distributor.initialize()
    #nonce_manager.reset_all_nonces()
    print("[RESET] Wallet counters and nonces reset to zero")

# def get_nonce(address, RPC_URL):
#     try:
#         payload = {
#             "jsonrpc": "2.0",
#             "method": "eth_getTransactionCount",
#             "params": [address, "pending"],
#             "id": 1
#         }
#         response = requests.post(RPC_URL, json=payload)

#         # Parse JSON safely
#         resp_json = response.json()

#         # If result is valid, return nonce
#         if "result" in resp_json:
#             return int(resp_json["result"], 16)
#         else:
#             print(f"[WARN] Invalid RPC responseee: {resp_json}")
#             return None

#     except (json.JSONDecodeError, ValueError) as e:
#         print(f"[ERROR] Invalid JSON while fetching nonce: {e} | Status: {response.status_code}")
#         return None

#     except Exception as e:
#         print(f"[ERROR] Failed to fetch nonce for {address}: {e}")
#         return None


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
        # sender_address = sender_wallet['address']
        # receiver_address = receiver_wallet['address']
        sender_address = Web3.to_checksum_address(sender_wallet['address'])
        receiver_address = Web3.to_checksum_address(receiver_wallet['address'])


        web3 = Web3(Web3.HTTPProvider(self.user.host))

        #print("Current nonce batches:",nonce_manager._batch_store)

        nonce = None   # <-- FIX: Ensure nonce is always defined

        try:

            # # --- DYNAMIC GAS PRICE LOGIC ---
            # # Get current base fee from the latest block
            # latest_block = web3.eth.get_block('latest')
            # print("latest_block--->",latest_block)
            # base_fee = latest_block['baseFeePerGas']
            # print("base_fee----->",base_fee)


            # # Calculate a max fee (base fee + priority fee)
            # # Let's aim for a medium-priority tip (e.g., 1.5 Gwei)
            # priority_fee = web3.to_wei(1.5, 'gwei')

            # print("priority_fee-->",priority_fee)

            # max_fee_per_gas = base_fee + priority_fee

            # print("max_fee_per_gas---->max_fee_per_gas = base_fee + priority_fee",max_fee_per_gas)

            # # Optional: Add a small multiplier for load test certainty (e.g., 1.1x)
            # max_fee_per_gas = int(max_fee_per_gas * 1.1)
               
            # print(" max_fee_per_gas--->max_fee_per_gas = int(max_fee_per_gas * 1.1)",max_fee_per_gas)

            #nonce = nonce_manager.get_next_nonce(web3, sender_address)
            
            #Function to calculate gas price
            # def get_gas_price(nonce):
            #     # bump gas price slightly depending on nonce (cycles every 10)
            #     return base_gas_price + (nonce % 10) * web3.to_wei(1, 'gwei')
        
            #base_gas_price + (nonce * web3.to_wei(1, 'gwei')),  # increase per nonce

            #current_gas_price = gas_tracker.get(sender_address, 80)

            #print("current_gas_price--->",current_gas_price)

            #nonce =get_nonce(sender_address,self.user.host)

            nonce = web3.eth.get_transaction_count(sender_address, 'pending')

           # print("nonce--->",nonce)
            
            #base_gas_price = web3.to_wei(80, 'gwei')

            #gas_price = get_gas_price(nonce)

            # txn = {
            #     'to': receiver_address,
            #     'value': web3.to_wei(ETHER_VALUE, 'ether'),
            #     'gas': GAS,
            #     'gasPrice':GAS_PRICE,
            #     'nonce': nonce,
            #     'chainId': CHAIN_ID
            #    }
            

            txn = {
                'to': receiver_address,
                'value': web3.to_wei(ETHER_VALUE, 'ether'),
                'gas': GAS,
                'gasPrice': web3.to_wei(GAS_PRICE, 'gwei'),
                'nonce': nonce,
                'chainId': CHAIN_ID
            }

        #     txn = {
        #     'to': receiver_address,
        #     'value': web3.to_wei(ETHER_VALUE, 'ether'),
        #     'gas': GAS,
        #     'maxFeePerGas': max_fee_per_gas,  # Use new dynamic fee
        #     'maxPriorityFeePerGas': priority_fee, # And priority fee
        #     'nonce': nonce,
        #     'chainId': CHAIN_ID,
        #     'type': 2  # Explicitly set EIP-1559 transaction type
        # }
            
            signed_txn = web3.eth.account.sign_transaction(txn, sender_wallet['privateKey'])
                        
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
                            sender_address, None, "Failed", nonce,time_taken, error_msg, self.worker_id
                        )
                        response.failure(error_msg)
                    else:
                        tx_hash = response_json.get("result")
                        self._handle_transaction_result(
                            sender_address, tx_hash, "Success", nonce, time_taken, "",self.worker_id
                        )
                        response.success()
                except json.JSONDecodeError:

                    error_msg = f"Invalid JSON response:  Status Code: {response.status_code} "

                    self._handle_transaction_result(
                        sender_address, None, "Failed", nonce,time_taken, error_msg,self.worker_id
                    )
                    response.failure(error_msg)

                save_transaction_log()
                
        except Exception as e:
            print("Inside  except Exception---->",e)
            error_msg = str(e)

            # Measure how long this request took before failing
            elapsed = time.time() - start_time

            self._handle_transaction_result(
                sender_address, None, "Failed", nonce,time.time() - start_time, error_msg,self.worker_id
            )
            #nonce_manager.reset_address(sender_address)
              
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
        #transaction_counter["total_attempted"] += 1
        # if status == "Success":
        #     #transaction_counter["total_successful"] += 1
        #     #nonce_manager.update_nonce(sender, nonce + 1)
        #     #gas_tracker[sender] = current_gas_price + 5
        
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
        
