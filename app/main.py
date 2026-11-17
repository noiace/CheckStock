from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uvicorn

from routers import (
    warehouses_router,
    stocks_router,
    receipts_router,
    fbs_router,
    fbo_router,
    transfers_router,
    movements_router,
    products_router,
)

app = FastAPI(title="CheckStock")

app.include_router(warehouses_router)
app.include_router(stocks_router)
app.include_router(receipts_router)
app.include_router(fbs_router)
app.include_router(fbo_router)
app.include_router(transfers_router)
app.include_router(movements_router)
app.include_router(products_router)
app.mount("/ui", StaticFiles(directory=Path(__file__).resolve().parent.parent / "web", html=True), name="ui")


@app.get("/", include_in_schema=False)
async def index():
    return RedirectResponse("/ui/")

if __name__ == "__main__":
    uvicorn.run("main:app", port=8000, reload=True)
