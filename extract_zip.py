import os

# Define the extraction directory
extract_dir = 'unzipped_sim12'

# Create the extraction directory if it doesn't exist
if not os.path.exists(extract_dir):
    os.makedirs(extract_dir)
    print(f"Successfully created directory {extract_dir}")
else:
    print(f"Directory {extract_dir} already exists")

# Create a single empty file
test_file_path = os.path.join(extract_dir, 'test_file.txt')
with open(test_file_path, 'w') as f:
    pass
print(f"Successfully created empty file {test_file_path}")
