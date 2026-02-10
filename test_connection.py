from web3 import Web3
import logging

# Enable logging to see what's happening under the hood
logging.basicConfig(level=logging.DEBUG)

RPC_HOST = "https://incarnation-rpc.bdagscan.com"

print(f"Attempting to connect to: {RPC_HOST}")
try:
    web3 = Web3(Web3.HTTPProvider(RPC_HOST))
    print(f"Checking connection via block number...")
    try:
        block_num = web3.eth.block_number
        print(f"Successfully retrieved block number: {block_num}")
        print("✅ Connection verified via block_number")
    except Exception as e:
        print(f"❌ Failed to retrieve block number: {e}")

except Exception as e:
    print(f"Error during connection setup: {e}")
