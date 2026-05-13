# LayoverOS Data Architecture & Web3 Payment Integration

## 📊 Synthetic Data Structure

### What's in `sfo_amenities.json`
10 synthetic amenities for SFO airport:

```json
{
  "name": "United Club",
  "type": "lounge",
  "terminal": "Terminal 3",
  "desc": "United Club is a lounge at SFO. Near Gate F11.",
  "lat": 37.619,
  "lon": -122.385
}
```

**Data Fields**:
- `name`: Amenity name (for display)
- `type`: Category (cafe, lounge, restaurant, amenity, shop)
- `terminal`: Location identifier
- `desc`: Rich semantic description (used for embeddings)
- `lat/lon`: Geographic coordinates

---

## 🧠 How Data Becomes "Semantic"

### Step 1: Load Raw JSON
```python
LOCAL_AMENITY_DOCS = _load_local_amenities()  # 10 objects
```

### Step 2: Enrich with Semantic Content
```python
{
  "page_content": "Peet's Coffee (cafe). Located in Terminal 2. 
                   Peet's Coffee is a cafe located at SFO airport. 
                   Famous for dark roasts."
  # This combines name + type + terminal + description
  # Makes it "rich" for semantic search
}
```

### Step 3: Create Embeddings
```python
# Each description → 1024-dimensional vector via Ollama
query: "Find coffee" → [0.12, -0.45, 0.89, ..., 0.34]  # 1024 dims

# Same for all 10 amenities:
LOCAL_DOC_EMBEDDINGS = [
  [0.23, -0.34, 0.12, ..., 0.45],  # Peet's Coffee embedding
  [0.11, 0.22, -0.33, ..., 0.88],  # United Club embedding
  ...
]
```

### Step 4: Build FAISS Index
```
FAISS Index (faiss_index_SFO):
┌─────────────────────────────────────┐
│ 1024-dimensional vectors            │
│ 10 amenity embeddings               │
│ Fast similarity search (cosine)     │
│ Pre-built from seed_database.py     │
└─────────────────────────────────────┘
```

### Step 5: Semantic Search
```
Query: "I want to relax with yoga"
  ↓
Embed: [query vector]
  ↓
FAISS: Find nearest neighbors
  ↓
Results:
- Yoga Room (similarity: 0.94)
- Freshen Up (similarity: 0.67)
- Coffee (similarity: 0.45)
  ↓
Return top-3 with metadata
```

---

## 💡 Why It's "Semantic" (Not Just Keyword Search)

### Keyword Search (Bad)
```python
if "yoga" in doc.desc:
    return doc
```
- ❌ "I want to relax" won't find Yoga Room
- ❌ "Where can I meditate" won't match
- ❌ Rigid, no understanding

### Semantic Search (Good)
```python
query_embedding = embed("I want to relax")
doc_embedding = embed("Public Yoga Room for relaxation")
similarity = cosine(query_embedding, doc_embedding)
# ✅ 0.94 similarity (understands intent)
# ✅ "I want to chill" also returns yoga
# ✅ Flexible, understands meaning
```

---

## 💰 Web3 Payment Integration: Coinbase Commerce

### Current Mock Payment
```python
@api.post("/pay")
def process_payment(request: PaymentRequest):
    # Just returns success message
    return {"status": "success", "transaction_id": "tx_mock_123"}
```

### What We Need
- Real Coinbase Commerce integration
- Crypto payment support (USDC recommended)
- Lounge booking workflow

---

## 🔧 Coinbase Commerce Integration (Step-by-Step)

### Step 1: Setup Coinbase Account

1. Go to: https://commerce.coinbase.com
2. Sign up / login
3. Create API key in Settings
4. Copy API_KEY

### Step 2: Install Coinbase SDK

```bash
pip install coinbase-commerce
```

### Step 3: Update `requirements.txt`

```bash
coinbase-commerce>=3.0.0
```

### Step 4: Add to `.env`

```bash
COINBASE_API_KEY=your_api_key_here
COINBASE_WEBHOOK_SECRET=your_webhook_secret  # Optional for testing
```

### Step 5: Implement Real Payment Endpoint

```python
from coinbase_commerce.client import Client

# In api.py
COINBASE_API_KEY = os.getenv("COINBASE_API_KEY")
coinbase_client = Client(api_key=COINBASE_API_KEY)

@api.post("/pay")
def process_payment(request: PaymentRequest):
    """
    Real Coinbase Commerce payment for lounge bookings
    """
    try:
        charge = coinbase_client.charge.create(
            name=f"Lounge Access: {request.description}",
            description=f"LayoverOS - {request.description}",
            local_price={
                "amount": str(request.amount),
                "currency": request.currency or "USDC"
            },
            pricing_type="fixed_price",
            # Optional: Add checkout experience
            metadata={
                "user_id": request.user_id or "guest",
                "lounge": request.description,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        return {
            "status": "pending",
            "transaction_id": charge.id,
            "payment_url": charge.hosted_url,
            "pricing": charge.pricing,
            "description": charge.description
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

---

## 🎯 Lounge Booking Workflow

### User Flow
```
1. User: "Book the United Club"
   ↓
2. Agent: Detects "book" keyword → routes to bursar_node
   ↓
3. Bursar: Returns {"next_step": "payment", details: {...}}
   ↓
4. Frontend: Shows booking modal with:
   - Lounge name
   - Price (e.g., $50 USDC)
   - "Pay with Crypto" button
   ↓
5. Click button → POST /pay
   ↓
6. Backend: Creates Coinbase Commerce charge
   ↓
7. Response: Returns hosted_url (Coinbase payment page)
   ↓
8. Frontend: Redirects user to Coinbase payment
   ↓
9. User: Completes payment with metamask/wallet
   ↓
10. Webhook: Receives confirmation
   ↓
11. Backend: Stores booking in database
   ↓
12. Frontend: Shows confirmation (booking confirmed)
```

---

## 📝 Enhanced Payment Model

```python
from pydantic import BaseModel
from enum import Enum

class CryptoNetwork(str, Enum):
    ETHEREUM = "ethereum"
    POLYGON = "polygon-ethereum"
    SOL = "solana"
    BASE = "base"

class PaymentRequest(BaseModel):
    # Booking Details
    lounge_name: str  # e.g., "United Club"
    lounge_id: str    # e.g., "united_club_sfo"
    
    # Payment Details
    amount: float     # e.g., 50.00
    currency: str = "USDC"  # Recommended for Web3
    network: CryptoNetwork = CryptoNetwork.ETHEREUM
    
    # User Details
    user_id: Optional[str] = None  # For tracking
    email: Optional[str] = None    # For Coinbase receipt
    
    # Metadata
    terminal: str = "Terminal 3"  # Location
    access_duration: str = "24h"  # Pass duration
```

---

## 🧩 Updated Bursar Node (For Payments)

```python
def bursar_node(state: AgentState):
    """
    Process payment requests for lounge access
    """
    raw_msg = state['messages'][-1]
    query = raw_msg.lower()
    
    # Detect lounge from query
    lounges = {
        "united club": {
            "name": "United Club",
            "id": "united_club_sfo",
            "terminal": "Terminal 3",
            "price": 50.00,
            "desc": "Full Bar, Buffet, Showers, WiFi"
        },
        "centurion lounge": {
            "name": "Centurion Lounge",
            "id": "centurion_lounge_sfo",
            "terminal": "Terminal 3",
            "price": 75.00,
            "desc": "Premium lounge, Caviar bar, Showers"
        }
    }
    
    matched_lounge = None
    for lounge_name, details in lounges.items():
        if lounge_name in query:
            matched_lounge = details
            break
    
    if matched_lounge:
        return {
            "messages": [
                f"[PAYMENT_REQUIRED] Ready to book {matched_lounge['name']} "
                f"for {matched_lounge['price']} USDC"
            ],
            "pending_booking": matched_lounge
        }
    else:
        return {
            "messages": [
                "Which lounge would you like to book? "
                "Options: United Club ($50), Centurion Lounge ($75)"
            ]
        }
```

---

## 🌐 Frontend Payment Modal Enhancement

```typescript
// frontend/app/components/PaymentModal.tsx
import { useState } from 'react';

interface PaymentModalProps {
  isOpen: boolean;
  lounge: {
    name: string;
    price: number;
    currency: string;
    description: string;
  };
  onClose: () => void;
}

export function PaymentModal({ isOpen, lounge, onClose }: PaymentModalProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [paymentUrl, setPaymentUrl] = useState<string | null>(null);

  const handlePayment = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/pay`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            lounge_name: lounge.name,
            lounge_id: lounge.name.toLowerCase().replace(' ', '_'),
            amount: lounge.price,
            currency: lounge.currency || 'USDC',
            network: 'ethereum'
          })
        }
      );

      const data = await response.json();
      
      if (data.payment_url) {
        // Redirect to Coinbase checkout
        window.location.href = data.payment_url;
      }
    } catch (error) {
      console.error('Payment error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full">
        <h2 className="text-2xl font-bold mb-4">Confirm Booking</h2>
        
        <div className="mb-6 p-4 bg-gray-50 rounded">
          <p className="text-sm text-gray-600">Lounge</p>
          <p className="text-xl font-semibold mb-3">{lounge.name}</p>
          
          <p className="text-sm text-gray-600">Price</p>
          <p className="text-2xl font-bold text-blue-600 mb-3">
            {lounge.price} {lounge.currency}
          </p>
          
          <p className="text-sm text-gray-600">Payment Method</p>
          <p className="text-lg font-semibold mb-3">Cryptocurrency (Coinbase)</p>
          
          <p className="text-xs text-gray-500">{lounge.description}</p>
        </div>

        <button
          onClick={handlePayment}
          disabled={isLoading}
          className="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold mb-3 
                     hover:bg-blue-700 disabled:opacity-50"
        >
          {isLoading ? 'Processing...' : 'Pay with Coinbase'}
        </button>

        <button
          onClick={onClose}
          className="w-full text-gray-600 py-2 hover:text-gray-800"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
```

---

## 🔐 Webhook Handling (For Confirmation)

```python
# In api.py - For Coinbase webhook confirmations
from fastapi import Request
import hmac
import hashlib

COINBASE_WEBHOOK_SECRET = os.getenv("COINBASE_WEBHOOK_SECRET", "")

@api.post("/webhook/coinbase")
async def handle_coinbase_webhook(request: Request):
    """
    Receive payment confirmations from Coinbase
    """
    body = await request.body()
    signature = request.headers.get("X-CC-Webhook-Signature", "")
    
    # Verify signature
    expected = hmac.new(
        COINBASE_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    if signature != expected:
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    payload = await request.json()
    event_type = payload.get("type")
    
    if event_type == "charge:confirmed":
        # Payment successful
        charge_id = payload["data"]["id"]
        amount = payload["data"]["pricing"]["local"]["amount"]
        
        print(f"✅ Payment confirmed: {charge_id} for {amount} USDC")
        
        # TODO: Store booking in database
        # TODO: Emit success event to frontend
        
        return {"status": "success"}
    
    elif event_type == "charge:failed":
        charge_id = payload["data"]["id"]
        print(f"❌ Payment failed: {charge_id}")
        return {"status": "failed"}
    
    return {"status": "received"}
```

---

## 📊 Lounge Pricing Data

Add to `sfo_amenities.json` or separate `lounges.json`:

```json
{
  "lounges": [
    {
      "id": "united_club_sfo",
      "name": "United Club",
      "terminal": "Terminal 3",
      "price_usd": 50,
      "price_crypto": "0.025",  # ~$50 in USDC/ETH
      "amenities": ["Open Bar", "Buffet", "Showers", "WiFi"],
      "hours": "5am-11pm",
      "access_duration": "24 hours",
      "desc": "Premium lounge with full bar and buffet"
    },
    {
      "id": "centurion_lounge_sfo",
      "name": "Centurion Lounge",
      "terminal": "Terminal 3",
      "price_usd": 75,
      "price_crypto": "0.0375",  # ~$75 in USDC
      "amenities": ["Caviar Bar", "Premium Spirits", "Showers", "WiFi"],
      "hours": "6am-10pm",
      "access_duration": "24 hours",
      "desc": "Ultra-premium lounge for Amex Platinum"
    }
  ]
}
```

---

## 🎯 Demo Script: Book a Lounge

```
User: "I want to book the United Club"
  ↓
Agent (bursar): "Ready to book United Club for 50 USDC. 
                  Click 'Pay with Coinbase' to proceed."
  ↓
Frontend: Shows PaymentModal with:
  - Lounge: United Club
  - Price: 50 USDC
  - "Pay with Coinbase" button
  ↓
User: Clicks "Pay with Coinbase"
  ↓
Backend: POST /pay creates Coinbase charge
  ↓
Response: Redirects to Coinbase payment page
  ↓
User: Connects wallet (MetaMask, etc.)
      Approves transaction
  ↓
Coinbase: Processes payment
  ↓
Webhook: Confirms to LayoverOS backend
  ↓
Backend: Stores booking
  ↓
Frontend: Shows "Booking Confirmed! 
           QR Code: [scan at T3]"
```

---

## 🚀 Setup Instructions

### 1. Get Coinbase API Key

```bash
1. Go to https://commerce.coinbase.com
2. Sign up
3. Settings → API Keys → Create key
4. Copy API key
```

### 2. Update `.env`

```bash
COINBASE_API_KEY=your_api_key_here
COINBASE_WEBHOOK_SECRET=your_webhook_secret
```

### 3. Install SDK

```bash
pip install coinbase-commerce
pip install -r requirements.txt
```

### 4. Restart Backend

```bash
cd /Users/aryaaa/Desktop/Mongo\ DB\ Hackathon\ /LayoverOS
source .venv/bin/activate
python api.py
```

### 5. Test Payment Flow

```bash
curl -X POST http://localhost:8000/pay \
  -H "Content-Type: application/json" \
  -d '{
    "lounge_name": "United Club",
    "amount": 50,
    "currency": "USDC"
  }'
```

Response:
```json
{
  "status": "pending",
  "transaction_id": "abcd1234",
  "payment_url": "https://commerce.coinbase.com/pay/abcd1234",
  "pricing": {...}
}
```

---

## 💡 Why This is Web3

✅ Cryptocurrency payments (USDC, ETH, etc.)
✅ No intermediaries (direct wallet → lounge)
✅ Transparent smart contract (Coinbase Commerce)
✅ Self-custodial (user controls private keys)
✅ Multi-chain support (Ethereum, Polygon, etc.)
✅ Instant settlement (no bank delays)

---

**Ready to integrate? 🚀**
