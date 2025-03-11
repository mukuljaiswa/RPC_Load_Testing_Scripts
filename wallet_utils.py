import os
import json
import queue

def load_wallets(directory_path):
    """
    Load all wallet JSON files from a given directory.
    Each file can contain a single wallet (as a dict) or multiple wallets (as a list of dicts).
    Each wallet should contain 'address' and 'privateKey'.
    """
    wallets = []
    if not os.path.isdir(directory_path):
        print(f"Error: {directory_path} is not a valid directory.")
        return wallets

    for filename in os.listdir(directory_path):
        if filename.endswith('.json'):
            filepath = os.path.join(directory_path, filename)
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    # Handle if file contains a list of wallets
                    if isinstance(data, list):
                        for wallet in data:
                            if isinstance(wallet, dict) and 'address' in wallet and 'privateKey' in wallet:
                                wallets.append(wallet)
                                print(f"Loaded wallet from {filename}: {wallet['address']}")
                            else:
                                print(f"Warning: An entry in {filename} is missing 'address' or 'privateKey'.")
                    # Handle if file contains a single wallet as a dict
                    elif isinstance(data, dict):
                        if 'address' in data and 'privateKey' in data:
                            wallets.append(data)
                            print(f"Loaded wallet from {filename}: {data['address']}")
                        else:
                            print(f"Warning: {filename} is missing 'address' or 'privateKey'.")
                    else:
                        print(f"Warning: {filename} has an unrecognized format.")
            except Exception as e:
                print(f"Error loading {filename}: {e}")
    return wallets

def create_wallet_queue(wallets):
    """
    Create a thread-safe queue from the list of wallets.
    """
    wallet_queue = queue.Queue()
    for wallet in wallets:
        wallet_queue.put(wallet)
    print(f"Created wallet queue with {wallet_queue.qsize()} wallets.")
    return wallet_queue

# Variables to track transactions
transaction_log = []  # Logs each transaction: [sender_address, transaction_hash, status, time_taken]
transaction_counter = {"total_attempted": 0, "total_successful": 0}
nonce_tracker = {}

def save_transaction_log():
    """
    Save (or print) the transaction log.
    """
    print("Transaction log saved. Entries:")
    for entry in transaction_log:
        print(entry)

def initialize_transaction_log():
    """
    Initialize/clear the transaction log.
    """
    global transaction_log
    transaction_log = []
    print("Transaction log initialized.")

def rename_transaction_log_file(start_time):
    """
    Simulate renaming a transaction log file using the test start time.
    """
    print(f"Transaction log file renamed with start time {start_time}.")
