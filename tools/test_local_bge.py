#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lattice_core.rag import FastEmbedEmbedding


provider = FastEmbedEmbedding("/mnt/d/lattice-data/models/fastembed")
vector = provider.embed(["飞行安全知识库测试"])[0]
print(provider.name, len(vector), round(sum(value * value for value in vector), 6))
