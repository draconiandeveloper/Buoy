import os
import shutil

# Get the user's LocalAppData path
localappdata_path = os.getenv('LOCALAPPDATA')
if not localappdata_path:
    print("Could not retrieve the LocalAppData path.")
    exit(1)

source_dir = os.path.join(localappdata_path, r'PyoidTM\Hook_Line_Sinker')
destination_dir = os.path.join(localappdata_path, r'PawsHLSR\Hook_Line_Sinker_Reborn') # This is still named this way to avoid breaking existing users

if not os.path.exists(source_dir):
    print(f"Source directory {source_dir} does not exist.")
    print("Looks like the fish escaped the hook! Seems like you don't have any HLS data to import.")
    exit(1)

if not os.path.exists(destination_dir):
    os.makedirs(destination_dir)

success = True

for item in os.listdir(source_dir):
    source_item = os.path.join(source_dir, item)
    destination_item = os.path.join(destination_dir, item)

    try:
        if os.path.isdir(source_item):
            shutil.move(source_item, destination_item)
            print(f"Moved directory: {item}")
        elif os.path.isfile(source_item):
            shutil.move(source_item, destination_item)
            print(f"Moved file: {item}")
    except Exception as e:
        print(f"Error moving {item}: {e}")
        success = False

if success:
    print("\nSuccess! Your Hook, Line, and Sinker data has been imported to Buoy!")
    input()
else:
    print("\nUh-oh! Some fish wriggled free and escaped the net. Try again or contact the developers on Discord!")
    input()
