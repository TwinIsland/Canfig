from pydantic import BaseModel, Field, ValidationError, conlist
from typing import List, Optional

class Command(BaseModel):
    name: str
    description: str

class Server(BaseModel):
    name: str
    port: int = Field(..., gt=0, lt=65536)  # Ports must be in the range 1-65535
    description: str
    commands: List[Command]

class Runner(BaseModel):
    runner_name: str
    commands: Optional[List[Command]] = []  # Optional, defaults to an empty list if not provided
    nickname: List[str] = Field(..., min_items=1)  # At least one nickname is required
