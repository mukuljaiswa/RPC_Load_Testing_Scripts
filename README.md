# RPC Load Testing - README

## Project Overview

This project contains a Locust load testing script for RPC services. The main script responsible for load testing is main_locust_load_testing_script.py. The repository also includes the necessary requirements for setting up the Locust and web3 environment, along with transaction history tracking.

## Folder Structure

### RPC_Load_Testing_Scripts/

|-- **main_locust_load_testing_script.py**  
|   Main Python script for executing load tests using Locust.

|-- **rpc_funds_transfer.py**  
|   Contains Web3 RPC methods for transferring funds.

|-- **wallet_utils.py**  
|   Includes utility functions related to wallet operations.

|-- **.env**  
|   Configuration file containing:
|   - RPC URL  
|   - Chain ID  
|   - Transferable amount  
|   - Gas fees  

|-- **devRequirements.txt**  
|   List of dependencies required for setting up Locust and Web3.

|-- **wallets/**  
|   Folder containing wallet-related data.
|   |-- **wallets.csv**  
|       CSV file with sender and receiver wallet details.

|-- **transaction_history/**  
|   Folder for storing logs of transactions performed during testing.
|   |-- **transaction_history_(start_date_time)_between_(end_date_time).csv**  
|       Transaction logs in CSV format, with file names indicating the testing period.  
|       Example: `transaction_history_10-01-2025_12_40_41_between_10-01-2025_12_50_44.csv`


## wallets.csv (csv headers)

- **Sender Address** – The wallet address initiating the transaction  
- **Sender Private Key** – Private key associated with the sender’s address  
- **Receiver Wallet Address** – The wallet address receiving the transaction  

## transaction_history.csv (csv headers)

- **Sender Address** – Address initiating the transaction  
- **Transaction Hash** – Unique hash of the transaction  
- **Status** – Transaction status (Success/Fail)  
- **Time Taken** – Time taken for the transaction to complete  

## Setup Instructions

### 1.Prerequisites

Ensure Python 3 and pip3 are installed.

If Python 3 or pip3 is not installed, install them using the following commands:
```
sudo apt update

sudo apt install python3 python3-pip

```

### 2.Environment Setup

Navigate to the project directory:


```
cd RPC_Load_Testing_Scripts

```

### 3.Set up a virtual environment:

```
python3 -m venv myenv

for Linux/Mac use 
source myenv/bin/activate

for windows use
myenv\Scripts\activate

```
Sometimes, it shows an error message while creating a virtual machine in Linux/macOS using source myenv/bin/activate. 
To resolve this, run 

```
sudo apt install python3-venv 

```
and then try step 3 again.

### 4.Install dependencies:

```

pip3 install -r devRequirements.txt

```

### 5.Verify Locust installation:

```
locust --version

```

### 6.Running the Load Testing Script

Run the main Locust script:

```
locust -f main_locust_load_testing_script.py

```

### 7.After running the command, the web interface will start at:

**http://0.0.0.0:8089** or **http://localhost:8089/**

Open the URL in a browser and fill in the desired number of users and ramp-up rate (e.g., 5 users/second).

Click the Start button to initiate testing.

### 8.Monitoring

Real-time monitoring includes total users, request success/fail rates, RPS (Requests Per Second), and graphical representations of active users and requests.

Logs will display transaction details such as sender, receiver, and transaction hash directly in the terminal.

### 9.stopping the Test

Click the Stop button on the web interface to halt the test.

A Locust HTML report can be downloaded from the web interface.

After stopping, the **transaction_history_(start_date_time)_between_(end_date_time).csv** file will be updated in the **transaction_history** folder.

### 10.Multi-Core Load Testing

For larger-scale testing, utilize all available CPU cores by running the following command:

```

locust -f main_locust_load_testing_script.py --processes -1

```

This command ensures the test utilizes all CPU cores for handling higher loads.

Without --processes -1, Locust will default to single-core usage.

#Notes

Always ensure the virtual environment (myenv) is active when running the script.

If the environment is not activated, activate it with:

**source myenv/bin/activate**


## Conclusion

This script provides an efficient way to perform load testing on RPC services, ensuring scalability and reliability through Locust's real-time monitoring and transaction logging features.


