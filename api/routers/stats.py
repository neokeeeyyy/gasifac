import os

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.services.updater import run_update

router = APIRouter(prefix="/api/gas/v1", tags=["gas-lp-admin"])


@router.post("/trigger-update")
async def trigger_update(
    x_cron_secret: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    if x_cron_secret != os.environ.get("CRON_SECRET"):
        raise HTTPException(status_code=403, detail="Invalid cron secret")
    result = await run_update(db)
    return result
