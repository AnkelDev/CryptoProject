from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.pubkey import Pubkey as PublicKey
from solders.system_program import TransferParams, transfer
from solana.transaction import Transaction
import base58
import math
import requests
import logging

# === Константы ===
LAMPORTS_PER_SOL = 1_000_000_000

# === Логирование ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# === Клиент ===
def _client(rpc_url: str) -> Client:
    return Client(rpc_url)


# === Получение баланса ===
def get_balance_sol(pubkey: str, rpc_url: str) -> float:
    client = _client(rpc_url)
    try:
        # поддержка обычных base58 адресов (например 44-символьных)
        pubkey_obj = PublicKey.from_string(pubkey)
    except Exception as e:
        raise Exception(f"Некорректный адрес кошелька: {e}")

    try:
        res = client.get_balance(pubkey_obj)

        if hasattr(res, "value"):
            lamports = res.value
        elif isinstance(res, dict) and "result" in res:
            lamports = res["result"]["value"]
        else:
            raise Exception(f"Неизвестный формат ответа: {res}")

        balance = lamports / LAMPORTS_PER_SOL
        logging.info(f"Баланс {pubkey[:6]}...: {balance:.6f} SOL")
        return balance

    except Exception as e:
        raise Exception(f"Ошибка получения баланса: {e}")


# === Оценка комиссии ===
def estimate_fees_sol(n_transfers: int, rpc_url: str) -> float:
    client = _client(rpc_url)
    try:
        rb = client.get_latest_blockhash()
        if isinstance(rb, dict):
            lamports_per_sig = rb["result"]["value"]["feeCalculator"]["lamportsPerSignature"]
        else:
            lamports_per_sig = 5000
    except Exception:
        lamports_per_sig = 5000
    total_lamports = lamports_per_sig * max(n_transfers, 1)
    return total_lamports / LAMPORTS_PER_SOL


# === Получение цены SOL ===
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


# === Формирование плана распределения ===
def prepare_distribution_plan(
    sender_pubkey: str,
    recipients: list,
    total_sol: float,
    equal_shares: bool,
    send_all: bool,
    rpc_url: str,
):
    """
    Формирует план распределения средств между получателями.
    """
    n = len(recipients)
    if n == 0:
        raise Exception("Не указаны получатели")

    balance = get_balance_sol(sender_pubkey, rpc_url)
    fee_est = estimate_fees_sol(n, rpc_url)

    if balance <= 0:
        raise Exception("Баланс отправителя нулевой")

    # === Расчёт сумм перевода ===
    if send_all:
        available = max(0.0, balance - fee_est - 0.0001)
        if available <= 0:
            raise Exception("Недостаточно средств для покрытия комиссий")
        amounts = [available / n for _ in recipients]
    elif equal_shares:
        if total_sol <= 0:
            raise Exception("Введите сумму для распределения")
        per = total_sol / n
        amounts = [per for _ in recipients]
    else:
        per = total_sol / n if total_sol else 0
        amounts = [per for _ in recipients]

    required_distribution = sum(amounts)
    required_balance = required_distribution + fee_est
    usd_per_sol = _fetch_sol_usd_price()

    # === Получение балансов получателей ===
    recipients_balances = []
    for r in recipients:
        try:
            bal = get_balance_sol(r, rpc_url)
        except Exception:
            bal = None
        recipients_balances.append({"address": r, "balance_sol": bal})

    logging.info(f"План готов: {n} получателей, {required_distribution:.6f} SOL для перевода.")

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


# === Отправка транзакций ===
def send_distribution_transactions(
    sender_pubkey: str,
    sender_private_key_base58: str,
    recipients: list,
    total_sol: float,
    equal_shares: bool,
    send_all: bool,
    rpc_url: str,
):
    """
    Отправляет переводы на список кошельков.
    Поддерживает 64-байтовый и 32-байтовый base58 ключ.
    """
    client = _client(rpc_url)
    try:
        secret_bytes = base58.b58decode(sender_private_key_base58)

        # ✅ Универсальная обработка форматов приватных ключей
        if len(secret_bytes) == 64:
            kp = Keypair.from_bytes(secret_bytes)
        elif len(secret_bytes) == 32:
            kp = Keypair.from_seed(secret_bytes)
        else:
            raise Exception(f"Неверная длина ключа ({len(secret_bytes)} байт): ожидалось 32 или 64.")
    except Exception as e:
        raise Exception(f"Некорректный приватный ключ: {e}")

    plan = prepare_distribution_plan(
        sender_pubkey, recipients, total_sol, equal_shares, send_all, rpc_url
    )
    results = []

    for rec in plan["recipients"]:
        to_addr = rec["address"]
        amount_sol = rec["amount_sol"]
        lamports = int(math.floor(amount_sol * LAMPORTS_PER_SOL))

        if lamports <= 0:
            results.append({"to": to_addr, "status": "skipped", "reason": "amount_zero"})
            continue

        try:
            tx = Transaction()
            tx.add(
                transfer(
                    TransferParams(
                        from_pubkey=kp.pubkey(),
                        to_pubkey=PublicKey.from_string(to_addr),
                        lamports=lamports,
                    )
                )
            )

            resp = client.send_transaction(tx, kp)
            sig = None
            if isinstance(resp, dict):
                sig = resp.get("result") or resp.get("value")

            results.append({"to": to_addr, "status": "ok", "tx": sig})
            logging.info(f"✅ Перевод {amount_sol:.6f} SOL → {to_addr[:6]}... успешно отправлен.")

        except Exception as e:
            logging.error(f"❌ Ошибка перевода {to_addr[:6]}...: {e}")
            results.append({"to": to_addr, "status": "error", "error": str(e)})

    return {"plan": plan, "results": results}
