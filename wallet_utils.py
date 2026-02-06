import csv
import os
import threading
from datetime import datetime
from dotenv import load_dotenv
import json
from collections import defaultdict
from web3 import Web3

transaction_log_file = None
log_lock = threading.Lock()
transaction_log = []

transaction_counter = {"total_attempted": 0, "total_successful": 0}

def load_wallets(file_path,wallet_type):
    """Load wallets from JSON file with validation"""

    print(f"Loading {wallet_type} wallets from {file_path}")
    try:
        with open(file_path, 'r') as f:
            wallets = json.load(f)
            if not isinstance(wallets, list):
                raise ValueError("Wallet file should contain a JSON array")
            print(f"Successfully loaded {len(wallets)} wallets")
            return wallets
    except Exception as e:
        print(f"Error loading wallets: {e}")
        raise

def check_and_create_transaction_log_file():
    """Ensure transaction log file exists with proper header"""
    folder = 'transaction_history'
    os.makedirs(folder, exist_ok=True)
    filename = os.path.join(folder, "transaction_history.csv")
    
    if not os.path.isfile(filename):
        print("Creating new transaction log file")
        with open(filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Sender Address", "Transaction Hash", "Status", "Time Taken", "Nonce"])
    return filename

def initialize_transaction_log():
    """Initialize the transaction log file"""
    global transaction_log_file
    if not transaction_log_file:
        transaction_log_file = check_and_create_transaction_log_file()
        print("Transaction log initialized")

def save_transaction_log():
    """Save all pending transactions to the log file"""
    global transaction_log
    if not transaction_log:
        print("No transactions to save")
        return
    
    print(f"Saving {len(transaction_log)} transactions to log")
    try:
        with log_lock:
            with open(transaction_log_file, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerows(transaction_log)
            print("Transactions saved successfully")
            transaction_log.clear()  # Clear only after successful save
    except Exception as e:
        print(f"Error saving transactions: {e}")

def rename_transaction_log_file(test_start_time):
    """Rename log file with timestamps after test completes"""
    global transaction_log_file
    if not transaction_log_file:
        print("No transaction log file to rename")
        return
    
    try:
        stop_time = datetime.now()
        start_str = test_start_time.strftime("%d-%m-%Y_%H_%M_%S")
        stop_str = stop_time.strftime("%d-%m-%Y_%H_%M_%S")
        new_filename = f"transaction_history/transaction_history_{start_str}_to_{stop_str}.csv"
        
        # Ensure all transactions are saved before renaming
        save_transaction_log()
        
        os.rename(transaction_log_file, new_filename)
        transaction_log_file = None
        print(f"Renamed transaction log to {new_filename}")
        
        # Ensure header exists in new file
        ensure_header_in_file(new_filename)
    except Exception as e:
        print(f"Error renaming transaction log: {e}")

def ensure_header_in_file(filename):
    """Ensure CSV file has proper header row"""
    try:
        if not os.path.isfile(filename):
            with open(filename, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["Sender Address", "Transaction Hash", "Status", "Time Taken", "Nonce"])
            print("Created new file with header")
    except Exception as e:
        print(f"Error ensuring header exists: {e}")