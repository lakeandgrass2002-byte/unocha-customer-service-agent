# UNOCHA Drink-Shop Customer Service Agent

A student-built AI customer-service demo for a drink-shop theme based on UNOCHA (烏弄). This is an educational prototype and **is not an official UNOCHA system**.

## Features

- Gradio chat interface with conversation history, a welcome message, and sample questions
- SQLite database rebuilt from `shop_info.csv` and `menu.csv` at startup
- Four tools:
  - `get_shop_info`: retrieve shop information
  - `search_drinks`: search menu items, with intent options for tea and mixed drinks
  - `calculate_order_total`: calculate the price of an order
  - `transfer_to_human`: handle requests that need human assistance
- Visible tool trace showing each tool name, arguments, and result
- Maximum of five model/tool steps per user question
- API key loaded from the local `.env` file rather than hard-coded in the source code
- Menu prices are reference prices; customers should verify prices and availability with the selected branch

## Requirements

- Python 3.10 or newer
- Access to the NKUST iAI API and a valid API key
- Dependencies listed in `requirements.txt`

The app is configured to use the iAI OpenAI-compatible API endpoint `https://www.iai.nkust.edu.tw/aihub/v1/` and model `Furen-large`.

## Project files

| File | Purpose |
|---|---|
| `app.py` | Gradio interface, agent loop, and tool functions |
| `shop_info.csv` | Shop information used by the agent |
| `menu.csv` | Menu items, sizes, prices, availability, and notes |
| `requirements.txt` | Python dependencies |
| `.env.example` | Example environment configuration without a real API key |
| `.gitignore` | Prevents secrets, virtual environments, and generated files from being committed |

The SQLite database (`unocha.db`) is generated from the CSV files when the app starts and should not be committed to GitHub.

## Install and run (Windows PowerShell)

Run these commands from the project folder.

1. Create a virtual environment:

   ```powershell
   py -3.12 -m venv .venv
   ```

   If Python 3.12 is not installed, use another installed Python version that meets the project requirements.

2. Activate the environment:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. Create your local `.env` file from the example:

   ```powershell
   Copy-Item .env.example .env
   ```

5. Open `.env` in your editor and set `LLM_API_URL`, `MODEL_NAME`, and `API_KEY` using the configuration provided for your iAI account. Put your real API key only in `.env` on your own computer. **Never commit `.env` or publish your API key.**

   Example structure for `.env.example` (the `API_KEY` value must remain blank or be a non-secret placeholder):

   ```dotenv
   LLM_API_URL=https://www.iai.nkust.edu.tw/aihub/v1/
   MODEL_NAME=Furen-large
   API_KEY=
   ```

6. Start the app:

   ```powershell
   python app.py
   ```

7. Open the local Gradio URL shown in the terminal.

## Database and data limitations

- `shop_info.csv` contains shop-information topics and their provenance/status.
- `menu.csv` contains menu items, sizes, reference prices, availability, and notes.
- `unocha.db` is generated locally at startup and is intentionally excluded from Git.
- This prototype is not connected to a live store menu, inventory, order system, payment gateway, or real employee-handover service.
- Menu details may be incomplete or change over time. Confirm current prices and availability with the specific branch.

## Suggested test questions

1. `名間鄉冬片仔多少錢？`
2. `我要兩杯大杯玉霞紅茶拿鐵，總共多少錢？`
3. `有哪些冬片仔調飲？`
4. `請問高雄某門市今天幾點打烊？`
5. `我想投訴飲料有異物。`
6. `幫我解釋微積分。`

## Tool-choice test

The agent was tested with 10 questions covering shop information, menu searches, order calculations, human handover, and out-of-scope questions.

- First test: **10/10 (100%)**
- Second test after the welcome-message change: **10/10 (100%)**

The welcome-message change was a user-interface improvement. The test results apply to the 10 questions in the local test script and do not guarantee perfect behavior for every possible user question.

## Sources

- Official UNOCHA menu: https://unocha.com.tw/drinks.php
- Official announcement on regional supply and price adjustments: https://unocha.com.tw/news_detail.php?id=2972
- iAI API configuration is provided by the NKUST iAI service for authorized users.
