from locust import TaskSet, task
from web3 import Web3
import random
import json
import time
from wallet_utils import load_wallets, transaction_log_file, log_lock, transaction_log, transaction_counter, nonce_tracker, save_transaction_log
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
CHAIN_ID = int(os.getenv('CHAIN_ID'))

ETHER_VALUE = os.getenv('ETHER_VALUE')

GAS_PRICE = os.getenv('GAS_PRICE')
GAS = int(os.getenv('GAS'))

wallets = load_wallets('wallets/wallets.csv')

class BlockchainTaskSet(TaskSet):
    @task(1)
    def transfer(self):
        start_time = time.time()
        sender_address, sender_privateKey, receiver_address = random.choice(wallets)
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
            response = self.client.post("/", headers={'Content-Type': 'application/json'}, json=data)
            time_taken = time.time() - start_time
            status = "Success" if response.status_code == 200 else "Failed"
            transaction_hash = json.loads(response.text).get("result", "N/A") if response.status_code == 200 else "N/A"

            with log_lock:
                transaction_log.append([sender_address, transaction_hash, status, f"{time_taken:.2f}s"])
            if status == "Success":
                transaction_counter["total_successful"] += 1
                nonce_tracker[sender_address] = nonce + 1

            print(f"\033[93mTransaction sent\033[0m: {status} {response.text} | \033[92mStatus: {status}\033[0m | Time Taken: {time_taken:.2f}s, Sender: {sender_address}")

            save_transaction_log()
        except Exception as e:
                        print(f"Error occurred: {e}")
