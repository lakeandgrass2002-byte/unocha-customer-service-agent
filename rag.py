import chromadb
from sentence_transformers import SentenceTransformer

from pathlib import Path
import re

# 專案資料夾路徑
BASE_DIR = Path(__file__).resolve().parent

# RAG 知識文件位置
KNOWLEDGE_FILE = BASE_DIR / "knowledge_base" / "customer_service_rules.md"

# 向量資料庫位置
DB_DIR = BASE_DIR / "vector_db"

# ChromaDB 集合名稱
COLLECTION_NAME = "unocha_customer_service"

def load_document():
    """讀取 Markdown 知識文件。"""

    if not KNOWLEDGE_FILE.exists():
        raise FileNotFoundError(
            f"找不到知識文件：{KNOWLEDGE_FILE}"
        )

    with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as file:
        text = file.read()

    return text


def chunk_text(text, chunk_size=300, overlap=50):
    """將長文件切割成多個有重疊的小區塊。"""

    if chunk_size <= 0:
        raise ValueError("chunk_size 必須大於 0")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap 必須介於 0 和 chunk_size 之間")

    # 清理多餘空白
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end == len(text):
            break

        start = end - overlap

    return chunks

# Embedding 模型名稱
EMBEDDING_MODEL_NAME = "BAAI/bge-small-zh-v1.5"


def load_embedding_model():
    """載入中文 Embedding 模型。"""

    print("正在載入 Embedding 模型...")

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    print("Embedding 模型載入成功！")

    return model


def create_embeddings(model, chunks):
    """將文字區塊轉換成向量。"""

    embeddings = model.encode(
        chunks,
        normalize_embeddings=True,
        show_progress_bar=True
    )

    return embeddings.tolist()

def create_vector_database(chunks, embeddings):
    """將文字區塊及向量存入 ChromaDB。"""

    client = chromadb.PersistentClient(
        path=str(DB_DIR)
    )

    # 刪除舊集合，避免重複匯入
    try:
        client.delete_collection(
            name=COLLECTION_NAME
        )
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    ids = [
        f"rule_{i}"
        for i in range(len(chunks))
    ]

    metadatas = [
        {
            "source": "customer_service_rules.md",
            "chunk_id": i
        }
        for i in range(len(chunks))
    ]

    if chunks:
        collection.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas
        )

    print("ChromaDB 建立成功！")
    print("資料筆數：", collection.count())

    return client, collection

def search_knowledge(query, model, collection, top_k=3):
    """根據使用者問題搜尋最相關的知識文件。"""

    if not query.strip():
        return []

    # 使用相同 Embedding 模型轉換問題
    query_embedding = model.encode(
        [query],
        normalize_embeddings=True
    ).tolist()

    # 搜尋最相似的文件
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(top_k, collection.count()),
        include=[
            "documents",
            "metadatas",
            "distances"
        ]
    )

    retrieved_results = []

    for i in range(len(results["documents"][0])):
        retrieved_results.append({
            "content": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i]
        })

    return retrieved_results

def initialize_rag():
    """初始化 RAG：讀取文件、建立向量並建立 ChromaDB。"""

    print("===== 正在初始化 RAG 知識庫 =====")

    # 1. 讀取知識文件
    document = load_document()

    # 2. 切割文字
    chunks = chunk_text(document)

    # 3. 載入 Embedding 模型
    model = load_embedding_model()

    # 4. 將文字轉換成向量
    embeddings = create_embeddings(model, chunks)

    # 5. 建立向量資料庫
    client, collection = create_vector_database(chunks, embeddings)

    print("===== RAG 初始化完成 =====")

    return model, collection

if __name__ == "__main__":

    # 1. 讀取文件
    document = load_document()

    print("\n===== Step 1: Document Loading =====")
    print("文件長度：", len(document))

    # 2. 文件切割
    chunks = chunk_text(document)

    print("\n===== Step 2: Chunking =====")
    print("切割區塊數量：", len(chunks))

    # 3. 載入 Embedding 模型
    model = load_embedding_model()

    # 4. 文字向量化
    embeddings = create_embeddings(model, chunks)

    print("\n===== Step 3: Embedding =====")
    print("向量數量：", len(embeddings))
    print("向量維度：", len(embeddings[0]))

    # 5. 建立 ChromaDB
    client, collection = create_vector_database(
        chunks,
        embeddings
    )

    # 6. 測試語意搜尋
    print("\n===== Step 4: RAG Search =====")

    test_question = "飲料裡面有異物怎麼辦？"

    results = search_knowledge(
        test_question,
        model,
        collection,
        top_k=3
    )

    print("\n使用者問題：", test_question)

    for i, result in enumerate(results, start=1):

        print(f"\n--- Search Result {i} ---")
        print("來源：", result["metadata"]["source"])
        print("距離：", result["distance"])
        print("內容：", result["content"])

    print("\n===== RAG Test Completed =====")