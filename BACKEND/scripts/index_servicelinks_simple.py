#!/usr/bin/env python3
"""
Simple standalone script to index ServiceLinks into Azure Cognitive Search
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

# Load .env.local
env_file = Path(__file__).parent.parent / ".env.local"
print(f"Loading env from: {env_file}")
load_dotenv(env_file, override=True)

# Get config
service_name = os.getenv("AZURE_SEARCH_SERVICE_NAME")
admin_key = os.getenv("AZURE_SEARCH_ADMIN_KEY")
index_name = os.getenv("AZURE_SEARCH_SERVICELINKS_INDEX")

print(f"Service: {service_name}")
print(f"Index: {index_name}")
print(f"Admin Key: {admin_key[:10] if admin_key else 'NOT SET'}...")

if not service_name or not admin_key or not index_name:
    print("❌ Missing configuration. Check .env.local")
    sys.exit(1)

# Initialize search client
endpoint = f"https://{service_name}.search.windows.net"
search_client = SearchClient(endpoint=endpoint, index_name=index_name, credential=AzureKeyCredential(admin_key))

print(f"\n✓ Connected to {endpoint}")

# Read ServiceLinks.csv
csv_path = Path(__file__).parent.parent.parent / "ServiceLinks.csv"
print(f"Reading: {csv_path}\n")

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

        doc = {
            "chunk_id": f"{partition_key}_{row_key}",
            "title": title,
            "url": url,
            "description": description,
            "doc_type": doc_type,
            "PartitionKey": partition_key,
            "Key": row_key,
            "chunk": f"{title} {description}",
        }
        documents.append(doc)
        print(f"  ✓ {title}")

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
