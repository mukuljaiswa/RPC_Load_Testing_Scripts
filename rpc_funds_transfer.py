from locust import TaskSet, task
from web3 import Web3
import random
import json
import time
import os
from wallet_utils import load_wallets, transaction_log, transaction_counter, nonce_tracker, save_transaction_log
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
CHAIN_ID = int(os.getenv('CHAIN_ID'))
ETHER_VALUE = os.getenv('ETHER_VALUE')
GAS_PRICE = os.getenv('GAS_PRICE')
GAS = int(os.getenv('GAS'))
SENDER_WALLET_PATH = os.getenv('SENDER_WALLET_PATH')
RECEIVER_WALLET_PATH = os.getenv('RECEIVER_WALLET_PATH')

sender_wallets_load = load_wallets(SENDER_WALLET_PATH)
receiver_wallets_load = load_wallets(RECEIVER_WALLET_PATH)

class BlockchainTaskSet(TaskSet):
    @task(1)
    def transfer(self):
        start_time = time.time()
        sender_wallets = random.choice(sender_wallets_load)
        receiver_wallets = random.choice(receiver_wallets_load)
        sender_address, sender_privateKey = sender_wallets['address'], sender_wallets['privateKey']
        receiver_address = receiver_wallets['address']
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
            with self.client.post("/", headers=headers, json=data, catch_response=True) as response:
                time_taken = time.time() - start_time
                try:
                    response_json = response.json()
                    if "error" in response_json:
                        error_message = response_json["error"]["message"]
                      #  log_failed_transaction(sender_address, error_message, f"{time_taken:.2f}s")
                        response.failure(f"Transaction failed: {error_message}")
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
                        print(f"\033[93mTransaction sent\033[0m: {status} {response.text}, | \033[92mStatus: {status} \033[0m| Time Taken: {time_taken:.2f}s, Sender_Address {sender_address}")
                except json.JSONDecodeError:
                    response.failure(sender_address, "Error parsing JSON response")
            save_transaction_log()
        except Exception as e:
            print(f"Error occurred: {e}")
