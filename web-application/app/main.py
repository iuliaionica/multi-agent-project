"""FastAPI application for car dealership website."""

import secrets
from pathlib import Path

from fastapi import FastAPI, Form, Query, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .models import ContactForm
from .services import CarService, ContactService

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR.parent / "data"

# Initialize app
app = FastAPI(title="AutoElite - Car Dealership")

# Mount static files
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Templates
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Services
car_service = CarService(DATA_DIR / "cars.csv")
contact_service = ContactService(DATA_DIR / "contacts.csv")

# CSRF tokens storage (in production, use Redis or database)
csrf_tokens: set[str] = set()


def generate_csrf_token() -> str:
    """Generate a new CSRF token."""
    token = secrets.token_urlsafe(32)
    csrf_tokens.add(token)
    # Keep only last 1000 tokens to prevent memory issues
    if len(csrf_tokens) > 1000:
        csrf_tokens.pop()
    return token


def validate_csrf_token(token: str | None) -> bool:
    """Validate and consume a CSRF token."""
    if token and token in csrf_tokens:
        csrf_tokens.discard(token)
        return True
    return False


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with custom pages."""
    if exc.status_code == 404:
        return templates.TemplateResponse(
            "404.html",
            {"request": request},
            status_code=404,
        )
    # For other errors, return default response
    return HTMLResponse(
        content=f"<h1>Error {exc.status_code}</h1><p>{exc.detail}</p>",
        status_code=exc.status_code,
    )


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with featured cars."""
    featured_cars = car_service.get_all()[:6]
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "featured_cars": featured_cars},
    )


def parse_positive_int(value: str | None) -> int | None:
    """Parse string to positive int, return None if invalid."""
    if not value or not value.strip():
        return None
    try:
        num = int(value)
        return num if num > 0 else None
    except ValueError:
        return None


@app.get("/catalog", response_class=HTMLResponse)
async def catalog(
    request: Request,
    brand: str | None = Query(None),
    fuel_type: str | None = Query(None),
    year: str | None = Query(None),
    min_price: str | None = Query(None),
    max_price: str | None = Query(None),
):
    """Catalog page with filters."""
    # Parse numeric filters safely
    year_int = parse_positive_int(year)
    min_price_int = parse_positive_int(min_price)
    max_price_int = parse_positive_int(max_price)

    # Filter empty strings to None for brand and fuel_type
    brand = brand if brand and brand.strip() else None
    fuel_type = fuel_type if fuel_type and fuel_type.strip() else None

    cars = car_service.filter_cars(
        brand=brand,
        fuel_type=fuel_type,
        year=year_int,
        min_price=min_price_int,
        max_price=max_price_int,
    )

    return templates.TemplateResponse(
        "catalog.html",
        {
            "request": request,
            "cars": cars,
            "brands": car_service.get_brands(),
            "fuel_types": car_service.get_fuel_types(),
            "years": car_service.get_years(),
            "brand": brand,
            "fuel_type": fuel_type,
            "year": year_int,
            "min_price": min_price_int,
            "max_price": max_price_int,
        },
    )


@app.get("/car/{car_id}", response_class=HTMLResponse)
async def car_detail(request: Request, car_id: int):
    """Car detail page."""
    car = car_service.get_by_id(car_id)
    if not car:
        return RedirectResponse(url="/catalog")

    return templates.TemplateResponse(
        "car_detail.html",
        {"request": request, "car": car},
    )


@app.get("/contact", response_class=HTMLResponse)
async def contact_page(
    request: Request,
    car_id: str | None = Query(None),
    success: bool = Query(False),
):
    """Contact page."""
    car_id_int = parse_positive_int(car_id)
    car = car_service.get_by_id(car_id_int) if car_id_int else None
    csrf_token = generate_csrf_token()

    return templates.TemplateResponse(
        "contact.html",
        {
            "request": request,
            "car": car,
            "success": success,
            "csrf_token": csrf_token,
            "errors": None,
            "form_data": None,
        },
    )


@app.post("/contact", response_class=HTMLResponse)
async def contact_submit(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    message: str = Form(""),
    car_id: str | None = Form(None),
    csrf_token: str = Form(""),
):
    """Handle contact form submission."""
    car_id_int = parse_positive_int(car_id)
    car = car_service.get_by_id(car_id_int) if car_id_int else None
    errors: list[str] = []

    # Validate CSRF token
    if not validate_csrf_token(csrf_token):
        errors.append("Invalid security token. Please try again.")

    # Validate form using Pydantic model
    if not errors:
        try:
            contact = ContactForm(
                name=name,
                email=email,
                phone=phone,
                car_id=car_id_int,
                message=message,
            )
            # Save to CSV
            contact_service.save(contact)

            # Redirect with success flag
            redirect_url = "/contact?success=true"
            if car_id_int:
                redirect_url += f"&car_id={car_id_int}"
            return RedirectResponse(url=redirect_url, status_code=303)

        except ValidationError as e:
            for error in e.errors():
                field = error["loc"][0]
                msg = error["msg"]
                errors.append(f"{field.capitalize()}: {msg}")

    # Return form with errors
    new_csrf_token = generate_csrf_token()
    return templates.TemplateResponse(
        "contact.html",
        {
            "request": request,
            "car": car,
            "success": False,
            "csrf_token": new_csrf_token,
            "errors": errors,
            "form_data": {
                "name": name,
                "email": email,
                "phone": phone,
                "message": message,
            },
        },
    )
