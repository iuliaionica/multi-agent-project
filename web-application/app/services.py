"""Services for reading car data from CSV."""

import csv
import logging
from datetime import datetime
from pathlib import Path

from .models import Car, ContactForm

logger = logging.getLogger(__name__)


class CarService:
    """Service for managing car data."""

    def __init__(self, csv_path: str | Path):
        self.csv_path = Path(csv_path)
        self._cars: list[Car] = []
        self._load_cars()

    def reload(self) -> int:
        """Reload cars from CSV. Returns number of cars loaded."""
        self._cars = []
        self._load_cars()
        return len(self._cars)

    def _load_cars(self) -> None:
        """Load cars from CSV file with error handling."""
        if not self.csv_path.exists():
            logger.warning(f"CSV file not found: {self.csv_path}")
            return

        with open(self.csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=2):
                try:
                    car = Car(
                        id=int(row["id"]),
                        brand=row["brand"],
                        model=row["model"],
                        year=int(row["year"]),
                        price=int(row["price"]),
                        mileage=int(row["mileage"]),
                        fuel_type=row["fuel_type"],
                        transmission=row["transmission"],
                        engine_size=float(row["engine_size"]),
                        color=row["color"],
                        description=row["description"],
                        image=row["image"],
                    )
                    self._cars.append(car)
                except (KeyError, ValueError) as e:
                    logger.error(f"Error parsing row {row_num} in {self.csv_path}: {e}")
                    continue

    def get_all(self) -> list[Car]:
        """Get all cars."""
        return self._cars

    def get_by_id(self, car_id: int) -> Car | None:
        """Get car by ID."""
        for car in self._cars:
            if car.id == car_id:
                return car
        return None

    def filter_cars(
        self,
        brand: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        fuel_type: str | None = None,
        year: int | None = None,
    ) -> list[Car]:
        """Filter cars by criteria."""
        result = self._cars

        if brand:
            result = [c for c in result if c.brand.lower() == brand.lower()]
        if min_price is not None:
            result = [c for c in result if c.price >= min_price]
        if max_price is not None:
            result = [c for c in result if c.price <= max_price]
        if fuel_type:
            result = [c for c in result if c.fuel_type.lower() == fuel_type.lower()]
        if year:
            result = [c for c in result if c.year == year]

        return result

    def get_brands(self) -> list[str]:
        """Get unique brands."""
        return sorted(set(c.brand for c in self._cars))

    def get_fuel_types(self) -> list[str]:
        """Get unique fuel types."""
        return sorted(set(c.fuel_type for c in self._cars))

    def get_years(self) -> list[int]:
        """Get unique years."""
        return sorted(set(c.year for c in self._cars), reverse=True)


class ContactService:
    """Service for managing contact form submissions."""

    CSV_HEADERS = ["id", "timestamp", "name", "email", "phone", "car_id", "message"]

    def __init__(self, csv_path: str | Path):
        self.csv_path = Path(csv_path)
        self._ensure_csv_exists()

    def _ensure_csv_exists(self) -> None:
        """Create CSV file with headers if it doesn't exist."""
        if not self.csv_path.exists():
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.CSV_HEADERS)

    def _get_next_id(self) -> int:
        """Get next available ID."""
        max_id = 0
        if self.csv_path.exists():
            with open(self.csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        row_id = int(row.get("id", 0))
                        max_id = max(max_id, row_id)
                    except ValueError:
                        continue
        return max_id + 1

    def save(self, contact: ContactForm) -> int:
        """Save contact form to CSV. Returns the ID of the saved record."""
        contact_id = self._get_next_id()
        timestamp = datetime.now().isoformat()

        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                contact_id,
                timestamp,
                contact.name,
                contact.email,
                contact.phone,
                contact.car_id or "",
                contact.message,
            ])

        logger.info(f"Contact saved: id={contact_id}, email={contact.email}")
        return contact_id

    def get_all(self) -> list[dict]:
        """Get all contact submissions."""
        contacts = []
        if not self.csv_path.exists():
            return contacts

        with open(self.csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                contacts.append(row)

        return contacts
