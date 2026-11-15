import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class FBOShipmentStatus(str, enum.Enum):
    IN_TRANSIT = "IN_TRANSIT"
    RECEIVED = "RECEIVED"

class FBOShipment(Base):
    __tablename__ = "fbo_shipments"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), nullable=False, index=True
    )
    
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id"), nullable=False, index=True
    )
    
    quantity: Mapped[int] = mapped_column(nullable=False)
    
    status: Mapped[FBOShipmentStatus] = mapped_column(
        SAEnum(
            FBOShipmentStatus,
            name="fbo_shipment_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=FBOShipmentStatus.IN_TRANSIT,
        server_default=FBOShipmentStatus.IN_TRANSIT.value,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_fbo_shipments_positive_quantity"),
    )
