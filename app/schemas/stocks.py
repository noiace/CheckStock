from pydantic import BaseModel, ConfigDict, computed_field


class StockRead(BaseModel):
    id: int
    product_id: int
    warehouse_id: int
    physical_quantity: int
    reserved_quantity: int

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def available_quantity(self) -> int:
        return self.physical_quantity - self.reserved_quantity


class StockOverview(StockRead):
    # Строка Stock может отсутствовать: для экрана покажем 0, а id = null.
    id: int | None = None
    sku: str
    product_name: str
    warehouse_name: str
    warehouse_is_active: bool
