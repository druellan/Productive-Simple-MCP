import os
import logging

logger = logging.getLogger(__name__)

class Config:
    """Configuration for Productive MCP Server"""

    def __init__(self):
        self.api_key = os.getenv(
            "PRODUCTIVE_API_KEY", ""
        )
        self.base_url = os.getenv("PRODUCTIVE_BASE_URL", "https://api.productive.io/api/v2")
        self.timeout = int(os.getenv("PRODUCTIVE_TIMEOUT", "30"))
        org_value = os.getenv("PRODUCTIVE_ORGANIZATION")
        if org_value:
            try:
                self.organization = int(org_value)
            except ValueError:
                logger.warning(f"PRODUCTIVE_ORGANIZATION must be a valid integer, got: {org_value}")
                self.organization = None
        else:
            self.organization = None
        self.items_per_page = int(os.getenv("PRODUCTIVE_ITEMS_PER_PAGE", "50"))
        self.output_format = os.getenv("OUTPUT_FORMAT", "toon")
        self.read_only = self._parse_bool_env("READ_ONLY", default=True)

    @staticmethod
    def _parse_bool_env(env_name: str, default: bool) -> bool:
        """Parse boolean environment variables using explicit true/false values."""
        raw_value = os.getenv(env_name)
        if raw_value is None:
            return default

        normalized = raw_value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False

        raise ValueError(f"{env_name} must be either 'true' or 'false'")

    def validate(self) -> bool:
        """Validate configuration
        
        Returns:
            bool: True if configuration is valid, False otherwise
            
        Raises:
            ValueError: If configuration is invalid with detailed error message
        """
        errors = []
        
        if not self.api_key:
            errors.append("PRODUCTIVE_API_KEY is required")
            
        if not self.base_url:
            errors.append("PRODUCTIVE_BASE_URL is required")
            
        if not self.organization:
            errors.append("PRODUCTIVE_ORGANIZATION is required")
        elif not isinstance(self.organization, int) or self.organization <= 0:
            errors.append("PRODUCTIVE_ORGANIZATION must be a positive integer")
            
        if self.timeout <= 0:
            errors.append("PRODUCTIVE_TIMEOUT must be a positive integer")
            
        if self.items_per_page <= 0 or self.items_per_page > 200:
            errors.append("PRODUCTIVE_ITEMS_PER_PAGE must be between 1 and 200")

        if self.output_format not in ["toon", "json"]:
            errors.append("OUTPUT_FORMAT must be either 'toon' or 'json'")

        if not isinstance(self.read_only, bool):
            errors.append("READ_ONLY must be either 'true' or 'false'")

        if errors:
            raise ValueError("Configuration validation failed: " + "; ".join(errors))
            
        return True

    @property
    def headers(self) -> dict:
        """Return headers for Productive API requests"""
        return {
            "X-Auth-Token": self.api_key,
            "X-Organization-Id": str(self.organization),
            "Content-Type": "application/vnd.api+json",
            "User-Agent": "Productive-MCP-Server/1.0"
        }

# Global config instance
config = Config()
