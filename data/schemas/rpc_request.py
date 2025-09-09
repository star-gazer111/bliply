from pydantic import BaseModel
from typing import List, Any

class RPCRequest(BaseModel):
    method: str
    params: List[Any] = []
