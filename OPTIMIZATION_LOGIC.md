# Optimized RPC Load Testing Script

## Overview
This script is a high-performance Locust load testing tool designed to flood-test EVM-compatible RPC nodes. It achieves maximum throughput by implementing **Optimistic Nonce Tracking** (in-memory) and **Wallet Rotation**, significantly reducing network overhead and preventing stuck transactions.

## Recent Optimizations
We have applied several critical optimizations to improve speed and reliability:

### 1. Optimistic Nonce Tracking (In-Memory)
Instead of asking the blockchain for the `nonce` before every single transaction (which doubles latency and fails if the mempool is full), we now:
*   Fetch the nonce from the network **only once** per wallet.
*   Store it in memory (`self.wallet_nonces`).
*   Increment it locally (`nonce += 1`) for all subsequent transactions.

**Benefit:** Cuts network calls by **50%** and allows filling the mempool with sequential transactions even if previous ones are still pending.

### 2. Periodic Nonce Synchronization (Self-Healing)
To prevent local nonce drift from becoming permanent:
*   The script maintains a counter for every wallet.
*   **Every 20 transactions**, it forces a network call (`get_transaction_count`) to verify the correct nonce.
*   This ensures that if transactions were silently dropped or stuck, the script "re-syncs" automatically without stopping.
*   **High Gas Priority:** The script uses a static high gas price (120 Gwei) to ensure transactions are mined immediately and do not get stuck in the mempool.

### 3. Failure Recovery Mechanism
If a transaction fails (e.g., returns "Nonce too low" or an RPC error):
*   The script immediately **deletes the cached nonce** for that specific wallet.
*   The next time that wallet is used, it forces a fresh fetch from the network to re-sync.

### 4. Distributed Wallet Rotation
*   Wallets are distributed evenly across workers using the `WalletDistributor` class.
*   This ensures **no two workers usage the same wallet**, eliminating `nonce` race conditions entirely.

### 5. Batched Disk I/O & Silent Console
*   **Batching:** Transaction logs are now held in memory and only written to disk in batches of **1000** (or when the test stops). This eliminates 99.9% of file system overhead.
*   **Silent Mode:** "Success" messages are no longer printed to the console (only errors). This removes terminal rendering latency, a common bottleneck in high-throughput CLI apps.

## Key Code Components

### `WalletDistributor` Strategy
Ensures safe distribution of workloads:
```python
def _calculate_worker_range(self, worker_id):
    # Splits 50,000 wallets across N workers
    # Worker 0 gets [0 - 3571]
    # Worker 1 gets [3572 - 7143]
    # ...
```

### `BlockchainTaskSet` Logic (The Core)
The `_transfer` function is where the magic happens:

```python
def transfer(self):
    # 1. Get Wallet
    sender_wallet, receiver_wallet = wallet_distributor.get_next_wallet_pair(self.worker_id)
    
    # 2. Get Nonce (Optimized with Sync)
    current_count = self.nonce_sync_counters.get(sender_address, 0)
    force_sync = current_count >= 20
    
    if not force_sync and sender_address in self.wallet_nonces:
         # FAST: Use local memory
         nonce = self.wallet_nonces[sender_address]
    else:
         # SLOW: Network call (First time, Error recovery, or Every 20th tx)
         nonce = self.web3.eth.get_transaction_count(sender_address, 'pending')
         self.wallet_nonces[sender_address] = nonce
         self.nonce_sync_counters[sender_address] = 0

    # 3. Optimistic Increment
    self.wallet_nonces[sender_address] = nonce + 1
    
    # 4. Send Transaction
    # ... (sign and send) ...

    # 5. Handle Errors (Recovery)
    if error:
        del self.wallet_nonces[sender_address] # Reset cache to force fresh fetch
```

## How to Run
For maximum performance (Headless Mode):
```bash
# Run with all available cores (e.g., 14 workers)
locust -f main_locust_load_testing_script.py --processes -1 --headless -u 14 -r 14 -t 1h
```

## Troubleshooting
*   **"Insufficient funds"**: Your test wallets are empty. Fund them before running.
*   **"Nonce too low"**: The script will auto-correct this on the next cycle by resetting the cache.
*   **"Test never started"**: Ensure you use `--headless` or click "Start" in the web UI.
