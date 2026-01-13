"""Data models for car dealership."""

import re
from pydantic import BaseModel, field_validator


class Car(BaseModel):
    """Car model."""
    id: int
    brand: str
    model: str
    year: int
    price: int
    mileage: int
    fuel_type: str
    transmission: str
    engine_size: float
    color: str
    description: str
    image: str

    @property
    def title(self) -> str:
        """Full car title."""
        return f"{self.brand} {self.model} ({self.year})"

    @property
    def price_formatted(self) -> str:
        """Formatted price with currency."""
        return f"€{self.price:,}"

    @property
    def mileage_formatted(self) -> str:
        """Formatted mileage."""
        return f"{self.mileage:,} km"


class ContactForm(BaseModel):
    """Contact form model with validation."""
    name: str
    email: str
    phone: str
    car_id: int | None = None
    message: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        if len(v.strip()) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v.strip()

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower().strip()

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v: str) -> str:
        # Remove spaces, dashes, parentheses for validation
        cleaned = re.sub(r"[\s\-\(\)]+", "", v)
        # Must be digits, optionally starting with +
        pattern = r"^\+?[0-9]{8,15}$"
        if not re.match(pattern, cleaned):
            raise ValueError("Invalid phone format (8-15 digits, optional + prefix)")
        return v.strip()

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        if len(v.strip()) < 10:
            raise ValueError("Message must be at least 10 characters")
        return v.strip()
