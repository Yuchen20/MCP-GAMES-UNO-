from datetime import datetime
import json
from typing import List, Dict, Any
import os
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import OrderBy, Direction
from langchain.text_splitter import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
from google import genai
from google.genai import types
import numpy as np
import plotly.express as px
import plotly.io as pio
import pandas as pd
from sklearn.cluster import KMeans
import plotly.graph_objects as go
from scipy.spatial import distance
import textwrap
from pathlib import Path

from .utils import get_app_dir, get_user_uuid, get_whether_to_annonimize

class MemoryProtocol:
    def __init__(self, qdrant_path: str = None):
        if qdrant_path is None:
            qdrant_path = str(get_app_dir() / "memory_db")
        self.qdrant_path = qdrant_path
        self.initialized = False
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")
        
    def initialize(self):
        """Initialization of the memory protocol"""
        if self.initialized:
            return
            
        # log_message("Starting memory server initialization")
        
        # Initialize text splitter with improved settings
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,  # Increased chunk size for better context
            chunk_overlap=200,  # Increased overlap for better continuity
            length_function=len,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""],  # More granular separators
            keep_separator=True  # Keep separators for better readability
        )
        
        # Initialize markdown splitter for structured documents
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "Header 1"),
                ("##", "Header 2"),
                ("###", "Header 3"),
            ]
        )
        
        # Initialize Gemini with explicit API key
        self.client = genai.Client(api_key=self.api_key)
        
        # log_message("Memory server initialization completed")
        self.initialized = True

    def _get_qdrant_client(self):
        """Get a Qdrant client instance"""
        return QdrantClient(path=f"{self.qdrant_path}")

    def _init_qdrant(self, client):
        """Initialize Qdrant collection"""
        collection_name = "memory_vectors"
        try:
            client.get_collection(collection_name)
        except Exception:
            # Create collection if it doesn't exist
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=768,
                    distance=models.Distance.COSINE
                )
            )

    def _with_qdrant(self, operation):
        """Context manager for Qdrant operations"""
        client = self._get_qdrant_client()
        try:
            # Initialize collection if needed
            self._init_qdrant(client)
            return operation(client)
        finally:
            client.close()

    def _generate_embedding(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT"):
        """Generate embedding"""
        if not self.initialized:
            self.initialize()
            
        try:
            response = self.client.models.embed_content(
                model="gemini-embedding-exp-03-07",
                contents=text,
                config=types.EmbedContentConfig(task_type=task_type,
                                                output_dimensionality=768)
            )
            # Extract the embedding vector from the response
            if hasattr(response, 'embeddings'):
                return response.embeddings[0].values
            elif hasattr(response, 'values'):
                return response.values
            else:
                raise ValueError(f"Unexpected embedding response format: {response}")
        except Exception as e:
            # log_message(f"Error generating embedding: {str(e)}")
            return f"Error: {str(e)}"

    def load_recorded_categories(self, ) -> Dict[str, List[str]]:
        """Load the existing category/tag structure from the JSON file."""
        CATEGORY_FILE = get_app_dir() / "recorded_category.json"

        if not CATEGORY_FILE.exists():
            return {}
        with open(CATEGORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    def update_recorded_categories(self, metadata: Dict[str, any]) -> None:
        """
        Update the recorded categories file with new category or tags.
        
        Args:
            metadata: dict containing at least 'category' (str) and 'tags' (List[str])
        """
        category = metadata.get("category")
        tags = metadata.get("tags", [])
        
        if not category:
            return  # No update if no category provided
        
        # Load existing
        categories = self.load_recorded_categories()
        
        # Update or insert
        existing_tags = set(categories.get(category, []))
        updated_tags = list(existing_tags.union(tags))
        
        categories[category] = updated_tags
        
        # Save updated structure
        CATEGORY_FILE = get_app_dir() / "recorded_category.json"
        CATEGORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CATEGORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(categories, f, indent=2, ensure_ascii=False)

    def record_memory(self, content: str, metadata: Dict[str, Any] = None) -> List[int]:
        if not self.initialized:
            self.initialize()

        # Split content into chunks
        chunks = self.text_splitter.split_text(content)
        memory_ids = []
        
        def record_operation(client):
            # Process chunks
            for i, chunk in enumerate(chunks):
                try:
                    # Generate embedding
                    embedding = self._generate_embedding(chunk)
                    
                    # Ensure embedding is a list of floats
                    if not isinstance(embedding, list):
                        embedding = list(embedding)
                    
                    # Generate a unique ID
                    memory_id = int(datetime.now().timestamp() * 1000) + i
                    
                    # Store in Qdrant
                    client.upsert(
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
                    
                    memory_ids.append(memory_id)
                except Exception as e:
                    # log_message(f"Error processing chunk: {str(e)}")
                    return [f"Error: {str(e)}"]
            return memory_ids

        return self._with_qdrant(record_operation)
    
    def retrieve_memory(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not self.initialized:
            self.initialize()
            
        def retrieve_operation(client):
            try:
                # Generate query embedding
                query_embedding = self._generate_embedding(query, "RETRIEVAL_QUERY")
                
                # Ensure embedding is a list of floats
                if not isinstance(query_embedding, list):
                    query_embedding = list(query_embedding)
                
                # Search in Qdrant
                results = client.search(
                    collection_name="memory_vectors",
                    query_vector=query_embedding,
                    limit=top_k
                )
                
                # Convert results to memory format
                memories = []
                for hit in results:
                    payload = hit.payload
                    if get_whether_to_annonimize() == "True":
                        response = self.client.models.generate_content(
                            model="gemini-2.0-flash-lite",
                            contents=[f"please annonimize (any person name, address, phone number, email, etc.) the following content (replace the sensitive information with '❏'): {payload['content']}"]
                        )
                        payload["content"] = response.text
                        
                    memories.append({
                        "id": hit.id,
                        "content": payload["content"],
                        "timestamp": payload["timestamp"],
                        "metadata": payload["metadata"]
                    })
            
                return memories
            except Exception as e:
                # log_message(f"Error retrieving memory: {str(e)}")
                return f"Error: {str(e)}"

        return self._with_qdrant(retrieve_operation)
    
    def get_recent_memories(self, limit: int = 10) -> List[Dict[str, Any]]:
        if not self.initialized:
            self.initialize()

        def recent_operation(client):
            try:
                results = client.scroll(
                    collection_name="memory_vectors",
                    limit=limit,
                    order_by=OrderBy(key="timestamp", direction=Direction.DESC),
                    with_payload=True,
                    with_vectors=False
                )[0]
                
                memories = []
                for hit in results:
                    payload = hit.payload
                    if get_whether_to_annonimize() == "True":
                        response = self.client.models.generate_content(
                            model="gemini-2.0-flash-lite",
                            contents=[f"please annonimize (any person name, address, phone number, email, etc.) the following content (replace the sensitive information with '❏'): {payload['content']}"]
                        )
                        payload["content"] = response.text

                    memories.append({
                        "id": hit.id,
                        "content": payload["content"],
                        "timestamp": payload["timestamp"],
                        "metadata": payload["metadata"]
                    })
                
                return memories
            
            except Exception as e:
                # log_message(f"Error getting recent memories: {str(e)}")
                return f"Error: {str(e)}"

        return self._with_qdrant(recent_operation)

    def update_memory(self, memory_id: int, new_content: str, metadata: Dict[str, Any] = None) -> bool:
        """Update an existing memory with new content and metadata"""
        if not self.initialized:
            self.initialize()
            
        def update_operation(client):
            try:
                # Generate new embedding for the updated content
                new_embedding = self._generate_embedding(new_content)
                
                # Ensure embedding is a list of floats
                if not isinstance(new_embedding, list):
                    new_embedding = list(new_embedding)
                
                # Update in Qdrant
                client.upsert(
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
                
                # log_message(f"Successfully updated memory with ID: {memory_id}")
                return True
            except Exception as e:
                # log_message(f"Error updating memory: {str(e)}")
                return False

        return self._with_qdrant(update_operation)

    def visualize_memories(self) -> str:
        """Visualize memory embeddings using t-SNE or UMAP and Plotly. Save HTML locally and upload to S3 under user UUID."""
        if not self.initialized:
            self.initialize()

        def visualize_operation(client):
            try:
                results = client.scroll(
                    collection_name="memory_vectors",
                    limit=1000,
                    with_payload=True,
                    with_vectors=True
                )[0]
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
                vectors_2d = reducer.fit_transform(vectors)
                
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
                    mode='markers',  # <-- Use markers instead of text
                    marker=dict(
                        size=10,
                        color='rgba(255, 182, 193, .9)',  # set color to pink
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
                # log_message(f"Error visualizing memories: {str(e)}")
                return f"Error: {str(e)}"

        return self._with_qdrant(visualize_operation)

    def delete_memory(self, memory_id: int) -> bool:
        """Delete a memory by its ID"""
        if not self.initialized:
            self.initialize()
            
        def delete_operation(client):
            try:
                # Delete from Qdrant
                client.delete(
                    collection_name="memory_vectors",
                    points_selector=models.PointIdsList(
                        points=[memory_id]
                    )
                )
                
                # log_message(f"Successfully deleted memory with ID: {memory_id}")
                return True
            except Exception as e:
                # log_message(f"Error deleting memory: {str(e)}")
                return False

        return self._with_qdrant(delete_operation)

    def import_file(self, file_path: str, metadata: Dict[str, Any] = None) -> List[int]:
        """Import a file into the memory database"""
        if not self.initialized:
            self.initialize()
            
        try:
            # Read the file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Determine if it's a markdown file
            is_markdown = file_path.lower().endswith(('.md', '.markdown'))
            
            # Split content based on file type
            if is_markdown:
                # Use markdown splitter for structured documents
                splits = self.markdown_splitter.split_text(content)
                chunks = [split.page_content for split in splits]
            else:
                # Use regular text splitter for other files
                chunks = self.text_splitter.split_text(content)
            
            # Prepare base metadata
            base_metadata = {
                "source": str(file_path),
                "file_name": Path(file_path).name,
                "ai_model": None,
                "category": "external_import",
                "tags": [],
                "intent": "bulk_import",
                "privacy_level": "private",
                "import_timestamp": datetime.now().isoformat(),
                "chunk_count": len(chunks)
            }
            
            # Update with provided metadata
            if metadata:
                base_metadata.update(metadata)
            
            # Store chunks
            memory_ids = []
            for i, chunk in enumerate(chunks):
                chunk_metadata = base_metadata.copy()
                chunk_metadata["chunk_index"] = i
                
                # Record the chunk
                memory_ids.extend(self.record_memory(chunk, chunk_metadata))
            
            # log_message(f"Successfully imported {len(memory_ids)} chunks from {file_path}")
            return memory_ids
            
        except Exception as e:
            # log_message(f"Error importing file: {str(e)}")
            return [f"Error: {str(e)}"] 