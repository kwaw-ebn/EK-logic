import re
from pydantic import BaseModel, Field, field_validator

class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator('email')
    @classmethod
    def email_valid(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Enter a valid email address')
        return value

class Registration(Credentials):
    name: str = Field(min_length=1, max_length=120)
    organization: str = Field(min_length=1, max_length=120)

    @field_validator('name', 'organization')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('This field cannot be blank')
        return value.strip()

class Named(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator('name')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('This field cannot be blank')
        return value.strip()

class AnalysisInput(Named):
    dimension: str = Field(min_length=1, max_length=255)
    measure: str | None = Field(default=None, max_length=255)
    operation: str = 'sum'

class MeaningsInput(BaseModel):
    meanings: dict[str, str]

class PropertyInput(BaseModel):
    property_id: str = Field(min_length=1, max_length=512)

class SyncInput(BaseModel):
    start: str
    end: str
