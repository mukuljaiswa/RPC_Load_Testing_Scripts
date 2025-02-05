from locust import TaskSet, task
from web3 import Web3
import random
import json
import time
from wallet_utils import load_wallets, transaction_log_file, log_lock, transaction_log, transaction_counter, nonce_tracker, save_transaction_log
from dotenv import load_dotenv
import os
import threading
from prometheus_client import start_http_server, Counter
from locust import runners, events
from locust.runners import MasterRunner



# Load environment variables
load_dotenv()
CHAIN_ID = int(os.getenv('CHAIN_ID'))

ETHER_VALUE = os.getenv('ETHER_VALUE')

GAS_PRICE = os.getenv('GAS_PRICE')
GAS = int(os.getenv('GAS'))

SENDER_WALLET_PATH=os.getenv('SENDER_WALLET_PATH')
RECEIVER_WALLET_PATH=os.getenv('RECEIVER_WALLET_PATH')

 
sender_wallets_load =load_wallets(SENDER_WALLET_PATH)
receiver_wallets_load=load_wallets(RECEIVER_WALLET_PATH)


#Prometheus metrics
SUCCESSFUL_TRANSACTIONS = Counter('successful_transactions', 'Number of successful transactions')
FAILED_TRANSACTIONS = Counter('failed_transactions', 'Number of failed transactions')


def log_failed_transaction(sender_address, message, time_taken="N/A"):
    """Logs a failed transaction and increments the Prometheus counter."""
    FAILED_TRANSACTIONS.inc()
    transaction_log.append([
        sender_address, "N/A", "Failed", time_taken
    ])
    print(f"\033[91mTransaction failed:\033[0m {message}, Sender_Address: {sender_address}")



class BlockchainTaskSet(TaskSet):
    @task(1)
    def transfer(self):
        start_time = time.time()
      
        sender_wallets = random.choice(sender_wallets_load)        
        receiver_wallets=random.choice(receiver_wallets_load)
            
        sender_address, sender_privateKey = sender_wallets['address'], sender_wallets['privateKey']
        receiver_address =  receiver_wallets['address']


        web3 = Web3(Web3.HTTPProvider(self.user.host))
        print("Sender Address ------->", sender_address)
        print("Receiver Address ----->", receiver_address)

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

            # Use catch_response for marking failures
            with self.client.post("/", headers=headers, json=data, catch_response=True) as response:

                time_taken = time.time() - start_time  # Calculate time taken
            
                try:
                    response_json = response.json()
                    if "error" in response_json:
                        error_message = response_json["error"]["message"]
                        log_failed_transaction(sender_address, error_message, f"{time_taken:.2f}s")
                        response.failure(f"Transaction failed: {error_message}")
                        transaction_log.append([ sender_address, "N/A", "Failed", time_taken])

                    else:
                        transaction_hash = response_json.get("result", None)
                        status = "Success"
                        SUCCESSFUL_TRANSACTIONS.inc()

                        transaction_log.append([
                            sender_address, transaction_hash or "N/A",
                            status, f"{time_taken:.2f}s"
                        ])

                        nonce_tracker[sender_address] = nonce + 1
                        transaction_counter["total_successful"] += 1
                        response.success()
                        print(f"\033[93mTransaction sent\033[0m: {status}  {response.text}, | \033[92mStatus: {status} \033[0m| Time Taken: {time_taken:.2f}s, Sender_Address {sender_address}")
                except json.JSONDecodeError:
                    response.failure(sender_address,"Error parsing JSON response")


            save_transaction_log()
        except Exception as e:
                        print(f"Error occurred: {e}")




# Start Prometheus metrics server in a background thread
def start_prometheus_metrics_server():
    start_http_server(8000)  # Expose metrics on port 8000
    print("Prometheus metrics server started on port 8000.")

if threading.current_thread() == threading.main_thread():
    threading.Thread(target=start_prometheus_metrics_server, daemon=True).start()






# BASE_PROMETHEUS_PORT = 8000  # Base port for Prometheus

# # Start Prometheus metrics server in a background thread
# def start_prometheus_metrics_server(environment):
#     """Starts Prometheus metrics server on an appropriate port based on the execution mode."""
    
#     # Check if we are running in multi-process mode
#     is_multi_process = any(arg.startswith("--processes") for arg in sys.argv)
    
#     if is_multi_process:
#         if isinstance(environment.runner, MasterRunner):
#             port = BASE_PROMETHEUS_PORT  # Master always uses 8000
#         else:
#             worker_index = getattr(runners, "worker_index", os.getpid() % 1000)  # Unique worker index
#             port = BASE_PROMETHEUS_PORT + worker_index  # Workers use 8001, 8002, etc.
#     else:
#         if environment.runner:  # Single process mode
#             port = BASE_PROMETHEUS_PORT  # Always 8000 in single process mode

#     start_http_server(port)
#     print(f"Prometheus metrics server started on port {port}.")

# if threading.current_thread() == threading.main_thread():
#     threading.Thread(target=start_prometheus_metrics_server, daemon=True).start()
