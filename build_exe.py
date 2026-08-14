import subprocess
import sys
import os
import shutil
import time
from pathlib import Path


def clean_dir(path: Path):
    if not path.exists():
        return
    for attempt in range(5):
        try:
            shutil.rmtree(path)
            break
        except Exception:
            time.sleep(0.5)


def main():
    print("Building ScriptMaker Instant-Startup Portable Folder...")
    
    dist_app_dir = Path("dist") / "ScriptMaker"
    clean_dir(dist_app_dir)

    python_exe = sys.executable
    cmd = [python_exe, "-m", "PyInstaller", "--clean", "-y", "ScriptMaker.spec"]
    
    print("Executing:", " ".join(cmd))
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        exe_path = dist_app_dir / "ScriptMaker.exe"
        
        if exe_path.exists():
            # Copy llama folder into dist/ScriptMaker/llama
            src_llama = Path("llama")
            dst_llama = dist_app_dir / "llama"
            if src_llama.exists() and src_llama.is_dir():
                print("Copying llama engine into dist/ScriptMaker/llama ...")
                clean_dir(dst_llama)
                shutil.copytree(src_llama, dst_llama, dirs_exist_ok=True)
            
            # Ensure models folder exists in dist/ScriptMaker/models
            dst_models = dist_app_dir / "models"
            dst_models.mkdir(exist_ok=True)
            
            print("\n" + "=" * 65)
            print("[SUCCESS] Instant-Startup Portable App created successfully!")
            print(f"  Folder:    {dist_app_dir.resolve()}")
            print(f"  Executable: {exe_path.resolve()}")
            print("=" * 65 + "\n")
        else:
            print("[ERROR] PyInstaller reported success but ScriptMaker.exe was not found in dist/ScriptMaker/")
            sys.exit(1)
    else:
        print(f"[ERROR] PyInstaller failed with exit code {result.returncode}")
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
