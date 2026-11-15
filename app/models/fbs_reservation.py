import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

class FBSReservationStatus(str, enum.Enum):
    RESERVED = "RESERVED"
    CANCELLED = "CANCELLED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"

class FBSReservation(Base):
    __tablename__ = "fbs_reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), nullable=False, index=True
    )
    
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id"), nullable=False, index=True
    )
    
    quantity: Mapped[int] = mapped_column(nullable=False)
    
    status: Mapped[FBSReservationStatus] = mapped_column(
        SAEnum(
            FBSReservationStatus,
            name="fbs_reservation_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=FBSReservationStatus.RESERVED,
        server_default=FBSReservationStatus.RESERVED.value,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_fbs_reservations_positive_quantity"),
    )
