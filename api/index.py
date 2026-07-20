from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers.precios import router as gas_router
from api.routers.stats import router as stats_router
from api.routers.stripe_checkout import router as stripe_router

app = FastAPI(title="Gasifac API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(gas_router)
app.include_router(stats_router)
app.include_router(stripe_router)


@app.get("/api/health")
async def root_health():
    return {"status": "ok", "version": "1.0.0"}
