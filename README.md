# UNOCHA Drink-Shop Customer Service Agent

A student-built AI customer-service demo for a drink-shop theme based on UNOCHA (烏弄).

This project is an educational prototype and is **not an official UNOCHA system**.

**Data Source / 資料來源**

All data used in this project, including shop information, menu items, and customer service rules, are fictional data created for academic demonstration purposes. They do not represent official UNOCHA business information or policies.

本專案使用的所有資料，包括店家資訊、飲料菜單及客服處理規則，皆為課堂展示目的自行建立的模擬資料，不代表烏弄官方營運資訊或正式政策。

## Features

- Gradio chat interface with conversation history, a welcome message, and sample questions.
- SQLite database rebuilt from `shop_info.csv` and `menu.csv` at startup.
- Five tools:
  - `get_shop_info`: retrieve shop information.
  - `search_drinks`: search menu items, sizes, prices, and availability.
  - `calculate_order_total`: calculate the total price of an order.
  - `transfer_to_human`: create a simulated human-handover record.
  - `search_customer_service_knowledge`: retrieve customer-service rules from the RAG knowledge base.
- Retrieval-Augmented Generation (RAG) using Sentence Transformers and ChromaDB.
- Chinese text embeddings generated with `BAAI/bge-small-zh-v1.5`.
- Visible tool trace showing tool names, arguments, and results.
- Automatic simulated handover for selected complaint and food-safety keywords.
- API key loaded from the local `.env` file rather than hard-coded in the source code.

## Technologies

- Python
- Gradio
- NKUST iAI OpenAI-compatible API
- Tool Calling
- Retrieval-Augmented Generation (RAG)
- Sentence Transformers
- ChromaDB
- SQLite

## Requirements

- Python 3.10 or newer
- Access to the NKUST iAI API and a valid API key
- Internet access for the first-time download of the embedding model
- Dependencies listed in `requirements.txt`

The app is configured to use the iAI OpenAI-compatible API endpoint:

`https://www.iai.nkust.edu.tw/aihub/v1/`

The default model is `Furen-large`.

## Project Structure

```text
UNOCHA-Midterm/
├── app.py
├── rag.py
├── shop_info.csv
├── menu.csv
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── knowledge_base/
│   └── customer_service_rules.md
└── vector_db/                 # Generated locally; not uploaded