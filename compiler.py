import os
import subprocess
import sys

def compile_with_pyinstaller():
    project_dir = os.getcwd()
    script_file = os.path.join(project_dir, "main.py")
    icon_path = os.path.join(project_dir, "images", "icon.ico")
    images_dir = os.path.join(project_dir, "images")
    version_file = os.path.join(project_dir, "version.json")
    output_name = "HookLineSinkerReborn"

    required_files = [script_file, icon_path, version_file]
    missing_files = [f for f in required_files if not os.path.exists(f)]
    if missing_files:
        print(f"Error: The following required files are missing: {', '.join(missing_files)}")
        sys.exit(1)

    command = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        f"--add-data={images_dir};images",
        f"--add-data={version_file};.",
        f"--icon={icon_path}",
        "--name", output_name,
        script_file
    ]

    try:
        subprocess.run(command, check=True)
        print(f"Compilation complete. Executable created in the 'dist' directory.")
    except subprocess.CalledProcessError as e:
        print(f"Compilation failed: {e}")

def bundled_file_path(relative_path):
    """
    Get the absolute path to a bundled file in the executable.
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), relative_path)

if __name__ == "__main__":
    compile_with_pyinstaller()
