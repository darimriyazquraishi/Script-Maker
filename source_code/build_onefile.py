import subprocess
import sys
import os
import shutil
import time
from pathlib import Path


def main():
    print("Building ScriptMaker Standalone Single-File (onefile) EXE...")
    
    python_exe = sys.executable
    cmd = [python_exe, "-m", "PyInstaller", "--clean", "-y", "ScriptMaker_onefile.spec"]
    
    print("Executing:", " ".join(cmd))
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        exe_path = Path("dist") / "ScriptMaker.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print("\n" + "=" * 65)
            print("[SUCCESS] Standalone Single-File EXE created successfully!")
            print(f"  Path: {exe_path.resolve()} ({size_mb:.1f} MB)")
            print("=" * 65 + "\n")
        else:
            print("[ERROR] PyInstaller reported success but ScriptMaker.exe was not found in dist/")
            sys.exit(1)
    else:
        print(f"[ERROR] PyInstaller failed with exit code {result.returncode}")
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
