import os
import shutil

# Get the user's LocalAppData path
localappdata_path = os.getenv('LOCALAPPDATA')
if not localappdata_path:
    print("Could not retrieve the LocalAppData path.")
    exit(1)

# Define the source and destination directories dynamically
source_dir = os.path.join(localappdata_path, r'PyoidTM\Hook_Line_Sinker')
destination_dir = os.path.join(localappdata_path, r'PawsHLSR\Hook_Line_Sinker_Reborn')

# Check if the source directory exists
if not os.path.exists(source_dir):
    print(f"Source directory {source_dir} does not exist.")
else:
    # Ensure the destination directory exists, create it if not
    if not os.path.exists(destination_dir):
        os.makedirs(destination_dir)

    # Loop through all items (files and folders) in the source directory
    for item in os.listdir(source_dir):
        source_item = os.path.join(source_dir, item)
        destination_item = os.path.join(destination_dir, item)

        # Move directories and files from source to destination
        try:
            if os.path.isdir(source_item):
                # Move the entire directory
                shutil.move(source_item, destination_item)
                print(f"Moved directory: {item}")
            elif os.path.isfile(source_item):
                # Move individual files
                shutil.move(source_item, destination_item)
                print(f"Moved file: {item}")
        except Exception as e:
            print(f"Error moving {item}: {e}")
