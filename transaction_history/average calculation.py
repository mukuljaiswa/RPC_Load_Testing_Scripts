import pandas as pd

# Provide the CSV file path
csv_file_path = "transaction_history_19-03-2025_16_13_39_to_19-03-2025_16_15_31.csv"  # Change this to the actual file path

# Read the CSV file
df = pd.read_csv(csv_file_path)

# Print total number of rows
total_rows = len(df)
print(f"Total number of rows: {total_rows}")

# Convert 'Time Taken' column to numeric, ensuring errors are ignored
df['Time Taken'] = pd.to_numeric(df['Time Taken'].str.replace('s', ''), errors='coerce')

# Exclude rows where 'Transaction Hash' is 'N/A'
filtered_df = df[df['Transaction Hash'] != 'N/A']

# Calculate statistics for 'Time Taken'
average_time_taken = filtered_df['Time Taken'].mean()
min_time_taken = filtered_df['Time Taken'].min()
max_time_taken = filtered_df['Time Taken'].max()

# Print the results
print(f"Average Time Taken: {average_time_taken:.2f} seconds")
print(f"Minimum Time Taken: {min_time_taken:.2f} seconds")
print(f"Maximum Time Taken: {max_time_taken:.2f} seconds")

