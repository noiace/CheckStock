from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey, CheckConstraint, UniqueConstraint

from .base import Base

class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False, index=True)
    
    physical_quantity: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )

    reserved_quantity: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )

    __table_args__ = (
        CheckConstraint(
            "physical_quantity >= 0",
            name="check_physical_quantity",
        ),
        CheckConstraint(
            "reserved_quantity >= 0",
            name="check_reserved_quantity",
        ),
        CheckConstraint(
            "reserved_quantity <= physical_quantity",
            name="check_reserved_not_exceed_physical",
        ),
        UniqueConstraint(
            "product_id",
            "warehouse_id",
            name="uq_product_warehouse",
        ),
    )