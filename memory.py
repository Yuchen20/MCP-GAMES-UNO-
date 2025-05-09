from fastmcp import FastMCP
from datetime import datetime
import json
from typing import List, Dict, Any
import os
import asyncio
import aiofiles
import time
from qdrant_client import QdrantClient
from qdrant_client.http import models
from langchain.text_splitter import RecursiveCharacterTextSplitter
from google import genai
from google.genai import types
import numpy as np
from pathlib import Path
import plotly.express as px
import plotly.io as pio
import boto3
import uuid
from sklearn.decomposition import PCA
import pandas as pd
import shutil

from dotenv import load_dotenv

load_dotenv()

def get_app_dir():
    """Get the application directory path"""
    app_dir = Path(os.path.expanduser("~")) / ".brain_in_a_vat"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir

def get_user_uuid():
    uuid_path = get_app_dir() / "user_uuid.txt"
    if uuid_path.exists():
        return uuid_path.read_text().strip()
    user_id = str(uuid.uuid4())
    uuid_path.write_text(user_id)
    return user_id

async def log_message(message: str):
    """Async logging function"""
    log_path = get_app_dir() / "log.txt"
    async with aiofiles.open(log_path, "a") as f:
        await f.write(f"{message} at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

class MemoryProtocol:
    def __init__(self, qdrant_path: str = None):
        if qdrant_path is None:
            qdrant_path = str(get_app_dir() / "memory_db")
        self.qdrant_path = qdrant_path
        self.initialized = False
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")
        
        # Initialize S3 client
        self.s3_client = boto3.client('s3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        self.bucket_name = os.getenv('AWS_BUCKET_NAME')
    
    async def initialize(self):
        """Async initialization of the memory protocol"""
        if self.initialized:
            return
            
        await log_message("Starting memory server initialization")
        
        # Initialize Qdrant
        self.qdrant_client = QdrantClient(path=f"{self.qdrant_path}")
        await self._init_qdrant()
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50
        )
        
        # Initialize Gemini with explicit API key
        self.client = genai.Client(api_key=self.api_key)
        
        await log_message("Memory server initialization completed")
        self.initialized = True
    
    async def _init_qdrant(self):
        collection_name = "memory_vectors"
        try:
            self.qdrant_client.get_collection(collection_name)
        except Exception:
            # Create collection if it doesn't exist
            self.qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=768,
                    distance=models.Distance.COSINE
                )
            )
    
    async def _generate_embedding(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT"):
        """Generate embedding asynchronously"""
        if not self.initialized:
            await self.initialize()
            
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: self.client.models.embed_content(
                    model="gemini-embedding-exp-03-07",
                    contents=text,
                    config=types.EmbedContentConfig(task_type=task_type,
                                                    output_dimensionality=768)
                )
            )
            # Extract the embedding vector from the response
            if hasattr(response, 'embeddings'):
                return response.embeddings[0].values
            elif hasattr(response, 'values'):
                return response.values
            else:
                raise ValueError(f"Unexpected embedding response format: {response}")
        except Exception as e:
            await log_message(f"Error generating embedding: {str(e)}")
            raise
    
    async def record_memory(self, content: str, metadata: Dict[str, Any] = None) -> List[int]:
        if not self.initialized:
            await self.initialize()
            
        # Split content into chunks
        chunks = self.text_splitter.split_text(content)
        memory_ids = []
        
        # Process chunks concurrently
        async def process_chunk(chunk: str, index: int) -> int:
            try:
                # Generate embedding
                embedding = await self._generate_embedding(chunk)
                
                # Ensure embedding is a list of floats
                if not isinstance(embedding, list):
                    embedding = list(embedding)
                
                # Generate a unique ID
                memory_id = int(datetime.now().timestamp() * 1000) + index
                
                # Store in Qdrant
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self.qdrant_client.upsert(
                        collection_name="memory_vectors",
                        points=[
                            models.PointStruct(
                                id=memory_id,
                                vector=embedding,
                                payload={
                                    "content": chunk,
                                    "timestamp": datetime.now().isoformat(),
                                    "metadata": metadata or {}
                                }
                            )
                        ]
                    )
                )
                
                return "Memory recorded successfully!"
            except Exception as e:
                await log_message(f"Error processing chunk: {str(e)}")
                raise
        
        # Process all chunks concurrently
        tasks = [process_chunk(chunk, i) for i, chunk in enumerate(chunks)]
        memory_ids = await asyncio.gather(*tasks)

        # # After recording, zip the memory DB and upload to S3
        # user_id = get_user_uuid()
        # db_path = Path(self.qdrant_path)
        # zip_path = get_app_dir() / f"memory_db_{user_id}.zip"
        # shutil.make_archive(str(zip_path).replace('.zip', ''), 'zip', root_dir=db_path)
        # loop = asyncio.get_event_loop()
        # await loop.run_in_executor(
        #     None,
        #     lambda: self.s3_client.upload_file(
        #         str(zip_path),
        #         self.bucket_name,
        #         f"memory_db/{user_id}/memory_db.zip",
        #     )
        # )
        return 'memory recorded successfully!'
    
    async def retrieve_memory(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not self.initialized:
            await self.initialize()
            
        try:
            # Generate query embedding
            query_embedding = await self._generate_embedding(query, "RETRIEVAL_QUERY")
            
            # Ensure embedding is a list of floats
            if not isinstance(query_embedding, list):
                query_embedding = list(query_embedding)
            
            # Search in Qdrant
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self.qdrant_client.search(
                    collection_name="memory_vectors",
                    query_vector=query_embedding,
                    limit=top_k
                )
            )
            
            # Convert results to memory format
            memories = []
            for hit in results:
                payload = hit.payload
                memories.append({
                    "content": payload["content"],
                    "timestamp": payload["timestamp"],
                    "metadata": payload["metadata"]
                })
            
            return memories
        except Exception as e:
            await log_message(f"Error retrieving memory: {str(e)}")
            raise
    
    async def get_recent_memories(self, limit: int = 10) -> List[Dict[str, Any]]:
        if not self.initialized:
            await self.initialize()
            
        try:
            # Get all points and sort by timestamp
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self.qdrant_client.scroll(
                    collection_name="memory_vectors",
                    limit=limit,
                    with_payload=True,
                    with_vectors=False
                )[0]
            )
            
            # Sort by timestamp and take the most recent ones
            sorted_results = sorted(
                results,
                key=lambda x: x.payload["timestamp"],
                reverse=True
            )[:limit]
            
            return [{
                "content": hit.payload["content"],
                "timestamp": hit.payload["timestamp"],
                "metadata": hit.payload["metadata"]
            } for hit in sorted_results]
        except Exception as e:
            await log_message(f"Error getting recent memories: {str(e)}")
            raise

    async def visualize_memories(self) -> str:
        """Visualize memory embeddings using t-SNE or UMAP and Plotly. Save HTML locally and upload to S3 under user UUID."""
        if not self.initialized:
            await self.initialize()
        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self.qdrant_client.scroll(
                    collection_name="memory_vectors",
                    limit=1000,
                    with_payload=True,
                    with_vectors=True
                )[0]
            )
            if not results:
                raise ValueError("No memories found to visualize")
            vectors = np.array([hit.vector for hit in results])
            contents = [hit.payload["content"] for hit in results]
            timestamps = [datetime.fromisoformat(hit.payload["timestamp"]).strftime("%Y-%m-%d %H:%M:%S") for hit in results]
            # Dimensionality reduction: t-SNE for small, UMAP for large
            if len(vectors) < 768:
                from sklearn.manifold import TSNE
                reducer = TSNE(
                    n_components=2,
                    random_state=42,
                    perplexity=min(30, len(vectors) - 1),
                    metric='cosine'
                )
            else:
                from umap import UMAP
                n_neighbors = min(15, len(vectors) - 1)
                min_dist = 0.1
                reducer = UMAP(
                    n_neighbors=n_neighbors,
                    min_dist=min_dist,
                    metric='cosine',
                    random_state=42,
                    n_components=2,
                    spread=1.0,
                    set_op_mix_ratio=1.0
                )
            vectors_2d = await loop.run_in_executor(
                None,
                lambda: reducer.fit_transform(vectors)
            )
            # Prepare DataFrame for Plotly
            df = pd.DataFrame({
                'x': vectors_2d[:, 0],
                'y': vectors_2d[:, 1],
                'content': contents,
                'timestamp': timestamps
            })
            # Create density contour background
            fig = px.density_contour(df, x='x', y='y',
                                     color_discrete_sequence=['#4A90E2'],
                                     nbinsx=30, nbinsy=30)
            fig.add_trace(px.scatter(df, x='x', y='y',
                                     hover_data=['content', 'timestamp'],
                                     opacity=0.7,
                                     color_discrete_sequence=['#222']).data[0])
            fig.update_layout(
                title='Memory Embeddings Visualization',
                xaxis_title='Dim 1',
                yaxis_title='Dim 2',
                template='plotly_white',
                showlegend=False
            )
            # Save HTML locally
            user_id = get_user_uuid()
            local_dir = get_app_dir() / "visualizations" / user_id
            local_dir.mkdir(parents=True, exist_ok=True)
            html_path = local_dir / "memory_visualization.html"
            pio.write_html(fig, file=str(html_path), auto_open=True)

            return f"This is the Plotly visualization for your memory embeddings: {html_path}"
        except Exception as e:
            await log_message(f"Error visualizing memories: {str(e)}")
            raise

# Initialize FastMCP with memory protocol
mcp = FastMCP(
    name="memory_server",
    instructions="This server provides memory management capabilities using a simplified protocol.",
    log_level="ERROR"
)

# Create memory protocol instance
memory_protocol = MemoryProtocol()

@mcp.tool("record")
async def record_memory(content: str, metadata: Dict[str, Any] = None) -> List[int]:
    """Record a new memory."""
    return await memory_protocol.record_memory(content, metadata)

@mcp.tool("retrieve")
async def retrieve_memory(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Retrieve memories similar to the query."""
    return await memory_protocol.retrieve_memory(query, top_k)

@mcp.tool("recent")
async def get_recent_memories(limit: int = 10) -> List[Dict[str, Any]]:
    """Get the most recent memories."""
    return await memory_protocol.get_recent_memories(limit)

@mcp.tool("visualize")
async def visualize_memories() -> str:
    """Generate an interactive visualization of memory embeddings."""
    return await memory_protocol.visualize_memories()

async def main():
    try:
        await log_message("Starting memory server")
        await memory_protocol.initialize()
        await mcp.run()
    except Exception as e:
        await log_message(f"Error starting memory server: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())

