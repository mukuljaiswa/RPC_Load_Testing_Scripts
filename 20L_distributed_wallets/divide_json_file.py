import json

def divide_json_file(input_file, num_parts):
    # Load the JSON data from the input file
    with open(input_file, 'r') as file:
        data = json.load(file)

    # Calculate the size of each part
    total_items = len(data)
    print(f"Total addresses in {input_file}: {total_items}")
    part_size = total_items // num_parts

    # Divide the data into parts and write to separate files
    for i in range(num_parts):
        start_index = i * part_size
        end_index = start_index + part_size if i != num_parts - 1 else total_items
        part_data = data[start_index:end_index]

        output_file = f"output_part_{i + 1}.json"
        with open(output_file, 'w') as out_file:
            json.dump(part_data, out_file, indent=2)

        print(f"Created {output_file} with {len(part_data)} addresses.")

# Example usage
divide_json_file('output.json', 10)

