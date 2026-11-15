from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)


class ProductRead(ProductCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)
