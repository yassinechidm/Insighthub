from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from app.db.database import engine
from app.api.router import router

app = FastAPI(title="InsightHub", version="0.1.0")
app.include_router(router)

@app.get("/")
async def root():
    return RedirectResponse(url="/docs")

@app.get("/health")
async def health():
    return {"status": "ok"}