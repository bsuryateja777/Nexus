#!/usr/bin/env python3
"""
Index ServiceLinks CSV data into Azure Cognitive Search with proper metadata fields
"""
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.azure_cognitive_search_service import AzureCognitiveSearchService

def index_servicelinks_from_csv():
    """Index ServiceLinks from CSV file into the servicelinks index"""

    # Initialize search service
    search_service = AzureCognitiveSearchService()

    if not search_service.is_configured():
        print("❌ Cognitive Search not configured")
        return False

    # Get servicelinks index name from env
    servicelinks_index = os.getenv("AZURE_SEARCH_SERVICELINKS_INDEX", "")
    if not servicelinks_index:
        print("❌ AZURE_SEARCH_SERVICELINKS_INDEX not configured")
        return False

    # Get servicelinks client
    servicelinks_client = search_service._get_search_client_for_index(servicelinks_index)
    if not servicelinks_client:
        print(f"❌ Failed to get search client for index: {servicelinks_index}")
        return False

    # Read ServiceLinks.csv
    csv_path = Path(__file__).parent.parent.parent / "ServiceLinks.csv"
    if not csv_path.exists():
        print(f"❌ ServiceLinks.csv not found at: {csv_path}")
        return False

    documents = []
    with open(csv_path, 'r') as f:
        # Skip header
        next(f)

        for idx, line in enumerate(f):
            parts = line.strip().split(',')
            if len(parts) < 6:
                print(f"⚠️  Skipping malformed line {idx + 2}: {line}")
                continue

            partition_key, row_key, title, url, description, doc_type = parts[:6]

            # Create document with metadata fields
            # Use chunk_id as the key field (required by index schema)
            doc = {
                "chunk_id": f"{partition_key}_{row_key}",
                "title": title,
                "url": url,
                "description": description,
                "doc_type": doc_type,
                "PartitionKey": partition_key,
                "Key": row_key,
                # Also include searchable text
                "chunk": f"{title} {description}",
            }

            documents.append(doc)
            print(f"  ✓ {title} -> {url}")

    if not documents:
        print("❌ No documents found in CSV")
        return False

    print(f"\n📤 Uploading {len(documents)} servicelinks to index: {servicelinks_index}")

    try:
        # Batch upload
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i+batch_size]
            servicelinks_client.upload_documents(documents=batch)
            print(f"  ✓ Uploaded batch {i//batch_size + 1}/{(len(documents)-1)//batch_size + 1}")

        print(f"\n✅ Successfully indexed {len(documents)} servicelinks")
        return True

    except Exception as e:
        print(f"❌ Failed to upload documents: {str(e)}")
        return False

if __name__ == "__main__":
    print("ServiceLinks Indexing Tool")
    print("=" * 60)

    if index_servicelinks_from_csv():
        print("\n✅ Done!")
        sys.exit(0)
    else:
        print("\n❌ Failed")
        sys.exit(1)
