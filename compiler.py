import os
import subprocess
import sys
import json

def get_version(version_file):
    try:
        with open(version_file, "r") as file:
            data = json.load(file)
        return data.get("version", "unknown_version")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading version file: {e}")
        sys.exit(1)

def compile_with_pyinstaller():
    project_dir = os.getcwd()
    script_file = os.path.join(project_dir, "main.py")
    icon_path = os.path.abspath(os.path.join(project_dir, "images", "icon.ico"))
    images_dir = os.path.abspath(os.path.join(project_dir, "images"))
    version_file = os.path.abspath(os.path.join(project_dir, "version.json"))

    required_files = [script_file, icon_path, version_file]
    missing_files = [f for f in required_files if not os.path.exists(f)]
    if missing_files:
        print(f"Error: The following required files are missing: {', '.join(missing_files)}")
        sys.exit(1)

    version = get_version(version_file)
    sanitized_version = version.replace(" ", "_").replace("/", "_")
    output_name = f"HLSReborn_v{sanitized_version}"

    # Command for PyInstaller with corrected path formats for Windows
    command = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        f"--add-data={images_dir};images",  # Windows-specific path separator
        f"--add-data={version_file};.",  # Bundles the version file
        f"--icon={icon_path}",
        "--name", output_name,
        script_file
    ]

    try:
        subprocess.run(command, check=True)
        print(f"Compilation complete. Executable '{output_name}.exe' created in the 'dist' directory.")
    except subprocess.CalledProcessError as e:
        print(f"Compilation failed: {e}")

def bundled_file_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), relative_path)

if __name__ == "__main__":
    compile_with_pyinstaller()
