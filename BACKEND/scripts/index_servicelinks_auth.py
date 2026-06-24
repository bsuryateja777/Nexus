#!/usr/bin/env python3
"""
Index ServiceLinks using Entra ID / Managed Identity authentication
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from azure.search.documents import SearchClient
from azure.identity import DefaultAzureCredential

# Fix encoding on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env.local
env_file = Path(__file__).parent.parent / ".env.local"
print(f"Loading env from: {env_file}")
load_dotenv(env_file, override=True)

# Get config
service_name = os.getenv("AZURE_SEARCH_SERVICE_NAME")
index_name = os.getenv("AZURE_SEARCH_SERVICELINKS_INDEX")

print(f"Service: {service_name}")
print(f"Index: {index_name}")

if not service_name or not index_name:
    print("❌ Missing AZURE_SEARCH_SERVICE_NAME or AZURE_SEARCH_SERVICELINKS_INDEX")
    sys.exit(1)

# Initialize with Entra ID / Managed Identity
endpoint = f"https://{service_name}.search.windows.net"
print(f"\n🔐 Using Entra ID / Managed Identity authentication...")

try:
    credential = DefaultAzureCredential()
    search_client = SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)
    print(f"✓ Connected to {endpoint}")
except Exception as e:
    print(f"❌ Authentication failed: {str(e)}")
    print("\nMake sure you're logged in:")
    print("  az login")
    sys.exit(1)

# Read ServiceLinks.csv
csv_path = Path(__file__).parent.parent.parent / "ServiceLinks.csv"
print(f"\nReading: {csv_path}\n")

documents = []
with open(csv_path, 'r') as f:
    # Skip header
    next(f)

    for idx, line in enumerate(f):
        parts = [p.strip() for p in line.strip().split(',')]
        if len(parts) < 6:
            print(f"⚠️  Skipping line {idx + 2}: not enough columns")
            continue

        partition_key, row_key, title, url, description, doc_type = parts[:6]

        # Determine platform from partition key
        platform = "AWS" if "aws" in partition_key.lower() else "Azure"

        doc = {
            "chunk_id": f"{partition_key}_{row_key}",
            "title": title,
            "url": url,
            "description": description,
            "doc_type": doc_type,
            "platform": platform,
            "service_type": partition_key,  # Store original partition key for filtering
        }
        documents.append(doc)
        print(f"  ✓ [{platform}] {title}")

if not documents:
    print("❌ No documents found")
    sys.exit(1)

print(f"\n📤 Uploading {len(documents)} servicelinks...")

try:
    result = search_client.upload_documents(documents=documents)
    print(f"✅ Successfully indexed {len(documents)} servicelinks")
    sys.exit(0)
except Exception as e:
    print(f"❌ Upload failed: {str(e)}")
    sys.exit(1)
