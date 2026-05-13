import os
from agent_graph import app
from dotenv import load_dotenv

load_dotenv()

print("🎬 Running FINAL 15-STEP DEMO VERIFICATION...")

from langchain_core.messages import HumanMessage

def run_query(query, expected_keyword):
    print(f"\n👤 User: {query}")
    try:
        result = app.invoke(
            {"messages": [HumanMessage(content=query)], "airport_code": "SFO"},
            {"recursion_limit": 5, "configurable": {"thread_id": "demo_verification_1"}}
        )
        last_msg = result["messages"][-1]
        content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
        
        # Lowercase for loose matching
        content_lower = content.lower()
        expected_lower = expected_keyword.lower()
        
        if expected_lower in content_lower:
             print(f"✅ SUCCESS: Response contains '{expected_keyword}'")
             # print(f"   Preview: {content[:100]}...")
             return True
        else:
             print(f"❌ FAIL: Expected '{expected_keyword}' but got: {content[:100]}...")
             return False
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        return False

# The 15 Safe Queries
queries = [
    ("I am at SFO", "Welcome"),
    ("Find coffee in Terminal 2", "Peet's"),
    ("Track flight UA400", "UA400"),
    ("Book a pass for the United Club", "PAYMENT_REQUIRED"),
    ("Where is the united club?", "Terminal 3"),
    ("Find vegetarian food in terminal 2", "Napa Farms"),
    ("Is there a yoga room?", "Yoga Room"),
    ("Where are the restrooms?", "Restrooms"),
    ("Find a charging station", "Workstations"),
    ("Where is the nearest bar?", "Lark Creek"),
    ("Is there a kids play area?", "Kids' Spot"),
    ("Find a place to sleep", "Freshen Up"),
    ("Where is the centurion lounge?", "Centurion"),
    ("List italian restaurants", "Cat Cora"),
    ("Show secure payment terminals", "Secure Payment"),
]

passed = 0
for q, k in queries:
    if run_query(q, k):
        passed += 1

print(f"\n📢 RESULTS: {passed}/{len(queries)} Passed.")
