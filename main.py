import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId

from database import db, create_document, get_documents

app = FastAPI(title="Cricket & Matka Betting API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic response helpers
class IDModel(BaseModel):
    id: str

class CreateUser(BaseModel):
    username: str
    email: Optional[str] = None

class CreateMarket(BaseModel):
    game_type: str
    title: str
    outcomes: List[dict]
    start_time: Optional[datetime] = None

class PlaceBet(BaseModel):
    user_id: str
    market_id: str
    outcome_key: str
    stake: float

@app.get("/")
def read_root():
    return {"message": "Betting backend is running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response

# --- Basic helpers ---

def oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

# --- Users ---
@app.post("/api/users", response_model=IDModel)
def create_user(payload: CreateUser):
    doc = {
        "username": payload.username,
        "email": payload.email,
        "created_at": datetime.now(timezone.utc),
        "is_active": True,
        "balance": 0.0,
    }
    new_id = create_document("user", doc)
    return {"id": new_id}

# --- Markets (Cricket, Matka, Others) ---
@app.post("/api/markets", response_model=IDModel)
def create_market(payload: CreateMarket):
    if payload.game_type not in ("cricket", "matka", "other"):
        raise HTTPException(status_code=400, detail="Invalid game_type")
    if not payload.outcomes or not isinstance(payload.outcomes, list):
        raise HTTPException(status_code=400, detail="Outcomes required")

    for o in payload.outcomes:
        if not {"key", "label", "odds"}.issubset(o.keys()):
            raise HTTPException(status_code=400, detail="Each outcome needs key, label, odds")

    market = {
        "game_type": payload.game_type,
        "title": payload.title,
        "outcomes": payload.outcomes,
        "status": "open",
        "start_time": payload.start_time,
        "created_at": datetime.now(timezone.utc),
    }
    new_id = create_document("market", market)
    return {"id": new_id}

@app.get("/api/markets")
def list_markets(game_type: Optional[str] = None):
    filt = {"game_type": game_type} if game_type else {}
    items = get_documents("market", filt, limit=100)
    for it in items:
        it["id"] = str(it.pop("_id"))
    return {"items": items}

# --- Betting ---
@app.post("/api/bets", response_model=IDModel)
def place_bet(payload: PlaceBet):
    # Verify market exists and is open
    market = db["market"].find_one({"_id": oid(payload.market_id)})
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    if market.get("status") != "open":
        raise HTTPException(status_code=400, detail="Market is not open")

    # Verify outcome exists
    outcome = next((o for o in market.get("outcomes", []) if o.get("key") == payload.outcome_key), None)
    if not outcome:
        raise HTTPException(status_code=400, detail="Invalid outcome")

    # Verify user exists
    user = db["user"].find_one({"_id": oid(payload.user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # For demo, skip wallet balance enforcement; in production, debit balance here
    potential = round(payload.stake * float(outcome.get("odds", 1.0)), 2)

    bet = {
        "user_id": payload.user_id,
        "market_id": payload.market_id,
        "outcome_key": payload.outcome_key,
        "stake": float(payload.stake),
        "odds": float(outcome.get("odds")),
        "potential_payout": potential,
        "status": "pending",
        "placed_at": datetime.now(timezone.utc),
    }
    new_id = create_document("bet", bet)
    return {"id": new_id}

@app.get("/api/users/{user_id}/bets")
def list_user_bets(user_id: str):
    items = get_documents("bet", {"user_id": user_id}, limit=200)
    for it in items:
        it["id"] = str(it.pop("_id"))
    return {"items": items}

# --- Settlement (basic) ---
class SettlePayload(BaseModel):
    settled_outcome_key: str

@app.post("/api/markets/{market_id}/settle")
def settle_market(market_id: str, payload: SettlePayload):
    market = db["market"].find_one({"_id": oid(market_id)})
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    if market.get("status") != "open":
        raise HTTPException(status_code=400, detail="Market must be open to settle")

    # Update market
    db["market"].update_one({"_id": market["_id"]}, {"$set": {"status": "settled", "settled_outcome_key": payload.settled_outcome_key, "settled_at": datetime.now(timezone.utc)}})

    # Update bets
    winning_key = payload.settled_outcome_key
    bets = db["bet"].find({"market_id": market_id})
    for b in bets:
        new_status = "won" if b.get("outcome_key") == winning_key else "lost"
        db["bet"].update_one({"_id": b["_id"]}, {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc)}})

    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
