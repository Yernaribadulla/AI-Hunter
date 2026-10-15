"""Independent local vacancy analysis API; never controls the browser."""

import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from services import analysis_core as core

app = FastAPI(title="AI-Hunter analysis", version="1.0")
gate = asyncio.Lock()


class AnalysisRequest(BaseModel):
    vacancy: dict
    instruction: str = Field(default="", max_length=10000)


@app.get("/health")
def health():
    return {"status": "ok", "service": "analysis"}


@app.get("/ready")
async def ready():
    try:
        async with gate:
            core.ACTIVE_MODEL = await asyncio.to_thread(core.get_lm_model)
        return {"model": core.ACTIVE_MODEL}
    except Exception as exc:
        raise HTTPException(503, "LM Studio is unavailable") from exc


@app.post("/v1/analyze")
async def analyze(body: AnalysisRequest):
    # One local model request at a time prevents GPU overload.
    async with gate:
        if core.ACTIVE_MODEL is None:
            try:
                core.ACTIVE_MODEL = await asyncio.to_thread(core.get_lm_model)
            except Exception as exc:
                raise HTTPException(503, "LM Studio is unavailable") from exc
        result = await core.analyze_vacancy(body.vacancy, body.instruction)
        result["model"] = core.ACTIVE_MODEL
        return result
