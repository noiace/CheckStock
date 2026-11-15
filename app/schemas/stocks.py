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
        # Доступно = физически на ФФ - зарезервировано под FBS.
        return self.physical_quantity - self.reserved_quantity


class StockOverview(StockRead):
    # Для экрана остатков сервис добавляет названия из Product и Warehouse.
    sku: str
    product_name: str
    warehouse_name: str
