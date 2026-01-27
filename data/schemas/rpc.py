from pydantic import BaseModel, Field
from typing import List, Dict, Any, Union


class Bliply(BaseModel):
    selected_provider: str
    score: float
    weights: dict[str, float]


class RPCRequest(BaseModel):
    jsonrpc: str
    method: str = Field(min_length=1)
    params: Union[List[Any], Dict[str, Any]]
    id: Union[int, str]