from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from models.product import Product
from schemas.products import ProductCreate, ProductRead

products_router = APIRouter(prefix="/products", tags=["products"])


@products_router.get("", response_model=list[ProductRead])
async def list_products(session: AsyncSession = Depends(get_db)):
    products = await session.scalars(select(Product).order_by(Product.sku))
    return list(products.all())


@products_router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(data: ProductCreate, session: AsyncSession = Depends(get_db)):
    sku = data.sku.strip()
    name = data.name.strip()
    if not sku or not name:
        raise HTTPException(status_code=422, detail="Артикул и название не могут быть пустыми")

    try:
        async with session.begin():
            product = Product(sku=sku, name=name)
            session.add(product)
            await session.flush()
            result = ProductRead.model_validate(product)
        return result
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Товар с таким артикулом уже существует") from exc
