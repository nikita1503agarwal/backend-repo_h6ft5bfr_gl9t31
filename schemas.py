"""
Database Schemas for WhatsApp-to-MPesa Microstore

Each Pydantic model represents a collection in MongoDB. Collection name is the lowercase of the class name.
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict

class Seller(BaseModel):
    name: str = Field(..., description="Seller full name or business name")
    email: Optional[EmailStr] = Field(None, description="Email address")
    phone: str = Field(..., description="Primary phone number (MSISDN, e.g., 2547XXXXXXXX)")
    whatsapp_number: Optional[str] = Field(None, description="WhatsApp number for notifications (MSISDN)")
    password: Optional[str] = Field(None, description="Hashed password or placeholder for simple auth")

class Store(BaseModel):
    owner_id: str = Field(..., description="Reference to Seller _id as string")
    name: str = Field(..., description="Display name")
    slug: str = Field(..., description="Unique store slug, used in links")
    description: Optional[str] = Field(None, description="Short blurb")
    whatsapp_number: Optional[str] = Field(None, description="WhatsApp number for notifications")
    mpesa_paybill: Optional[str] = Field(None, description="Business shortcode if using Paybill/Till")

class Product(BaseModel):
    store_slug: str = Field(..., description="Slug of owning store")
    name: str = Field(..., description="Product name")
    price: float = Field(..., ge=0, description="Price in KES")
    description: Optional[str] = Field(None, description="Product description")
    image_url: Optional[str] = Field(None, description="Product image URL")
    is_active: bool = Field(True)

class OrderItem(BaseModel):
    product_id: str
    name: str
    price: float
    quantity: int = Field(..., ge=1)

class CustomerInfo(BaseModel):
    name: Optional[str] = None
    phone: str = Field(..., description="Customer MSISDN 2547XXXXXXXX for STK push")

class Order(BaseModel):
    store_slug: str
    items: List[OrderItem]
    total: float
    customer: CustomerInfo
    status: str = Field("pending", description="pending, paid, failed, cancelled")
    mpesa: Dict = Field(default_factory=dict, description="MPesa transaction metadata")
