import csv
import os
import threading
from datetime import datetime
from dotenv import load_dotenv
import json
import random

transaction_log_file = None
log_lock = threading.Lock()
transaction_log = []
transaction_counter = {"total_attempted": 0, "total_successful": 0}
nonce_tracker = {}

# Load wallets from JSON
def load_wallets(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

# Ensure transaction log file exists
def check_and_create_transaction_log_file():
    folder = 'transaction_history'
    os.makedirs(folder, exist_ok=True)
    filename = os.path.join(folder, "transaction_history.csv")    
    if not os.path.isfile(filename):
        with open(filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Sender Address", "Transaction Hash", "Status", "Time Taken"])
            
    return filename

# Initialize transaction log file
def initialize_transaction_log():
    global transaction_log_file
    if not transaction_log_file:
        transaction_log_file = check_and_create_transaction_log_file()

# Save transaction log
def save_transaction_log():
    global transaction_log
    with open(transaction_log_file, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(transaction_log)
    transaction_log.clear()

import os
from datetime import datetime

def rename_transaction_log_file(test_start_time):
    """Safely rename transaction log file after test completion."""
    global transaction_log_file

    if transaction_log_file is None:
        print("[WARNING] Transaction log file is not set. Skipping renaming.")
        return

    if not os.path.exists(transaction_log_file):
        print(f"[WARNING] Transaction log file '{transaction_log_file}' not found. Skipping renaming.")
        return

    try:
        stop_time = datetime.now()
        start_timestamp = test_start_time.strftime("%d-%m-%Y_%H_%M_%S")
        stop_timestamp = stop_time.strftime("%d-%m-%Y_%H_%M_%S")
        new_filename = f"transaction_history/transaction_history_{start_timestamp}_to_{stop_timestamp}.csv"

        os.rename(transaction_log_file, new_filename)
        transaction_log_file = None  # Reset global variable

        ensure_header_in_file(new_filename)
        print(f"[INFO] Renamed transaction log to {new_filename}")

    except Exception as e:
        print(f"[ERROR] Failed to rename transaction log: {e}")


# Ensure header in transaction log file
def ensure_header_in_file(filename):
    if not os.path.isfile(filename):
        with open(filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Sender Address", "Transaction Hash", "Status", "Time Taken"])
