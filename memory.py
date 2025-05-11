from itertools import tee
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
from typing import Annotated
from pydantic import Field
from sklearn.cluster import KMeans
import plotly.graph_objects as go
from scipy.spatial import distance
import textwrap

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
                    "id": hit.id,
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
                "id": hit.id,
                "content": hit.payload["content"],
                "timestamp": hit.payload["timestamp"],
                "metadata": hit.payload["metadata"]
            } for hit in sorted_results]
        
        except Exception as e:
            await log_message(f"Error getting recent memories: {str(e)}")
            raise

    async def update_memory(self, memory_id: int, new_content: str, metadata: Dict[str, Any] = None) -> bool:
        """Update an existing memory with new content and metadata"""
        if not self.initialized:
            await self.initialize()
            
        try:
            # Generate new embedding for the updated content
            new_embedding = await self._generate_embedding(new_content)
            
            # Ensure embedding is a list of floats
            if not isinstance(new_embedding, list):
                new_embedding = list(new_embedding)
            
            # Update in Qdrant
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.qdrant_client.upsert(
                    collection_name="memory_vectors",
                    points=[
                        models.PointStruct(
                            id=memory_id,
                            vector=new_embedding,
                            payload={
                                "content": new_content,
                                "timestamp": datetime.now().isoformat(),
                                "metadata": metadata or {}
                            }
                        )
                    ]
                )
            )
            
            await log_message(f"Successfully updated memory with ID: {memory_id}")
            return True
        except Exception as e:
            await log_message(f"Error updating memory: {str(e)}")
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
            
            # Perform Clustering
            cluster_number = min(5, len(df))  # Use at most 5 clusters
            kmeans = KMeans(n_clusters=cluster_number, random_state=42, n_init='auto')
            df['cluster'] = kmeans.fit_predict(vectors_2d)
            cluster_centers = kmeans.cluster_centers_
            
            # Find Closest Point to each Cluster Center
            closest_points_indices = []
            for i in range(len(cluster_centers)):
                center = cluster_centers[i]
                points_in_cluster = df[df['cluster'] == i][['x', 'y']].values
                
                if len(points_in_cluster) == 0:
                    continue
                    
                # Calculate distances from the center to all points in this cluster
                distances_to_center = [distance.euclidean(point, center) for point in points_in_cluster]
                
                # Find the index of the minimum distance within the subset
                min_dist_idx_in_subset = np.argmin(distances_to_center)
                
                # Get the original index from the main dataframe
                original_idx = df[df['cluster'] == i].index[min_dist_idx_in_subset]
                closest_points_indices.append(original_idx)
            
            df_closest_points = df.loc[closest_points_indices]
            
            # Create Plot
            # Base density contour
            fig = px.density_contour(df, x='x', y='y',
                                     nbinsx=cluster_number * 2, nbinsy=cluster_number * 2)
            
            # Style the contour trace
            fig.update_traces(
                contours_coloring='fill',
                colorscale='Blues',
                contours_showlabels=False,
                opacity=0.6,
                selector=dict(type='histogram2dcontour')
            )
            if len(fig.data) > 0 and isinstance(fig.data[0], go.Histogram2dContour):
                fig.data[0].showscale = False
            
            # Add scatter points
            fig.add_trace(go.Scatter(
                x=df['x'],
                y=df['y'],
                mode='markers',
                marker=dict(
                    color='#222222',
                    size=7,
                    opacity=0.7
                ),
                customdata=df[['content', 'timestamp']],
                hovertemplate="<b>Content:</b> %{customdata[0]}<br><b>Timestamp:</b> %{customdata[1]}<extra></extra>"
            ))
            
            def wrap_text(text, width=80):
                """Wrap text with <br> tags for Plotly annotations."""
                return "<br>".join(textwrap.wrap(text, width))
            # Add Text Labels with Boxes for the closest points
            for i, row in df_closest_points.iterrows():
            
                fig.add_annotation(
                    x=row['x'],
                    y=row['y'],
                    text=wrap_text(row['content']),
                    showarrow=False,
                    xanchor="left",
                    yanchor="bottom",
                    xshift=7,
                    yshift=7,
                    font=dict(family="Arial, Sans-serif", size=10, color="#111111"),
                    align="left",
                    bordercolor="#777777",
                    borderwidth=1,
                    borderpad=4,
                    bgcolor="rgba(255, 255, 255, 0.9)",
                    opacity=1
                )
            
            # Layout and Styling
            fig.update_layout(
                title_text='Memory Embeddings Visualization',
                title_font_size=16,
                title_x=0.5,
                template='plotly_white',
                showlegend=False,
                xaxis=dict(showgrid=False, zeroline=False, visible=False),
                yaxis=dict(showgrid=False, zeroline=False, visible=False),
                margin=dict(l=20, r=20, t=60, b=20),
                hovermode='closest'
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
    instructions=(
        "This server provides memory management capabilities using a simplified protocol. "
        "It should be used automatically by the assistant to record, retrieve, and visualize user-specific information without explicit prompts."
    ),
    log_level="ERROR"
)

# Create memory protocol instance
memory_protocol = MemoryProtocol()

@mcp.tool("record")
async def record_memory(
    content: Annotated[str, Field(description="A concise summary of the user detail or pattern to remember." )],
    metadata: Annotated[Dict[str, Any], Field(
        description=(
            "Optional metadata describing the type, source, and context of the memory. "
            "E.g., {'category': 'preference', 'source': 'interaction', 'timestamp': '2025-05-10T12:00:00Z'}"
        )
    )] = None
) -> List[int]:
    """
    Record a new memory entry in the assistant's memory store. Before recording a new memory, the assistant should `retrieve` and check if there is an old memory that is similar to the new content. If there is, it should use the `update` tool to update the old memory.

    This tool is designed for background use: the assistant should call it automatically when it identifies
    enduring user-specific information — such as stable preferences, personal background, or recurring topics — that can enhance future responses. The `content` parameter holds the distilled memory text, 
    and `metadata` provides structured context (e.g., category, origin, timestamp).

    Returns a list of newly assigned memory IDs.
    """
    return await memory_protocol.record_memory(content, metadata)


@mcp.tool("retrieve")
async def retrieve_memory(
    query: Annotated[str, Field(description="A natural-language prompt or key phrase to search the memory store." )],
    top_k: Annotated[int, Field(description="The maximum number of relevant memories to return.", ge=1, le=100)] = 5
) -> List[Dict[str, Any]]:
    """
    Retrieve up to `top_k` past memories most semantically similar to the input `query`.

    The assistant should automatically invoke this function when it needs contextual user history—
    for example, to recall stable preferences, earlier-discussed projects, or personal details—
    without explicit user instruction. Returns a list of memory entries, each including:
      - `content`: the stored memory text
      - `metadata`: associated metadata such as category, timestamp, and source context

    Args:
      query: Text to match against stored memories.
      top_k: Number of top-matching memories to retrieve.

    Returns:
      A list of dictionaries with keys `content`, and `metadata`, ordered by relevance.
    """
    return await memory_protocol.retrieve_memory(query, top_k)


@mcp.tool("recent")
async def get_recent_memories(
    limit: Annotated[int, Field(
        description="Maximum number of recent memories to retrieve.",
        ge=1, le=100
    )] = 10
) -> List[Dict[str, Any]]:
    """
    Retrieve the most recently recorded memory entries, up to `limit` items.

    The assistant should automatically call this function when composing responses that benefit from the freshest context—
    such as referencing what the user just said, recent preferences, or newly provided details.

    Each returned entry contains:
      - `content`: The stored memory text
      - `metadata`: Associated metadata (e.g., timestamp, category, context source)

    Args:
      limit: The maximum number of recent memories to return.

    Returns:
      A list of memory dictionaries ordered from newest to oldest.
    """
    return await memory_protocol.get_recent_memories(limit)


@mcp.tool("update")
async def update_memory(
    memory_id: Annotated[int, Field(description="The ID of the memory to update")],
    new_content: Annotated[str, Field(description="The new content to replace the existing memory")],
    metadata: Annotated[Dict[str, Any], Field(
        description=(
            "Optional metadata describing the type, source, and context of the updated memory. "
            "E.g., {'category': 'preference', 'source': 'interaction', 'timestamp': '2025-05-10T12:00:00Z'}"
        )
    )] = None,
    user_confirmed: Annotated[bool, Field(description="User's explicit confirmation to update the memory")] = False
) -> bool:
    """
    Update an existing memory with new content and metadata.

    This tool should only be used when there is an old memory that is similar to the new content, which can be checked whenever there is a new memory recorded. The update action must be confirmed by the user.
    The assistant should first retrieve the existing memory, show it to the user, and get their confirmation before proceeding with the update.

    Args:
        memory_id: The ID of the memory to update
        new_content: The new content to replace the existing memory
        metadata: Optional metadata for the updated memory
        user_confirmed: Must be True to proceed with the update

    Returns:
        True if the update was successful, raises an exception otherwise
    """
    if not user_confirmed:
        raise ValueError("User confirmation is required to update a memory")
    return await memory_protocol.update_memory(memory_id, new_content, metadata)

@mcp.tool("visualize")
async def visualize_memories() -> str:
    """
    Create and return a URL or embedded HTML snippet for an interactive visualization of user memory embeddings.

    The visualization highlights semantic clusters and temporal trends among recorded memories, enabling the assistant or user to explore how different preferences or details relate. 
    The assistant should automatically call this tool when a visual overview of stored memories would improve context or transparency.
    After all, this is just a nice visualization, so don't use it too frequently, but should be used when the user asks for it.

    Returns:
      A string of a URL pointing to a hosted interactive visualization dashboard
    """
    return await memory_protocol.visualize_memories()

@mcp.prompt("save_chat")
async def save_chat() -> str:
    """
    Analyze the ongoing chat to identify and persist important user-specific information.
    """
    return "Based on the chat history, identify some of the important memories and save them."



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

