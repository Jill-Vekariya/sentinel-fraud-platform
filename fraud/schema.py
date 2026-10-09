from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator
class Transaction(BaseModel):
    transaction_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,80}$')
    account_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,80}$')
    timestamp: datetime
    amount: float = Field(gt=0, le=10000000, allow_inf_nan=False)
    device_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,80}$')
    country: str = Field(pattern=r'^[A-Z]{2}$')
    home_country: str = Field(pattern=r'^[A-Z]{2}$')
    @field_validator('timestamp')
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None: raise ValueError('timestamp must include a timezone')
        return value.astimezone(timezone.utc)
class Feedback(BaseModel):
    is_fraud: bool
    source: str = Field(min_length=1, max_length=100)
