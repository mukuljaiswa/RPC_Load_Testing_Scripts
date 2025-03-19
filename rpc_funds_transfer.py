from locust import TaskSet, task
from web3 import Web3
import json
import time
import os
from wallet_utils import load_wallets, transaction_log, transaction_counter, nonce_tracker, save_transaction_log
from dotenv import load_dotenv
import multiprocessing
import sys


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

# Default to all available CPU cores
worker_count = multiprocessing.cpu_count()

# Parse command-line arguments
for i, arg in enumerate(sys.argv):
    if arg == "--processes" and i + 1 < len(sys.argv):
        try:
            user_input = int(sys.argv[i + 1])
            if user_input > 0:
                worker_count = user_input  # Use the provided positive number
            elif user_input == -1:
                worker_count = multiprocessing.cpu_count()  # Use all available CPU cores
            else:
                print(f"Invalid value for --processes: {sys.argv[i+1]}, using default {worker_count}")
        except ValueError:
            print(f"Invalid value for --processes: {sys.argv[i+1]}, using default {worker_count}")
        break


# Function to partition wallets among workers
def partition_wallets(wallets, worker_count, worker_id):
    if not wallets:
        return []
    
    total_wallets = len(wallets)
    base_size = total_wallets // worker_count
    extra = total_wallets % worker_count

    start = worker_id * base_size + min(worker_id, extra)
    end = start + base_size + (1 if worker_id < extra else 0)

    return wallets[start:end]

# Define the user class
class BlockchainTaskSet(TaskSet):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.worker_id = self.user.environment.runner.worker_index if self.user.environment.runner else 0
        self.sender_wallets = partition_wallets(sender_wallets, worker_count, self.worker_id)
        self.receiver_wallets = partition_wallets(receiver_wallets, worker_count, self.worker_id)
        self.sender_index = 0
        self.receiver_index = 0

    @task
    def transfer(self):
        if not self.sender_wallets or not self.receiver_wallets:
            print(f"[Worker {self.worker_id}] No wallets assigned, skipping transaction.")
            return
        
        start_time = time.time()

        # Get the current sender and receiver based on the worker's index
        sender_wallet = self.sender_wallets[self.sender_index]
        receiver_wallet = self.receiver_wallets[self.receiver_index]

        sender_address, sender_privateKey = sender_wallet['address'], sender_wallet['privateKey']
        receiver_address = receiver_wallet['address']
        web3 = Web3(Web3.HTTPProvider(self.user.host))  # Use `self.user.host`

        print(f"[Worker {self.worker_id}] Sender Address: {sender_address} --> Receiver Address: {receiver_address}")

        try:
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
            signed_txn = web3.eth.account.sign_transaction(txn, sender_privateKey)
            data = {
                "jsonrpc": "2.0",
                "method": "eth_sendRawTransaction",
                "params": [f"0x{signed_txn.raw_transaction.hex()}"],
                "id": 1
            }
            headers = {'Content-Type': 'application/json'}
            with self.client.post("/", headers=headers, json=data, catch_response=True) as response:
                time_taken = time.time() - start_time
                try:
                    response_json = response.json()
                    if "error" in response_json:
                        error_message = response_json["error"]["message"]
                        response.failure(f"[Worker {self.worker_id}] Transaction failed: {error_message}")
                        transaction_log.append([sender_address, "N/A", "Failed", time_taken])
                    else:
                        transaction_hash = response_json.get("result", None)
                        status = "Success"
                        transaction_log.append([
                            sender_address, transaction_hash or "N/A",
                            status, f"{time_taken:.2f}s"
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

        # Update indices for the next transaction
        self.sender_index = (self.sender_index + 1) % len(self.sender_wallets)
        self.receiver_index = (self.receiver_index + 1) % len(self.receiver_wallets)
