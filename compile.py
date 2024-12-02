import subprocess
import shutil
import json
import sys
import os

def get_separator():
    return ';' if sys.platform == 'win32' else ':'

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
    icon_path = os.path.abspath(os.path.join(project_dir, "images", "icon.png"))
    version_file = os.path.abspath(os.path.join(project_dir, "version.json"))

    required_files = [script_file, icon_path, version_file]
    missing_files = [f for f in required_files if not os.path.exists(f)]
    if missing_files:
        print(f"Error: The following required files are missing: {', '.join(missing_files)}")
        sys.exit(1)

    version = get_version(version_file)
    sanitized_version = version.replace(" ", "_").replace("/", "_")
    output_name = f"Buoy_v{sanitized_version}"

    command = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        f"--add-data={version_file}{get_separator()}.",
        f"--icon={icon_path}",
        "--name", output_name,
        script_file
    ]

    try:
        subprocess.run(command, check=True)
        print(f"Compilation complete. Executable '{output_name}' created in the 'dist' directory.")
    except subprocess.CalledProcessError as e:
        print(f"Compilation failed: {e}")


if __name__ == "__main__":
    compile_with_pyinstaller()

    dist_dir = os.path.join(os.getcwd(), 'dist')
    if not os.path.exists(dist_dir):
        exit(0) # We are to assume that the build process failed.

    shutil.copy(os.path.join(os.getcwd(), 'version.json'), dist_dir)
    shutil.copy(os.path.join(os.getcwd(), 'icon.png'), dist_dir)