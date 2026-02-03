import json
import os
from typing import Dict

# basically maintain a usage_counters.json file where we track CUs/credits/num_requests for each provider
# and use it to implement the spillover strategy
class QuotaManager:
    def __init__(self, data_file: str = "data/usage_counters.json"):
        self.data_file = data_file
        self.usage_data: Dict[str, int] = {}
        self._load_data()

    def _load_data(self):
        """Load usage data from the JSON file."""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    self.usage_data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.usage_data = {}
        else:
            self.usage_data = {}

    def _save_data(self):
        """Save usage data to the JSON file."""
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.usage_data, f, indent=2)
        except IOError as e:
            print(f"Error saving quota data: {e}")

    def check_allowance(self, provider_name: str, limit_monthly: int) -> bool:
        """Check if the provider is within its monthly limit."""
        if limit_monthly <= 0:
            return True # Unlimited or not configured
            
        current_usage = self.usage_data.get(provider_name, 0)
        return current_usage < limit_monthly

    def increment(self, provider_name: str, count: int = 1):
        """Increment the usage counter for a provider."""
        self.usage_data[provider_name] = self.usage_data.get(provider_name, 0) + count
        self._save_data() # Simple save on every write for robustness as requested

    def get_usage(self, provider_name: str) -> int:
        return self.usage_data.get(provider_name, 0)

    def reset_usage(self, provider_name: str):
        if provider_name in self.usage_data:
            self.usage_data[provider_name] = 0
            self._save_data()
