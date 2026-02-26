import os
import shutil
import json
from pathlib import Path

DATA_DIR = Path("data")
ENTITY_DIR = DATA_DIR / "entities"

# Clear media folders
for date_dir in DATA_DIR.iterdir():
    if date_dir.is_dir() and date_dir.name != "entities":
        print(f"Removing {date_dir}")
        shutil.rmtree(date_dir)

# Reset entity JSONs
files = ["actors.json", "clothes.json", "scenes.json", "posts.json"]
for f in files:
    path = ENTITY_DIR / f
    if path.exists():
        with open(path, "w") as out:
            json.dump({}, out)
        print(f"Reset {f}")

print("Data cleared!")
