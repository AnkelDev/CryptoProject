from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import os
import logging

from app.solana_utils import (
    get_balance_sol,
    estimate_fees_sol,
    prepare_distribution_plan,
    send_distribution_transactions,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "changeme")
RPC_URL = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")

app = FastAPI(title="Lotos Crypto Transaction")

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# --- MODELS ---
class BalanceRequest(BaseModel):
    pubkey: str

class EstimateRequest(BaseModel):
    pubkey: str
    recipients: str
    equal_shares: bool = False
    send_all: bool = False
    total_sol: float = 0.0

class DistributeRequest(EstimateRequest):
    private_key_base58: str
    admin_token: str


# --- PAGES ---
@app.get("/", response_class=HTMLResponse)
def index():
    return RedirectResponse("/distribute")

@app.get("/distribute", response_class=HTMLResponse)
def distribute_page(request: Request):
    return templates.TemplateResponse("distribute.html", {"request": request})


# --- API ENDPOINTS ---
@app.post("/api/balance")
async def api_balance(req: BalanceRequest):
    try:
        balance = get_balance_sol(req.pubkey, RPC_URL)
        return {"success": True, "balance_sol": balance}
    except Exception as e:
        logging.exception("Ошибка при получении баланса")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/estimate")
async def api_estimate(req: EstimateRequest):
    try:
        recipients = [r.strip() for r in req.recipients.splitlines() if r.strip()]
        if not recipients:
            raise Exception("Список получателей пуст")

        plan = prepare_distribution_plan(
            sender_pubkey=req.pubkey,
            recipients=recipients,
            total_sol=req.total_sol,
            equal_shares=req.equal_shares,
            send_all=req.send_all,
            rpc_url=RPC_URL,
        )
        return {"success": True, "plan": plan}
    except Exception as e:
        logging.exception("Ошибка при расчёте распределения")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/distribute")
async def api_distribute(req: DistributeRequest):
    if req.admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Неверный токен администратора")

    try:
        recipients = [r.strip() for r in req.recipients.splitlines() if r.strip()]
        if not recipients:
            raise Exception("Список получателей пуст")

        result = send_distribution_transactions(
            sender_pubkey=req.pubkey,
            sender_private_key_base58=req.private_key_base58,
            recipients=recipients,
            total_sol=req.total_sol,
            equal_shares=req.equal_shares,
            send_all=req.send_all,
            rpc_url=RPC_URL,
        )
        return {"success": True, "result": result}
    except Exception as e:
        logging.exception("Ошибка при распределении")
        raise HTTPException(status_code=400, detail=str(e))


# --- ERRORS ---
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail, "path": request.url.path},
    )
