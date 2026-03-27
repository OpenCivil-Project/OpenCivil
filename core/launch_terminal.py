import subprocess
import os

root_dir = os.path.dirname(os.path.abspath(__file__))

cli_path = os.path.join(root_dir, "cli.py")

command = f'start cmd /K "python {cli_path}"'

try:
    print(f"Launching OpenCivil Terminal...")
    subprocess.Popen(command, shell=True)
except Exception as e:
    print(f"Error launching window: {e}")
