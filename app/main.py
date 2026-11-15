from fastapi import FastAPI
import uvicorn

from routers import (
    warehouses_router,
    stocks_router,
    receipts_router,
    fbs_router,
    fbo_router,
    transfers_router,
    movements_router,
)

app = FastAPI(title="CheckStock")

app.include_router(warehouses_router)
app.include_router(stocks_router)
app.include_router(receipts_router)
app.include_router(fbs_router)
app.include_router(fbo_router)
app.include_router(transfers_router)
app.include_router(movements_router)

def main():
    print("Hello from test-task!")

if __name__ == "__main__":
    uvicorn.run("main:app", port=8000, reload=True)
