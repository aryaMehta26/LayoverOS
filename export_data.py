import os
import json
import time
from pymongo import MongoClient
from dotenv import load_dotenv
from bson import json_util

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
BACKUP_DIR = "backup_data"

def export_data():
    if not MONGO_URI:
        print("❌ Error: MONGO_URI not found.")
        return

    print("🔌 Connecting to MongoDB...")
    try:
        client = MongoClient(MONGO_URI)
        print("✅ Connected!")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    # Create backup dir
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

    # Target Databases
    target_dbs = ["LayoverOS", "layover_os"]
    
    found_any = False

    for db_name in target_dbs:
        if db_name not in client.list_database_names():
            print(f"⚠️  Database '{db_name}' not found on server.")
            continue
        
        found_any = True
        print(f"\n📂 Backing up Database: {db_name}")
        db = client[db_name]
        
        for coll_name in db.list_collection_names():
            print(f"   - Exporting collection: {coll_name}")
            collection = db[coll_name]
            
            # Fetch all documents
            cursor = collection.find({})
            documents = list(cursor)
            
            # Serialize to JSON (using json_util for ObjectId/Dates)
            file_path = os.path.join(BACKUP_DIR, f"{db_name}_{coll_name}.json")
            with open(file_path, "w") as f:
                f.write(json_util.dumps(documents, indent=2))
            
            print(f"     ✅ Saved {len(documents)} docs to {file_path}")

    if not found_any:
        print("\n❌ No target databases found! Check spelling or permissions.")
    else:
        print(f"\n🎉 Backup complete! stored in '/{BACKUP_DIR}'")
        print("Keep these files safe. You can restore them to a new cluster later.")

if __name__ == "__main__":
    export_data()
