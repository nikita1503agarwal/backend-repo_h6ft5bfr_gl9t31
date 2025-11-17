import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Seller, Store, Product, Order, OrderItem, CustomerInfo

app = FastAPI(title="WhatsApp-to-MPesa Microstore API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------- Helpers ----------------------

def to_object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")


def ensure_unique_slug(slug: str):
    existing = db["store"].find_one({"slug": slug})
    if existing:
        raise HTTPException(status_code=400, detail="Store slug already exists")


# ---------------------- Auth/Onboarding ----------------------

class SignupRequest(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    whatsapp_number: Optional[str] = None

class SignupResponse(BaseModel):
    seller_id: str

@app.post("/api/signup", response_model=SignupResponse)
def signup(payload: SignupRequest):
    seller = Seller(
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        whatsapp_number=payload.whatsapp_number,
    )
    seller_id = create_document("seller", seller)
    return {"seller_id": seller_id}


# ---------------------- Store ----------------------

class CreateStoreRequest(BaseModel):
    owner_id: str
    name: str
    slug: str
    description: Optional[str] = None
    whatsapp_number: Optional[str] = None

class StoreResponse(BaseModel):
    store_id: str

@app.post("/api/store", response_model=StoreResponse)
def create_store(payload: CreateStoreRequest):
    ensure_unique_slug(payload.slug)
    # Validate owner exists
    owner = db["seller"].find_one({"_id": to_object_id(payload.owner_id)})
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")

    store = Store(
        owner_id=payload.owner_id,
        name=payload.name,
        slug=payload.slug.lower(),
        description=payload.description,
        whatsapp_number=payload.whatsapp_number or owner.get("whatsapp_number") or owner.get("phone"),
    )
    store_id = create_document("store", store)
    return {"store_id": store_id}


@app.get("/api/store/{slug}")
def get_store(slug: str):
    store = db["store"].find_one({"slug": slug.lower()})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    store["_id"] = str(store["_id"])
    return store


# ---------------------- Products ----------------------

class CreateProductRequest(BaseModel):
    store_slug: str
    name: str
    price: float
    description: Optional[str] = None
    image_url: Optional[str] = None

class ProductResponse(BaseModel):
    product_id: str

@app.post("/api/products", response_model=ProductResponse)
def create_product(payload: CreateProductRequest):
    # Ensure store exists
    store = db["store"].find_one({"slug": payload.store_slug.lower()})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    product = Product(
        store_slug=payload.store_slug.lower(),
        name=payload.name,
        price=payload.price,
        description=payload.description,
        image_url=payload.image_url,
    )
    product_id = create_document("product", product)
    return {"product_id": product_id}


@app.get("/api/products/{store_slug}")
def list_products(store_slug: str):
    items = get_documents("product", {"store_slug": store_slug.lower(), "is_active": True})
    for it in items:
        it["_id"] = str(it["_id"])
    return items


# ---------------------- Orders + MPesa STK (Mockable) ----------------------

class CheckoutRequest(BaseModel):
    store_slug: str
    items: List[OrderItem]
    customer: CustomerInfo

class CheckoutResponse(BaseModel):
    order_id: str
    status: str

@app.post("/api/checkout", response_model=CheckoutResponse)
def checkout(payload: CheckoutRequest):
    # Calculate total
    total = 0.0
    for item in payload.items:
        total += item.price * item.quantity

    order = Order(
        store_slug=payload.store_slug.lower(),
        items=payload.items,
        total=round(total, 2),
        customer=payload.customer,
        status="pending",
        mpesa={},
    )
    order_id = create_document("order", order)

    # Trigger MPesa STK push (sandbox/mocked)
    # In production integrate Safaricom Daraja API. Here we simulate immediate success.
    db["order"].update_one({"_id": ObjectId(order_id)}, {"$set": {"status": "paid", "mpesa": {"status": "success"}}})

    # Send WhatsApp notification (mock - store for now)
    db["notification"].insert_one({
        "type": "whatsapp",
        "store_slug": payload.store_slug.lower(),
        "order_id": order_id,
        "message": f"New order paid: {len(payload.items)} items, KES {round(total,2)} from {payload.customer.phone}",
    })

    return {"order_id": order_id, "status": "paid"}


@app.get("/")
def read_root():
    return {"message": "Microstore API running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
