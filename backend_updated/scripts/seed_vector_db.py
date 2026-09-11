"""Seed the local MVP vector store from app/data/knowledge_base."""

from app.services.rag import seed_knowledge_base


if __name__ == "__main__":
    seed_knowledge_base()