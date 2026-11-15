import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

class StockMovementType(str, enum.Enum):
    RECEIPT = "RECEIPT"
    FBS_RESERVED = "FBS_RESERVED"
    FBS_CANCELLED = "FBS_CANCELLED"
    FBS_SHIPPED = "FBS_SHIPPED"
    FBS_DELIVERED = "FBS_DELIVERED"
    FBO_SHIPPED = "FBO_SHIPPED"
    FBO_RECEIVED = "FBO_RECEIVED"
    TRANSFER_SHIPPED = "TRANSFER_SHIPPED"
    TRANSFER_RECEIVED = "TRANSFER_RECEIVED"

class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    movement_type: Mapped[StockMovementType] = mapped_column(
        SAEnum(
            StockMovementType,
            name="stock_movement_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), nullable=False, index=True
    )
    
    quantity: Mapped[int] = mapped_column(nullable=False)

    from_warehouse_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouses.id"), index=True
    )
    
    to_warehouse_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouses.id"), index=True
    )

    fbs_reservation_id: Mapped[int | None] = mapped_column(
        ForeignKey("fbs_reservations.id")
    )
    
    fbo_shipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("fbo_shipments.id")
    )
    
    transfer_id: Mapped[int | None] = mapped_column(
        ForeignKey("transfers.id")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_stock_movements_positive_quantity"),
        CheckConstraint(
            "(CASE WHEN fbs_reservation_id IS NULL THEN 0 ELSE 1 END) + "
            "(CASE WHEN fbo_shipment_id IS NULL THEN 0 ELSE 1 END) + "
            "(CASE WHEN transfer_id IS NULL THEN 0 ELSE 1 END) <= 1",
            name="ck_stock_movements_single_operation",
        ),
    )
