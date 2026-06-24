#!/usr/bin/env python3
import os
from pathlib import Path
from dotenv import load_dotenv

# Show .env.local path
env_file = Path(__file__).parent.parent / ".env.local"
print(f"Looking for: {env_file}")
print(f"Exists: {env_file.exists()}")

if env_file.exists():
    print(f"\nFile size: {env_file.stat().st_size} bytes")
    print("\nRaw content:")
    with open(env_file, 'r') as f:
        content = f.read()
        print(content[:500])

    print("\n" + "="*60)
    print("Loading with python-dotenv...")
    load_dotenv(env_file, override=True)

    print("\nEnvironment variables found:")
    print(f"  AZURE_SEARCH_SERVICE_NAME = {os.getenv('AZURE_SEARCH_SERVICE_NAME')}")
    print(f"  AZURE_SEARCH_ADMIN_KEY = {os.getenv('AZURE_SEARCH_ADMIN_KEY')[:20] if os.getenv('AZURE_SEARCH_ADMIN_KEY') else 'NOT SET'}...")
    print(f"  AZURE_SEARCH_SERVICELINKS_INDEX = {os.getenv('AZURE_SEARCH_SERVICELINKS_INDEX')}")
else:
    print(f"❌ File not found!")
