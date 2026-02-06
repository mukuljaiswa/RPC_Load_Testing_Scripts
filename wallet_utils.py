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
            
            # Pre-checksum addresses to save CPU during test execution
            for wallet in wallets:
                if 'address' in wallet:
                    wallet['address'] = Web3.to_checksum_address(wallet['address'])
            
            print(f"Successfully loaded {len(wallets)} wallets")
            return wallets
    except Exception as e:
        print(f"Error loading wallets: {e}")
        raise

def check_and_create_transaction_log_file():
    """Ensure transaction log file exists with proper header (Unique per Process)"""
    folder = 'transaction_history'
    os.makedirs(folder, exist_ok=True)
    
    # ⚡ FIX: Use PID to ensure every worker has its OWN file
    # This prevents "File not found" and race conditions when renaming
    pid = os.getpid()
    filename = os.path.join(folder, f"transaction_history_worker_{pid}.csv")
    
    if not os.path.isfile(filename):
        # print(f"Creating new transaction log file for PID {pid}")
        with open(filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Sender Address", "Transaction Hash", "Status", "Time Taken", "Nonce", "Worker ID", "Error Message"])
    return filename

def initialize_transaction_log():
    """Initialize the transaction log file"""
    global transaction_log_file
    if not transaction_log_file:
        transaction_log_file = check_and_create_transaction_log_file()
        print("Transaction log initialized")

def save_transaction_log(force=False):
    """Save all pending transactions to the log file (Batched)"""
    global transaction_log
    
    # ⚡ OPTIMIZATION: Only write to disk if we have enough data or are forced
    # This prevents opening/closing the file 1000 times per second
    if not force and len(transaction_log) < 1000:
        return

    if not transaction_log:
        # print("No transactions to save") # Silent return to avoid spam
        return
    
    try:
        with log_lock:
            # Copy and clear local log quickly to minimize lock contention
            log_to_save = transaction_log[:]
            transaction_log.clear()
            
            if not log_to_save:
                return

            with open(transaction_log_file, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerows(log_to_save)
            print(f"Transactions saved successfully ({len(log_to_save)} records)")
    except Exception as e:
        print(f"Error saving transactions: {e}")

def rename_transaction_log_file(test_start_time):
    """Rename THIS worker's log file with timestamps after test completes"""
    global transaction_log_file
    if not transaction_log_file or not os.path.exists(transaction_log_file):
        # process might have already renamed it or started without one
        return
    
    try:
        stop_time = datetime.now()
        start_str = test_start_time.strftime("%d-%m-%Y_%H_%M_%S")
        stop_str = stop_time.strftime("%d-%m-%Y_%H_%M_%S")
        pid = os.getpid()
        
        # New name includes start/stop time AND worker PID
        new_filename = f"transaction_history/transaction_log_{start_str}_to_{stop_str}_worker_{pid}.csv"
        
        # Ensure all transactions are saved before renaming
        save_transaction_log(force=True)
        
        os.rename(transaction_log_file, new_filename)
        # print(f"Renamed log to {new_filename}")
        
    except Exception as e:
        print(f"Error renaming transaction log for PID {os.getpid()}: {e}")

