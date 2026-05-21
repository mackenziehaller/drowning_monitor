from vanna.ollama import Ollama
from vanna.chromadb import ChromaDB_VectorStore
from config import OLLAMA_MODEL, DB_PATH

class MyVanna(ChromaDB_VectorStore, Ollama):
    def __init__(self, config=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        Ollama.__init__(self, config=config)

vn = MyVanna(config={"model": OLLAMA_MODEL})
vn.connect_to_sqlite(DB_PATH)
