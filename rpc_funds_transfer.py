from locust import TaskSet, task
from web3 import Web3
import json
import time
import os
from wallet_utils import (
    load_wallets,
    create_wallet_queue,
    transaction_log,
    transaction_counter,
    nonce_tracker,
    save_transaction_log
)
from dotenv import load_dotenv
import queue

# Load environment variables
load_dotenv()
CHAIN_ID = int(os.getenv('CHAIN_ID'))
ETHER_VALUE = os.getenv('ETHER_VALUE')
GAS_PRICE = os.getenv('GAS_PRICE')
GAS = int(os.getenv('GAS'))
SENDER_WALLET_PATH = "blockdag_distributed_wallets/"
# Fixed receiver address
RECEIVER_ADDRESS = "0x73209844aFd5aC3746679FafFEed16993C7d47c6"

# Load sender wallets from the given directory and create a queue.
sender_wallets_list = load_wallets(SENDER_WALLET_PATH)
sender_wallet_queue = create_wallet_queue(sender_wallets_list)

class BlockchainTaskSet(TaskSet):
    @task(1)
    def transfer(self):
        start_time = time.time()
        # Get the next available sender wallet from the queue.
        try:
            sender_wallet = sender_wallet_queue.get_nowait()
        except queue.Empty:
            print("No more sender wallets available in the queue. Skipping transaction.")
            return

        sender_address = sender_wallet['address']
        sender_privateKey = sender_wallet['privateKey']
        receiver_address = RECEIVER_ADDRESS

        web3 = Web3(Web3.HTTPProvider(self.user.host))
        print("\n=== Initiating Transaction ===")
        print(f"Sender Address:   {sender_address}")
        print(f"Receiver Address: {receiver_address}")
        
        try:
            transaction_counter["total_attempted"] += 1
            # Get or initialize the nonce for the sender address.
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
                        response.failure(f"Transaction failed: {error_message}")
                        transaction_log.append([sender_address, "N/A", "Failed", f"{time_taken:.2f}s"])
                        print(f"Transaction failed for {sender_address}: {error_message} | Time Taken: {time_taken:.2f}s")
                    else:
                        transaction_hash = response_json.get("result", None)
                        status = "Success"
                        transaction_log.append([
                            sender_address,
                            transaction_hash or "N/A",
                            status,
                            f"{time_taken:.2f}s"
                        ])
                        nonce_tracker[sender_address] = nonce + 1
                        transaction_counter["total_successful"] += 1
                        response.success()
                        print(f"Transaction sent successfully for {sender_address}: {response.text}")
                        print(f"Status: {status} | Time Taken: {time_taken:.2f}s")
                except json.JSONDecodeError:
                    response.failure("Error parsing JSON response")
                    print("Error: JSON decode error in response.")
            save_transaction_log()
        except Exception as e:
            print(f"Error occurred for {sender_address}: {e}")
        
        print(f"Wallet {sender_address} has been used and removed from the queue.")
