from web3 import Web3
import pandas as pd
from datetime import datetime
import time
import random
import concurrent.futures

# ================= CONFIG =================
RPC_HOST = "https://incarnation-rpc.bdagscan.com"
CHAIN_ID = 1404

START_BLOCK = 100
END_BLOCK = 53274

OUTPUT_FILE = "incarnation_block_metrics_100_53274.xlsx"
# =========================================

# Connect to RPC
web3 = Web3(Web3.HTTPProvider(RPC_HOST))

# Check connection by fetching the latest block number
try:
    latest_block = web3.eth.block_number
    print(f"✅ Connected to RPC. Latest block: {latest_block}")
except Exception as e:
    raise Exception(f"❌ Unable to connect to RPC: {e}")

print("✅ Connected to RPC")

# Threading Config
MAX_WORKERS = 20  # You can increase this if your machine/RPC can handle it


def fetch_block(block_number, retries=10):
    """Fetches a single block and returns its basic data, with retries."""
    for attempt in range(retries):
        try:
            block = web3.eth.get_block(block_number, full_transactions=False)
            return {
                "BlockNumber": block.number,
                "BlockHash": block.hash.hex(),
                "Timestamp": block.timestamp,
                "TransactionCount": len(block.transactions)
            }
        except Exception as e:
            # Check for Rate Limit or JSON Decode Error (often means server sent error text instead of JSON)
            error_str = str(e)
            if "Too Many Requests" in error_str or "429" in error_str or "Expecting value" in error_str:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                # Cap the wait time to 30 seconds max
                wait_time = min(wait_time, 30)
                print(f"⚠ Issue on block {block_number} (Attempt {attempt+1}/{retries}): {e}. Retrying in {wait_time:.2f}s...")
                time.sleep(wait_time)
            else:
                print(f"❌ Error processing block {block_number}: {e}. Retrying anyway...")
                time.sleep(2)
    
    print(f"❌❌ FAILED to fetch block {block_number} after {retries} attempts. SKIPPING.")
    return None

# List to store raw block data
raw_data = []

print(f"🚀 Starting extraction with {MAX_WORKERS} workers...")

with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    # Create a dictionary of futures to block numbers
    future_to_block = {executor.submit(fetch_block, bn): bn for bn in range(START_BLOCK, END_BLOCK + 1)}
    
    for i, future in enumerate(concurrent.futures.as_completed(future_to_block)):
        result = future.result()
        if result:
            raw_data.append(result)
        
        # Print progress every 50 blocks
        if (i + 1) % 50 == 0:
            print(f"✔ Fetched {i + 1} blocks...")

print("✅ Fetching complete. Processing data...")

# Sort data by BlockNumber to ensure sequential processing for time diffs
raw_data.sort(key=lambda x: x["BlockNumber"])

data = []
previous_timestamp = None

for item in raw_data:
    block_timestamp = item["Timestamp"]
    created_time = datetime.utcfromtimestamp(block_timestamp)
    tx_count = item["TransactionCount"]

    # Time difference between blocks
    if previous_timestamp is None:
        time_diff = None
        tps = None
    else:
        time_diff = block_timestamp - previous_timestamp
        tps = round(tx_count / time_diff, 4) if time_diff > 0 else 0

    data.append({
        "BlockNumber": item["BlockNumber"],
        "BlockHash": item["BlockHash"],
        "CreatedTime (UTC)": created_time,
        "TransactionCount": tx_count,
        "TimeDifference (sec)": time_diff,
        "Transaction/s": tps
    })

    previous_timestamp = block_timestamp

# Convert to DataFrame
df = pd.DataFrame(data)

# Save to Excel
df.to_excel(OUTPUT_FILE, index=False)

print(f"\n📊 Excel file generated: {OUTPUT_FILE}")

