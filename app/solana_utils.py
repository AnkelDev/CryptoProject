from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.pubkey import Pubkey as PublicKey
from solders.system_program import TransferParams, transfer
from solders.transaction import Transaction
from solders.message import Message
from solders.hash import Hash
import base58
import math
import requests
import logging

LAMPORTS_PER_SOL = 1_000_000_000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def _client(rpc_url: str) -> Client:
    return Client(rpc_url)


# ============================================
# BALANCE
# ============================================

def get_balance_sol(pubkey: str, rpc_url: str) -> float:
    client = _client(rpc_url)

    try:
        pubkey_obj = PublicKey.from_string(pubkey)
    except Exception as e:
        raise Exception(f"Некорректный адрес кошелька: {e}")

    res = client.get_balance(pubkey_obj)

    if hasattr(res, "value"):
        lamports = res.value
    elif isinstance(res, dict) and "result" in res:
        lamports = res["result"]["value"]
    else:
        raise Exception(f"Неизвестный формат ответа: {res}")

    return lamports / LAMPORTS_PER_SOL


# ============================================
# FEES
# ============================================

def estimate_fees_sol(n_transfers: int, rpc_url: str) -> float:
    client = _client(rpc_url)
    try:
        rb = client.get_latest_blockhash()
        lamports_per_sig = rb.value.fee_calculator.lamports_per_signature
    except Exception:
        lamports_per_sig = 5000

    total_lamports = lamports_per_sig * max(n_transfers, 1)
    return total_lamports / LAMPORTS_PER_SOL


# ============================================
# USD PRICE
# ============================================

def _fetch_sol_usd_price():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "solana", "vs_currencies": "usd"},
            timeout=5,
        )
        data = r.json()
        return float(data["solana"]["usd"])
    except Exception:
        return 0.0


# ============================================
# DISTRIBUTION PLAN
# ============================================

def prepare_distribution_plan(
    sender_pubkey: str,
    recipients: list,
    total_sol: float,
    equal_shares: bool,
    send_all: bool,
    rpc_url: str,
):
    n = len(recipients)
    if n == 0:
        raise Exception("Не указаны получатели")

    balance = get_balance_sol(sender_pubkey, rpc_url)
    fee_est = estimate_fees_sol(n, rpc_url)

    if balance <= 0:
        raise Exception("Баланс отправителя нулевой")

    if send_all:
        available = max(0.0, balance - fee_est - 0.0001)
        if available <= 0:
            raise Exception("Недостаточно средств для покрытия комиссий")
        per = available / n
        amounts = [per] * n

    elif equal_shares:
        if total_sol <= 0:
            raise Exception("Введите сумму для распределения")
        per = total_sol / n
        amounts = [per] * n

    else:
        per = total_sol / n if total_sol else 0
        amounts = [per] * n

    required_distribution = sum(amounts)
    required_balance = required_distribution + fee_est
    usd_per_sol = _fetch_sol_usd_price()

    recipients_balances = []
    for r in recipients:
        try:
            bal = get_balance_sol(r, rpc_url)
        except Exception:
            bal = None
        recipients_balances.append({"address": r, "balance_sol": bal})

    return {
        "recipients": [{"address": r, "amount_sol": a} for r, a in zip(recipients, amounts)],
        "recipients_balances": recipients_balances,
        "balance_sol": balance,
        "required_distribution_sol": required_distribution,
        "estimated_fees_sol": fee_est,
        "required_total_sol": required_balance,
        "required_total_usd": required_balance * usd_per_sol,
        "usd_per_sol": usd_per_sol,
    }


# ============================================
# SEND TRANSACTIONS
# ============================================

def send_distribution_transactions(
    sender_pubkey: str,
    sender_private_key_base58: str,
    recipients: list,
    total_sol: float,
    equal_shares: bool,
    send_all: bool,
    rpc_url: str,
):
    client = _client(rpc_url)

    # --- Decode private key ---
    secret_bytes = base58.b58decode(sender_private_key_base58)

    if len(secret_bytes) == 64:
        kp = Keypair.from_bytes(secret_bytes)
    elif len(secret_bytes) == 32:
        kp = Keypair.from_seed(secret_bytes)
    else:
        raise Exception(f"Неверная длина ключа: {len(secret_bytes)}. Ожидалось 32 или 64.")

    sender_pubkey_obj = kp.pubkey()

    plan = prepare_distribution_plan(
        sender_pubkey, recipients, total_sol, equal_shares, send_all, rpc_url
    )

    results = []

    # --- latest blockhash (исправлено) ---
    blockhash_resp = client.get_latest_blockhash()
    raw_blockhash = blockhash_resp.value.blockhash

    blockhash = (
        raw_blockhash
        if isinstance(raw_blockhash, Hash)
        else Hash.from_string(raw_blockhash)
    )

    # --- process each transfer ---
    for rec in plan["recipients"]:
        to_addr = rec["address"]
        amount_sol = rec["amount_sol"]
        lamports = int(amount_sol * LAMPORTS_PER_SOL)

        if lamports <= 0:
            results.append({"to": to_addr, "status": "skipped", "reason": "amount_zero"})
            continue

        try:
            instruction = transfer(
                TransferParams(
                    from_pubkey=sender_pubkey_obj,
                    to_pubkey=PublicKey.from_string(to_addr),
                    lamports=lamports,
                )
            )

            message = Message.new_with_blockhash(
                instructions=[instruction],
                payer=sender_pubkey_obj,
                blockhash=blockhash
            )

            tx = Transaction.new_signed_with_payer(
                message,
                [kp],
            )

            resp = client.send_raw_transaction(tx.to_bytes())

            results.append({
                "to": to_addr,
                "status": "ok",
                "tx": resp.value if hasattr(resp, "value") else resp
            })

            logging.info(f"OK → {amount_sol:.6f} SOL → {to_addr[:6]}...")

        except Exception as e:
            logging.error(f"ERROR {to_addr[:6]}...: {e}")
            results.append({"to": to_addr, "status": "error", "error": str(e)})

    return {"plan": plan, "results": results}
