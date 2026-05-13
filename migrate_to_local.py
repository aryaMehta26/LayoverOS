import os
import json
import time
from dotenv import load_dotenv
from langchain_voyageai import VoyageAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

load_dotenv()

# Configuration
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
DATA_FILE = "sfo_amenities.json"
INDEX_FOLDER = "faiss_index_SFO" # Partitioned by Airport Code

def migrate():
    if not VOYAGE_API_KEY:
        print("❌ Error: VOYAGE_API_KEY not found in .env")
        return

    print(f"📖 Loading data from {DATA_FILE}...")
    try:
        with open(DATA_FILE, "r") as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        print(f"❌ {DATA_FILE} not found! Run get_sfo_data.py or restore from backup.")
        return

    print(f"📦 Found {len(raw_data)} items.")

    # Convert to Documents
    docs = []
    for item in raw_data:
        page_content = f"{item['name']} ({item['type']}). Located in {item['terminal']}. {item.get('desc', '')}"
        metadata = {
            "name": item["name"],
            "type": item["type"],
            "terminal": item["terminal"],
            "status": "OPEN",
            "lat": item["lat"],
            "lon": item["lon"]
        }
        docs.append(Document(page_content=page_content, metadata=metadata))

    # Initialize Embeddings
    print("🧠 Initializing Voyage AI Embeddings...")
    embeddings = VoyageAIEmbeddings(
        model="voyage-3-large", 
        voyage_api_key=VOYAGE_API_KEY
    )

    # Create Dictionary
    print("🏗️  Building Local FAISS Index (This may take a moment)...")
    vector_store = FAISS.from_documents(docs, embeddings)

    # Save to Disk
    print(f"💾 Saving index to '{INDEX_FOLDER}'...")
    vector_store.save_local(INDEX_FOLDER)
    
    print("\n✅ Migration Complete!")
    print(f"   You can now search completely offline (assuming embeddings are cached or swapped).")
    print(f"   To test: Run a script loading FAISS.load_local('{INDEX_FOLDER}', embeddings)")

if __name__ == "__main__":
    migrate()
