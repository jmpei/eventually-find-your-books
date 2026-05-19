from pydantic import BaseModel
from typing import List, Optional

class Rating(BaseModel):
    user_id: str
    book_id: str
    rating: float  # 1-5

class RecommendationResponse(BaseModel):
    user_id: str
    recommendations: List[str]  # list of book_ids
