import json
import sys

def split_json_file(input_file, num_parts=10):
    # Load the JSON data from the input file
    with open(input_file, 'r') as f:
        data = json.load(f)

    total_items = len(data)
    # Calculate base size and determine the remainder
    base_size = total_items // num_parts
    remainder = total_items % num_parts

    start = 0
    for i in range(num_parts):
        # Distribute the remainder: add one extra item for the first 'remainder' parts
        end = start + base_size + (1 if i < remainder else 0)
        chunk = data[start:end]
        
        # Write each chunk to its own output file
        output_file = f"output_{i+1}.json"
        with open(output_file, 'w') as f_out:
            json.dump(chunk, f_out, indent=2)
        print(f"Written {len(chunk)} items to {output_file}")
        
        start = end

def main():
    if len(sys.argv) < 2:
        print("Usage: python split_json.py <input_file.json>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    split_json_file(input_file)

if __name__ == '__main__':
    main()
