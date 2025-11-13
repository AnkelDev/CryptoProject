# Lotos Crypto Transaction

Локальный запуск (пример):

1. Создайте виртуальное окружение и установите зависимости:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Установите переменные окружения (пример):
   ```bash
   export ADMIN_TOKEN=your_secret
   export RPC_URL=https://api.mainnet-beta.solana.com
   ```

3. Запустите приложение:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

4. Откройте в браузере: http://localhost:8000

ВАЖНО: Никогда не храните приватные ключи в публичном репозитории. Этот проект демонстрационный.
