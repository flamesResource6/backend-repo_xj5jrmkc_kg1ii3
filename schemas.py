"""
Database Schemas for Cricket, Matka and General Betting

Each Pydantic model represents a collection in MongoDB.
Collection name is the lowercase of the class name (e.g., User -> "user").
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

class User(BaseModel):
    username: str = Field(..., description="Unique username")
    email: Optional[str] = Field(None, description="Email address")
    created_at: Optional[datetime] = None
    is_active: bool = True

class WalletTransaction(BaseModel):
    user_id: str = Field(..., description="User ID")
    amount: float = Field(..., description="Positive for credit, negative for debit")
    type: Literal["deposit", "withdraw", "bet", "win", "refund"]
    note: Optional[str] = None
    balance_after: Optional[float] = None
    created_at: Optional[datetime] = None

class Outcome(BaseModel):
    key: str = Field(..., description="Outcome key identifier")
    label: str = Field(..., description="Human label e.g. Team A to Win")
    odds: float = Field(..., gt=1.0, description="Decimal odds e.g. 1.85")

class Market(BaseModel):
    game_type: Literal["cricket", "matka", "other"]
    title: str
    outcomes: List[Outcome]
    status: Literal["open", "closed", "settled"] = "open"
    start_time: Optional[datetime] = None
    settled_outcome_key: Optional[str] = None

class Bet(BaseModel):
    user_id: str
    market_id: str
    outcome_key: str
    stake: float = Field(..., gt=0)
    odds: float = Field(..., gt=1.0)
    potential_payout: float
    status: Literal["pending", "won", "lost", "refunded"] = "pending"
    placed_at: Optional[datetime] = None
