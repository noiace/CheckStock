import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

class TransferStatus(str, enum.Enum):
    IN_TRANSIT = "IN_TRANSIT"
    RECEIVED = "RECEIVED"

class Transfer(Base):
    __tablename__ = "transfers"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), nullable=False, index=True
    )
    
    from_warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id"), nullable=False, index=True
    )
    
    to_warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id"), nullable=False, index=True
    )
    
    quantity: Mapped[int] = mapped_column(nullable=False)
    
    status: Mapped[TransferStatus] = mapped_column(
        SAEnum(
            TransferStatus,
            name="transfer_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=TransferStatus.IN_TRANSIT,
        server_default=TransferStatus.IN_TRANSIT.value,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_transfers_positive_quantity"),
        CheckConstraint(
            "from_warehouse_id <> to_warehouse_id",
            name="ck_transfers_distinct_warehouses",
        ),
    )
