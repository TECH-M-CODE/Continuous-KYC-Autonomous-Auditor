import os
import yaml
from typing import Optional, Dict
from pydantic import BaseModel
from app.infrastructure.broker import broker, POLICY_RELOADED

class VelocityConfig(BaseModel):
    window_hours: int
    multiplier_threshold: int

class RiskPolicy(BaseModel):
    weights: Dict[str, float]
    sector_risk: Dict[str, float]
    bands: Dict[str, float]
    jurisdiction_factors: Dict[str, float]
    velocity: VelocityConfig
    severity_defaults: Dict[str, float]
    propagation_factor: float

class PolicyLoader:
    def __init__(self, file_name: str = "policy.yaml"):
        # Resolve absolute path from working directory or file directory
        possible_paths = [
            file_name,
            os.path.join(os.path.dirname(__file__), "../../../", file_name),
            os.path.join(os.getcwd(), file_name)
        ]
        self.file_path = possible_paths[0]
        for path in possible_paths:
            if os.path.exists(path):
                self.file_path = os.path.abspath(path)
                break
        self._policy: Optional[RiskPolicy] = None
        self._last_mtime: float = 0.0
        # Load immediately
        self.get_policy()

    def get_policy(self) -> RiskPolicy:
        if not os.path.exists(self.file_path):
            if os.path.exists("policy.yaml"):
                self.file_path = os.path.abspath("policy.yaml")
            else:
                raise FileNotFoundError(f"Policy file not found: {self.file_path}")
        
        current_mtime = os.path.getmtime(self.file_path)
        if self._policy is None or current_mtime > self._last_mtime:
            with open(self.file_path, "r") as f:
                data = yaml.safe_load(f)
            new_policy = RiskPolicy(**data)
            
            is_reload = self._policy is not None
            self._policy = new_policy
            self._last_mtime = current_mtime
            
            if is_reload:
                broker.publish(POLICY_RELOADED, {"updated_at": current_mtime})
                
        return self._policy

# Initialize default loader
policy_loader = PolicyLoader()

def get_policy() -> RiskPolicy:
    return policy_loader.get_policy()
