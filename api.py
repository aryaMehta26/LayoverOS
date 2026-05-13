from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from agent_graph import app
import uvicorn
import os
import json
from datetime import datetime
import hmac
import hashlib

try:
    from coinbase_commerce.client import Client
except ImportError:
    Client = None

# Initialize FastAPI
api = FastAPI(title="LayoverOS API", version="1.0")

# Allow Frontend to Talk to Backend (CORS)
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for Hackathon (or specific ["http://localhost:3000"])
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default_thread"
    user_location: str = "SFO"
    airport_code: str = "SFO"

class ChatResponse(BaseModel):
    response: str
    history: List[str]

class PaymentRequest(BaseModel):
    lounge_name: str
    lounge_id: Optional[str] = None
    amount: Optional[float] = None
    currency: str = "USDC"
    description: Optional[str] = None
    user_id: Optional[str] = None
    email: Optional[str] = None

@api.get("/")
def health_check():
    return {"status": "LayoverOS System Online"}

@api.post("/pay")
def process_payment(request: PaymentRequest):
    """
    Real Coinbase Commerce payment for lounge bookings (Web3)
    """
    # Lounge pricing database
    lounges = {
        "united_club_sfo": {
            "name": "United Club",
            "terminal": "Terminal 3",
            "price_usd": 50.0,
            "currency": "USDC",
            "amenities": ["Open Bar", "Buffet", "Showers", "WiFi"],
            "access_duration": "24 hours",
            "description": "Premium lounge with full bar, buffet, and showers"
        },
        "centurion_lounge_sfo": {
            "name": "Centurion Lounge",
            "terminal": "Terminal 3",
            "price_usd": 75.0,
            "currency": "USDC",
            "amenities": ["Caviar Bar", "Premium Spirits", "Showers", "WiFi"],
            "access_duration": "24 hours",
            "description": "Ultra-premium lounge for AmEx Platinum"
        },
        "freshen_up_sfo": {
            "name": "Freshen Up",
            "terminal": "International G",
            "price_usd": 40.0,
            "currency": "USDC",
            "amenities": ["Showers", "Nap Pods", "Toiletries"],
            "access_duration": "2 hours",
            "description": "Quick refresh with shower facilities"
        }
    }
    
    # Get lounge details
    lounge_id = request.lounge_id or request.lounge_name.lower().replace(" ", "_") + "_sfo"
    lounge = lounges.get(lounge_id)
    
    if not lounge:
        raise HTTPException(status_code=404, detail=f"Lounge {request.lounge_name} not found")
    
    # Try Coinbase if configured
    coinbase_key = os.getenv("COINBASE_API_KEY")
    if coinbase_key and Client:
        try:
            coinbase_client = Client(api_key=coinbase_key)
            
            charge = coinbase_client.charge.create(
                name=f"Lounge Access: {lounge['name']}",
                description=f"LayoverOS - {lounge['description']}",
                local_price={
                    "amount": str(lounge["price_usd"]),
                    "currency": lounge["currency"]
                },
                pricing_type="fixed_price",
                metadata={
                    "user_id": request.user_id or "guest",
                    "lounge": lounge["name"],
                    "terminal": lounge["terminal"],
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            print(f"💰 [Web3] Coinbase charge: {charge.id} | {lounge['name']} | {lounge['price_usd']} USDC")
            
            return {
                "status": "pending",
                "transaction_id": charge.id,
                "payment_url": charge.hosted_url,
                "lounge": lounge["name"],
                "amount": lounge["price_usd"],
                "currency": lounge["currency"],
                "terminal": lounge["terminal"],
                "message": "Redirecting to Coinbase for payment"
            }
        except Exception as e:
            print(f"❌ Coinbase error: {e}")
            raise HTTPException(status_code=400, detail=f"Payment failed: {str(e)}")
    else:
        # Fallback mock (for testing without Coinbase key)
        print(f"💰 [Mock] Payment: {lounge['price_usd']} USDC for {lounge['name']}")
        return {
            "status": "success",
            "transaction_id": f"tx_mock_{int(datetime.now().timestamp())}",
            "lounge": lounge["name"],
            "amount": lounge["price_usd"],
            "currency": lounge["currency"],
            "terminal": lounge["terminal"],
            "message": "Payment processed (mock mode)"
        }

@api.get("/lounges")
def get_lounges():
    """List all available lounges with pricing"""
    lounges = {
        "united_club_sfo": {
            "name": "United Club",
            "terminal": "Terminal 3",
            "price_usd": 50.0,
            "currency": "USDC",
            "amenities": ["Open Bar", "Buffet", "Showers", "WiFi"],
            "access_duration": "24 hours",
            "description": "Premium lounge with full bar, buffet, and showers"
        },
        "centurion_lounge_sfo": {
            "name": "Centurion Lounge",
            "terminal": "Terminal 3",
            "price_usd": 75.0,
            "currency": "USDC",
            "amenities": ["Caviar Bar", "Premium Spirits", "Showers", "WiFi"],
            "access_duration": "24 hours",
            "description": "Ultra-premium lounge for AmEx Platinum"
        },
        "freshen_up_sfo": {
            "name": "Freshen Up",
            "terminal": "International G",
            "price_usd": 40.0,
            "currency": "USDC",
            "amenities": ["Showers", "Nap Pods", "Toiletries"],
            "access_duration": "2 hours",
            "description": "Quick refresh with shower facilities"
        }
    }
    
    return {
        "lounges": [
            {"id": lounge_id, **lounge}
            for lounge_id, lounge in lounges.items()
        ]
    }

@api.post("/webhook/coinbase")
async def handle_coinbase_webhook(request: Request):
    """
    Receive payment confirmations from Coinbase Commerce (Web3)
    """
    body = await request.body()
    signature = request.headers.get("X-CC-Webhook-Signature", "")
    
    webhook_secret = os.getenv("COINBASE_WEBHOOK_SECRET", "")
    
    # Verify signature if secret is configured
    if webhook_secret:
        expected = hmac.new(
            webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        if signature != expected:
            print("❌ Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")
    
    try:
        payload = json.loads(body)
        event_type = payload.get("type")
        
        if event_type == "charge:confirmed":
            charge_id = payload["data"]["id"]
            amount = payload["data"]["pricing"]["local"]["amount"]
            metadata = payload["data"].get("metadata", {})
            
            print(f"✅ [Web3] Payment Confirmed: {charge_id} | {amount} USDC | Lounge: {metadata.get('lounge', 'Unknown')}")
            
            # TODO: Store booking in database
            # TODO: Generate QR code for lounge access
            # TODO: Send confirmation email
            
            return {"status": "success", "message": "Booking confirmed"}
        
        elif event_type == "charge:failed":
            charge_id = payload["data"]["id"]
            print(f"❌ Payment Failed: {charge_id}")
            return {"status": "failed", "message": "Payment declined"}
        
        elif event_type == "charge:created":
            charge_id = payload["data"]["id"]
            print(f"⏳ Payment Initiated: {charge_id}")
            return {"status": "initiated"}
        
        return {"status": "received", "event": event_type}
    
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@api.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """
    Main Chat Endpoint.
    Receives user message -> Runs LangGraph Agent -> Returns Response.
    """
    config = {"configurable": {"thread_id": request.thread_id}}
    
    # Initialize state with the user's location context
    initial_state = {
        "messages": [request.message],
        "user_location": request.user_location,
        # We will add airport_code to the state in agent_graph.py next
    }
    
    try:
        # Run the Agent
        output = app.invoke(initial_state, config=config)
        
        # Extract the last message from the agent
        agent_response = output['messages'][-1]
        
        # In LangGraph/LangChain, messages are often objects, we ensure string format
        if hasattr(agent_response, 'content'):
            response_text = agent_response.content
        else:
            response_text = str(agent_response)

        return ChatResponse(
            response=response_text,
            history=[str(m) for m in output['messages']]
        )
    
    except Exception as e:
        print(f"Error processing chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting LayoverOS API on port {port}...")
    uvicorn.run(api, host="0.0.0.0", port=port)
