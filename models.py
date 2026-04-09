from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class Task:
    title: str
    done: bool = False
    deadline: str = "No deadline"
    priority: str = "Low"
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
