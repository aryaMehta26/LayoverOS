import os
import operator
import time
import json
import math
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from typing import TypedDict, Annotated, List, Optional, Any
from dotenv import load_dotenv

# LangGraph & LangChain imports
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage

try:
    from pymongo import MongoClient
except Exception:
    MongoClient = None

try:
    from langchain_voyageai import VoyageAIEmbeddings
except Exception:
    VoyageAIEmbeddings = None

try:
    from langchain_fireworks import ChatFireworks
except Exception:
    ChatFireworks = None

def _post_json(url: str, payload: dict, timeout: int = 30) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class _LLMResponse:
    def __init__(self, content: str):
        self.content = content


class OllamaClient:
    def __init__(self, base_url: str, chat_model: str, embed_model: str):
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embed_model = embed_model

    def invoke(self, messages: Any):
        if isinstance(messages, str):
            payload_messages = [{"role": "user", "content": messages}]
        else:
            payload_messages = []
            for message in messages:
                role = "user"
                if isinstance(message, SystemMessage):
                    role = "system"
                elif isinstance(message, HumanMessage):
                    role = "user"
                payload_messages.append({"role": role, "content": getattr(message, "content", str(message))})

        payload = {
            "model": self.chat_model,
            "messages": payload_messages,
            "stream": False,
        }

        result = _post_json(f"{self.base_url}/api/chat", payload)
        content = result.get("message", {}).get("content", "")
        return _LLMResponse(content)

    def embed_query(self, text: str) -> List[float]:
        payloads = [
            (f"{self.base_url}/api/embeddings", {"model": self.embed_model, "prompt": text}),
            (f"{self.base_url}/api/embed", {"model": self.embed_model, "input": text}),
        ]

        last_error = None
        for url, payload in payloads:
            try:
                result = _post_json(url, payload)
                if "embedding" in result:
                    return result.get("embedding", [])
                if "embeddings" in result and result["embeddings"]:
                    return result["embeddings"][0]
            except Exception as error:
                last_error = error

        if last_error:
            raise last_error
        return []


def _cosine_similarity(left: List[float], right: List[float]) -> float:
    if not left or not right:
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(left_value * right_value for left_value, right_value in zip(left, right)) / (left_norm * right_norm)


def _normalize_terminal(terminal: str) -> str:
    return terminal.lower().replace("terminal", "").replace(" ", "").strip()


def _load_local_amenities() -> List[dict]:
    data_path = os.getenv("LOCAL_AMENITIES_PATH", "sfo_amenities.json")
    if not os.path.exists(data_path):
        return []

    try:
        with open(data_path, "r", encoding="utf-8") as handle:
            raw_items = json.load(handle)
    except Exception as error:
        print(f"❌ Failed to load local amenities: {error}")
        return []

    normalized_items = []
    for item in raw_items:
        terminal = item.get("terminal", "General Area")
        normalized_items.append(
            {
                "airport_code": "SFO",
                "name": item.get("name", "Unknown Place"),
                "type": item.get("type", "amenity"),
                "terminal": terminal,
                "terminal_normalized": _normalize_terminal(terminal),
                "status": "OPEN",
                "wait_time": "5 mins",
                "desc": item.get("desc", ""),
                "page_content": f"{item.get('name', 'Unknown Place')} ({item.get('type', 'amenity')}). Located in {terminal}. {item.get('desc', '')}",
                "lat": item.get("lat"),
                "lon": item.get("lon"),
            }
        )

    return normalized_items


def _keyword_score(query_text: str, doc_text: str) -> float:
    query_tokens = {token for token in query_text.lower().split() if token}
    doc_tokens = {token for token in doc_text.lower().split() if token}
    if not query_tokens or not doc_tokens:
        return 0.0
    return len(query_tokens & doc_tokens) / len(query_tokens | doc_tokens)


# Load environment variables early so local paths and model settings are available.
load_dotenv()

LOCAL_AMENITY_DOCS = _load_local_amenities()
LOCAL_DOC_EMBEDDINGS: List[List[float]] = []
LOCAL_EMBEDDING_CLIENT: Optional[OllamaClient] = None


def _build_local_embeddings(embedding_client: Optional[OllamaClient]) -> None:
    global LOCAL_DOC_EMBEDDINGS
    if LOCAL_DOC_EMBEDDINGS or not LOCAL_AMENITY_DOCS or embedding_client is None:
        return

    try:
        LOCAL_DOC_EMBEDDINGS = [embedding_client.embed_query(doc["page_content"]) for doc in LOCAL_AMENITY_DOCS]
        print(f"🦙 Loaded {len(LOCAL_DOC_EMBEDDINGS)} local amenity embeddings from {os.getenv('LOCAL_AMENITIES_PATH', 'sfo_amenities.json')}")
    except Exception as error:
        print(f"⚠️ Local embedding load failed: {error}. Falling back to lexical search.")
        LOCAL_DOC_EMBEDDINGS = []


def _local_semantic_search(query_text: str, airport_code: str, terminal_match: Optional[str] = None, limit: int = 3) -> List[str]:
    airport_code = airport_code.upper().strip()
    if airport_code != "SFO":
        return ["⚠️ Local semantic search is currently loaded for SFO only. Switch to SFO for the full demo."]

    candidates = [doc for doc in LOCAL_AMENITY_DOCS if doc.get("airport_code") == airport_code]
    if terminal_match:
        normalized_terminal = _normalize_terminal(terminal_match)
        candidates = [doc for doc in candidates if doc.get("terminal_normalized") == normalized_terminal]

    if not candidates:
        return []

    scored_docs = []
    embedding_client = LOCAL_EMBEDDING_CLIENT or embeddings
    if embedding_client is not None:
        try:
            query_vector = embedding_client.embed_query(query_text)
            if LOCAL_DOC_EMBEDDINGS and len(LOCAL_DOC_EMBEDDINGS) == len(LOCAL_AMENITY_DOCS):
                for doc in candidates:
                    doc_index = LOCAL_AMENITY_DOCS.index(doc)
                    score = _cosine_similarity(query_vector, LOCAL_DOC_EMBEDDINGS[doc_index])
                    scored_docs.append((score, doc))
            else:
                for doc in candidates:
                    scored_docs.append((_keyword_score(query_text, doc["page_content"]), doc))
        except Exception as error:
            print(f"⚠️ Local search embedding error: {error}")
            for doc in candidates:
                scored_docs.append((_keyword_score(query_text, doc["page_content"]), doc))
    else:
        for doc in candidates:
            scored_docs.append((_keyword_score(query_text, doc["page_content"]), doc))

    scored_docs.sort(key=lambda item: item[0], reverse=True)

    formatted_results = []
    for _, doc in scored_docs[:limit]:
        status_icon = "🟢 OPEN" if doc.get("status") == "OPEN" else "🔴 CLOSED"
        formatted_results.append(
            f"- **{doc.get('name', 'Unknown Place')}** ({doc.get('terminal', 'General Area')})\n"
            f"  Status: {status_icon} | Wait: {doc.get('wait_time', '5 mins')}\n"
            f"  {doc.get('desc', '')}"
        )

    return formatted_results


# --- CONFIGURATION ---
OFFLINE_MODE = True # User asked to migrate off the cluster
LOCAL_INDEX_PATH = "faiss_index"

MONGO_URI = os.getenv("MONGO_URI")
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2:latest")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "mxbai-embed-large:latest")
DB_NAME = "layover_os"
COLLECTION_NAME = "amenities"
FLIGHTS_COLLECTION = "flights"
INDEX_NAME = "vector_index"

# Initialize Connections (Conditional)
client = None
db = None
collection = None
flights_collection = None
vector_store = None

embeddings = None
if VOYAGE_API_KEY and VoyageAIEmbeddings is not None:
    embeddings = VoyageAIEmbeddings(model="voyage-3-large", voyage_api_key=VOYAGE_API_KEY)
    print("🧠 Voyage AI embeddings enabled")
else:
    print("🦙 Voyage AI not configured. Using local Ollama embeddings and lexical fallback.")

# Global Cache for Lazy Loading
loaded_indexes = {}

def get_airport_index(airport_code):
    """
    Retrieves the vector store for a specific airport.
    - In OFFLINE_MODE: Lazy loads 'faiss_index_{CODE}' from disk.
    - In ONLINE_MODE: Returns the global MongoDB vector_store.
    """
    if not VOYAGE_API_KEY or VoyageAIEmbeddings is None:
        return None

    if not OFFLINE_MODE:
        return vector_store # Global variable from Online setup

    # Normalize code (just in case)
    code = airport_code.upper().strip()
    
    # 1. Check RAM Cache
    if code in loaded_indexes:
        return loaded_indexes[code]
    
    # 2. Load from Disk
    # We look for "faiss_index_SFO", "faiss_index_JFK", etc.
    index_path = f"faiss_index_{code}"
    
    if os.path.exists(index_path):
        print(f"📂 Loading Index for {code} from '{index_path}'...")
        try:
            from langchain_community.vectorstores import FAISS
            index = FAISS.load_local(
                index_path, 
                embeddings, 
                allow_dangerous_deserialization=True
            )
            loaded_indexes[code] = index
            print(f"✅ Loaded {code} Index into RAM!")
            return index
        except Exception as e:
            print(f"❌ Failed to load {code} index: {e}")
            return None
    else:
        # Fallback: Try generic 'faiss_index' if specific one missing (backward compatibility)
        if os.path.exists("faiss_index"):
            print(f"⚠️ Specific index '{index_path}' not found. Falling back to generic 'faiss_index'.")
            return get_airport_index("GENERIC") # Recursive cleverness or just load it here
        
        print(f"⚠️ Index not found for {code} at '{index_path}'")
        return None

if OFFLINE_MODE:
    print("🛡️  OFFLINE MODE DETECTED: Vector Store will be loaded dynamically per airport.")
    # Pre-check if SFO exists just to give feedback at startup
    if os.path.exists("faiss_index_SFO"):
        print("✅ Found 'faiss_index_SFO' on disk.")
    elif os.path.exists("faiss_index"):
        print("⚠️ Found generic 'faiss_index'. Will use as fallback.")
    else:
        print("❌ No local indexes found. Run 'migrate_to_local.py'.")

else:
    # ONLINE MODE - Connect to Mongo
    if not MONGO_URI or MongoClient is None:
        print("❌ ERROR: Missing MONGO_URI in .env")
        exit(1)
        
    try:
        client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        flights_collection = db[FLIGHTS_COLLECTION]
        
        from langchain_mongodb import MongoDBAtlasVectorSearch
        vector_store = MongoDBAtlasVectorSearch(
            collection=collection,
            embedding=embeddings,
            index_name=INDEX_NAME,
            relevance_score_fn="cosine",
        )
        print("✅ Connected to MongoDB Atlas")
    except Exception as e:
        print(f"❌ Connection failed: {e}")

class ResilientLLM:
    def __init__(self):
        self.fireworks = None
        self.ollama = OllamaClient(
            base_url=OLLAMA_BASE_URL,
            chat_model=OLLAMA_CHAT_MODEL,
            embed_model=OLLAMA_EMBED_MODEL,
        )

        if FIREWORKS_API_KEY and ChatFireworks is not None:
            try:
                self.fireworks = ChatFireworks(
                    model="accounts/fireworks/models/llama-v3p3-70b-instruct",
                    api_key=FIREWORKS_API_KEY,
                    max_retries=0,
                    request_timeout=10,
                )
                print("🧠 Fireworks AI connected")
            except Exception as error:
                print(f"⚠️ Fireworks init failed: {error}")

        try:
            global LOCAL_EMBEDDING_CLIENT
            LOCAL_EMBEDDING_CLIENT = self.ollama
            _build_local_embeddings(self.ollama)
            print(f"🦙 Ollama local model ready at {OLLAMA_BASE_URL} ({OLLAMA_CHAT_MODEL})")
        except Exception as error:
            print(f"⚠️ Ollama init failed: {error}")

    def invoke(self, messages: Any):
        try:
            return self.ollama.invoke(messages)
        except Exception as error:
            print(f"⚠️ Ollama request failed: {error}")

        if self.fireworks:
            try:
                return self.fireworks.invoke(messages)
            except Exception as error:
                print(f"⚠️ Fireworks fallback failed: {error}")

        return _LLMResponse(
            "I can help with airport amenities, flights, and passes. Try asking for coffee, restrooms, or flight status."
        )


llm = ResilientLLM()

print("✅ LayoverOS runtime initialized")

# --- STATE DEFINITION ---
class AgentState(TypedDict):
    messages: Annotated[List[str], operator.add]
    user_location: str   # e.g., "Terminal 2"
    airport_code: str    # e.g., "SFO", "JFK", "DEN"
    flight_number: str   # e.g., "UA400" (Persisted)
    next_step: str

# --- NODE DEFINITIONS ---

def supervisor_node(state: AgentState):
    raw_msg = state['messages'][-1]
    if hasattr(raw_msg, 'content'):
        last_message = raw_msg.content.lower()
    else:
        last_message = str(raw_msg).lower()
    
    import re
    
    # 0. Context Switching (Airport Code)
    # Check if user mentioned a supported airport to switch context
    found_airport = None
    for code in ["SFO", "JFK", "DEN"]:
        if code in last_message.upper():
            found_airport = code
            print(f"✈️ Context Switch Detected: {found_airport}")
            break
            
    # 1. Check for Strong Flight Signals
    # We only trigger flight logic if user EXPLICITLY asks for it or provides a code (e.g. UA400)
    has_flight_code = re.search(r'[A-Z]{2}\d{3,4}', last_message.upper())
    has_flight_keyword = any(kw in last_message for kw in ["flight", "fly", "airline", "boarding"])
    is_planning_trip = "plan" in last_message and "to" in last_message # e.g. "Plan trip to JFK"
    
    if has_flight_keyword or has_flight_code or is_planning_trip:
        return {"next_step": "flight_tracker", "airport_code": found_airport} if found_airport else {"next_step": "flight_tracker"}
        
    # 2. Check for Payment Intent
    elif any(kw in last_message for kw in ["buy", "pay", "book", "purchase", "reserve"]):
        return {"next_step": "bursar", "airport_code": found_airport} if found_airport else {"next_step": "bursar"}
        
    # 3. Default: Amenity Search (The Safety Net)
    # "I am at SFO" -> Scout
    # "Where is coffee?" -> Scout
    else:
        return {"next_step": "scout", "airport_code": found_airport} if found_airport else {"next_step": "scout"}

def scout_node(state: AgentState):
    raw_msg = state['messages'][-1]
    if hasattr(raw_msg, 'content'):
        query_text = raw_msg.content
    else:
        query_text = str(raw_msg)
    airport = state.get('airport_code', 'SFO') # Default to SFO
    
    print(f"\n[Scout] Searching '{query_text}' in {airport}...")

    # --- CONCIERGE MODE (Context Setting) ---
    # If user just says "I am at SFO", don't search. Ask for details.
    query_lower = query_text.lower().strip()

    # --- CONCIERGE MODE (Context Setting) ---
    # If user just says "I am at SFO", don't search. Ask for details.
    if len(query_text.split()) < 5 and ("at" in query_text.lower() or "in" in query_text.lower()) and airport.lower() in query_text.lower():
        # User is setting context: "I am at SFO"
        if llm:
            try:
                sys_msg = SystemMessage(content=f"You are a helpful Concierge at {airport}. The user just arrived. Ask them TWO things: which Terminal they are in, and what amenity they are looking for. Keep it short.")
                human_msg = HumanMessage(content=query_text)
                ai_msg = llm.invoke([sys_msg, human_msg])
                return {"messages": [ai_msg.content]}
            except Exception as e:
                print(f"❌ LLM Concierge Error: {e}")
                return {"messages": ["Concierge: Welcome! Which terminal are you in, and what are you looking for?"]}
        else:
            return {"messages": ["Concierge: Welcome! Which terminal are you in, and what are you looking for?"]}
    
    # --- TERMINAL FILTERING ---
    import re
    terminal_match = re.search(r'Terminal\s+(\w+)', query_text, re.IGNORECASE)
    
    # Base filter: Airport matches
    search_filter = {"airport_code": {"$eq": airport}}
    
    if terminal_match:
        target_terminal = terminal_match.group(1)
        # Try to match the format in DB (usually just the number/letter)
        # We add it to the filter logic
        print(f"🎯 Filtering for Terminal: {target_terminal}")
        search_filter["terminal_id"] = {"$eq": target_terminal}

    # --- PRO FILTERING ---
    # We only show results for the CURRENT AIRPORT (and Terminal if specified)
    # --- UNIFIED SEARCH (FAISS OR MONGO) ---
    found_items = []
    
    # DYNAMIC LOADING: Get the correct index for this airport
    current_vector_store = get_airport_index(airport)

    if current_vector_store and embeddings is not None:
        try:
            print(f"🔍 Searching Vector Store for: '{query_text}'")
            # Unified LangChain search (works for both FAISS and Mongo)
            # Returns list of (Document, score) tuples
            results = current_vector_store.similarity_search_with_score(query_text, k=3)
            
            for doc, score in results:
                meta = doc.metadata
                name = meta.get("name", "Unknown Place")
                # In our seed, page_content is the rich description. 
                # meta['desc'] isn't always there/populated, so use doc.page_content.
                desc = doc.page_content 
                location = meta.get("terminal", "General Area")
                
                # Default fallback for status
                status = meta.get("status", "OPEN")
                wait = meta.get("wait_time", "5 mins")
                
                status_icon = "🟢 OPEN" if status == "OPEN" else "🔴 CLOSED"
                
                found_items.append(
                    f"- **{name}** ({location})\n"
                    f"  Status: {status_icon} | Wait: {wait}\n"
                    f"  {desc}"
                )
                
            print(f"✅ Found {len(results)} matches.")

        except Exception as e:
            print(f"❌ Search Error: {e}")
            found_items.append("⚠️ Database Search Error.")
    else:
        found_items = _local_semantic_search(query_text, airport, terminal_match.group(1) if terminal_match else None)
    
    if not found_items:
        response = f"Scout: I couldn't find anything matching '{query_text}' at {airport}."
    else:
        context = "\n".join(found_items)
        if llm:
             # Natural Language Synthesis
            sys_msg = SystemMessage(
                content=f"You are LayoverOS, an advanced operating system for travel. {airport}. "
                        "The user is on a layover. Optimize their time based on the amenities found. "
                        "Keep it short, professional, and helpful. Mention the location (terminal) and status."
            )
            human_msg = HumanMessage(content=f"User Request: {query_text}\n\nContext Options:\n{context}")
            try:
                ai_msg = llm.invoke([sys_msg, human_msg])
                response = ai_msg.content
            except Exception as e:
                print(f"❌ LLM Error: {e}") 
                response = f"Scout: Here are the options I found based on your request:\n{context}"
        else:
            # Fallback
            response = f"Scout: Here are the top options at {airport}:\n\n" + "\n".join(found_items)
        
    return {"messages": [response]}

def flight_node(state: AgentState):
    """
    Looks up flight details in the 'flights' collection.
    """
    raw_msg = state['messages'][-1]
    if hasattr(raw_msg, 'content'):
        last_message = raw_msg.content.upper()
    else:
        last_message = str(raw_msg).upper()
    print(f"\n[FlightTracker] Analyzing: {last_message}")
    
    # Simple extraction: look for typical flight codes like "UA123"
    # In a hackathon, we can just search the collection for *any* match in the text
    # or grab the first word that looks like a flight number.
    
    # Strategy: Regex or just simple substring search if logic is too complex
    # Let's try searching text index if it exists, or just regex find
    
    # Hackathon Shortcut: Search for typical prefixes
    import re
    # 1. Try to find in current message
    import re
    match = re.search(r'([A-Z]{2}\d{3,4})', last_message)
    
    current_flight = state.get('flight_number')
    
    if match:
        flight_num = match.group(1)
        print(f"Detected Flight Number: {flight_num}")
        # SAVE TO STATE!
        # (Note: In LangGraph, returning a key updates that key in the state)
        
    elif current_flight:
        # Use memory
        flight_num = current_flight
        print(f"Using Remembered Flight: {flight_num}")
    else:
        flight_num = None

    if flight_num:
        doc = flights_collection.find_one({"flight_number": flight_num})
        
        if doc:
            status = doc.get('status', 'Unknown')
            gate = doc.get('gate', 'TBD')
            dest = doc.get('destination', 'Unknown')
            
            if llm:
                try:
                    sys_msg = SystemMessage(content="You are a Flight Tracker. Inform the user about their flight status clearly.")
                    # We mention the flight number in the human msg context so LLM knows it
                    human_msg = HumanMessage(content=f"Flight: {flight_num} to {dest}. Status: {status}. Gate: {gate}. \nUser asked: {last_message}")
                    ai_msg = llm.invoke([sys_msg, human_msg])
                    response = ai_msg.content
                except Exception as e:
                    print(f"❌ LLM Error (FlightNode): {e}")
                    response = f"✈️ **Flight {flight_num} to {dest}**\nStatus: **{status}**\nGate: {gate}"
            else:
                response = f"✈️ **Flight {flight_num} to {dest}**\nStatus: **{status}**\nGate: {gate}"
                
            return {"messages": [response], "flight_number": flight_num}
        else:
            # If not found, CLEAR the state so we don't get stuck on a typo
            response = f"FlightTracker: I couldn't find flight {flight_num} in our database. Please double-check the number (e.g., UA400)."
            return {"messages": [response], "flight_number": ""}
    else:
        # Fallback search in flights collection using text if no regex match?
        # For hackathon, just ask for clarity
        if llm:
            try:
                 response = llm.invoke("User wants to find a flight but didn't provide a number. Ask them for it politely. Keep it short.").content
            except Exception as e:
                 print(f"❌ LLM Flight Fallback Error: {e}")
                 response = "FlightTracker: I can help with that. What is the flight number? (e.g., UA400)"
        else:
             response = "FlightTracker: I can help with that. What is the flight number? (e.g., UA400)"
             
        return {"messages": [response]}

def bursar_node(state: AgentState):
    """
    Process payment requests for lounge bookings (Web3/Coinbase)
    """
    print("\n[Bursar] Processing Lounge Booking & Payment...")
    
    raw_msg = state['messages'][-1]
    query = raw_msg.lower() if hasattr(raw_msg, 'content') else str(raw_msg).lower()
    
    # Lounge database
    lounges = {
        "united club": {
            "id": "united_club_sfo",
            "name": "United Club",
            "terminal": "Terminal 3",
            "price": 50,
            "description": "Premium lounge with bar, buffet, showers"
        },
        "centurion lounge": {
            "id": "centurion_lounge_sfo",
            "name": "Centurion Lounge",
            "terminal": "Terminal 3",
            "price": 75,
            "description": "Ultra-premium lounge for AmEx Platinum"
        },
        "freshen up": {
            "id": "freshen_up_sfo",
            "name": "Freshen Up",
            "terminal": "International G",
            "price": 40,
            "description": "Showers and nap pods"
        }
    }
    
    # Detect which lounge user wants
    matched_lounge = None
    for lounge_name, details in lounges.items():
        if lounge_name in query:
            matched_lounge = details
            break
    
    if matched_lounge:
        # Generate payment prompt
        response = (
            f"[PAYMENT_REQUIRED] "
            f"Booking: **{matched_lounge['name']}** ({matched_lounge['terminal']}) | "
            f"{matched_lounge['price']} USDC (Web3 Payment via Coinbase Commerce)"
        )
        print(f"💰 [Web3] Booking: {matched_lounge['name']} - ${matched_lounge['price']} USDC")
        return {"messages": [response]}
    else:
        # Ask which lounge
        response = (
            "Which lounge would you like to book?\n\n"
            "1. **United Club** (Terminal 3) - 50 USDC\n"
            "   Premium with bar, buffet, showers\n\n"
            "2. **Centurion Lounge** (Terminal 3) - 75 USDC\n"
            "   Ultra-premium for AmEx Platinum\n\n"
            "3. **Freshen Up** (International G) - 40 USDC\n"
            "   Quick refresh with showers"
        )
        return {"messages": [response]}

# --- GRAPH CONSTRUCTION ---

builder = StateGraph(AgentState)

builder.add_node("supervisor", supervisor_node)
builder.add_node("scout", scout_node)
builder.add_node("flight_tracker", flight_node)
builder.add_node("bursar", bursar_node)

builder.add_edge(START, "supervisor")

def router(state: AgentState):
    return state["next_step"]

builder.add_conditional_edges(
    "supervisor",
    router,
    {
        "scout": "scout",
        "flight_tracker": "flight_tracker",
        "bursar": "bursar"
    }
)

builder.add_edge("scout", END)
builder.add_edge("flight_tracker", END)
builder.add_edge("bursar", END)

# --- PERSISTENCE ---
from langgraph.checkpoint.memory import MemorySaver

try:
    from langgraph.checkpoint.mongodb import MongoDBSaver
except Exception:
    MongoDBSaver = None

if OFFLINE_MODE:
    print("💾 Using MemorySaver (Online Persistence Disabled)")
    checkpointer = MemorySaver()
else:
    if client and MongoDBSaver is not None:
        checkpointer = MongoDBSaver(client=client)
    else:
        checkpointer = MemorySaver() # Fallback

app = builder.compile(checkpointer=checkpointer)


# --- CLI TEST RUNNER ---
if __name__ == "__main__":
    print("🚀 LayoverOS (REAL MODE) Started.")
    
    # Mock Config
    config = {"configurable": {"thread_id": "test_thread"}}
    current_state = {
        "messages": [], 
        "user_location": "Terminal 2",
        "airport_code": "SFO" # Default for CLI
    }
    
    while True:
        try:
            user_input = input("\nUser (Type 'quit' to exit): ")
            if user_input.lower() in ["quit", "exit"]:
                break
            
            # Allow CLI user to switch airport context manually for testing
            if user_input.startswith("/airport"):
                new_code = user_input.split(" ")[1].upper()
                current_state["airport_code"] = new_code
                print(f"✈️ Switched context to {new_code}")
                continue

            current_state["messages"].append(user_input)
            output = app.invoke(current_state, config=config)
            print(f"\n{output['messages'][-1]}")
            current_state = output
        except Exception as e:
            print(f"Error: {e}")
