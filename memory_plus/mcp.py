from fastmcp import FastMCP
from typing import List, Dict, Any
from typing import Annotated
from pydantic import Field
import json

from memory_plus.memory_protocol import MemoryProtocol
from memory_plus.utils import get_app_dir

# Create memory protocol instance
memory_protocol = MemoryProtocol()

# Initialize FastMCP with memory protocol
mcp = FastMCP(
    name="memory_server",
    instructions="""
    Memory Server Protocol:

    1. User Identification:
       - Assume all interactions are with `default_user`.
       - If `default_user` is not recognized, proactively identify them before proceeding.

    2. Category Initialization:
       - On startup, load recorded categories via `resource://recorded_memory_categories`.
       - Use this manifest to know which memory types exist and avoid unnecessary retrievals.

    3. Memory Retrieval:
       - Begin each interaction by outputting exactly `Remembering...`.
       - Retrieve context using:
         • `retrieve(query, top_k)` for semantic queries.
         • `recent(count)` for the most recently stored memories when temporal context is needed.

    4. Active Memory Listening:
       - Continuously monitor the conversation for new user-specific information across diverse categories, including but not limited to:
         a) Basic Identity (age, gender, location, job, education)
         b) Behaviors (interests, habits, daily routines)
         c) Preferences (communication style, preferred language, coding preferences, user interface tastes)
         d) Goals (short- and long-term aspirations, project objectives)
         e) Relationships (personal and professional networks, up to three degrees of separation)
         f) Expertise & Skills (programming languages, domain knowledge, certifications)
         g) Contextual Activities (current tasks, active projects, reading list, workouts)
         h) Sentiments & Emotions (emotional tone, frustration, enthusiasm)
         i) Miscellaneous Personal Details (hobbies, significant life events, cultural background)

    5. Memory Update & Recording:
       - For each candidate memory:
         a. Call `retrieve(content, top_k)` to fetch similar entries.
         b. If similarity < threshold, call `record(content, metadata)`.
         c. Otherwise, call `update(memory_id, new_content, metadata)`.
       - Use existing categories from the manifest when constructing metadata.
       - If `resource://recorded_memory_categories` hasn't been fetched, do so before recording.

    6. Memory Visualization:
       - Provide a visualization of stored memories on demand or for debugging.

    All operations run transparently in the background to enhance personalization without user intervention.
    """,
    log_level="ERROR"
)



@mcp.tool("set_whether_to_annonimize")
def set_whether_to_annonimize(
    whether_to_annonimize: Annotated[bool, Field(description="Whether to annonimize the content")] = False
) -> bool:
    """
    Set whether to annonimize the content.
    """
    # open the file and write the whether_to_annonimize
    with open(get_app_dir() / "whether_to_annonimize.txt", "w") as f:
        f.write(str(whether_to_annonimize))
    return str(whether_to_annonimize)

@mcp.resource("resource://recorded_memory_categories")
def get_recorded_memory_categories() -> str:
    """
    Retrieve the list of recorded memory categories and their associated tags.

    This resource provides a structured overview of what categories of memory have been stored 
    (e.g., "coding_preference", "personal_detail"). It helps the assistant determine whether 
    retrieving memory is appropriate in a given context by indicating the available memory domains.

    Returns:
        str: A JSON-encoded string mapping each category to its list of known tags.
    """
    return json.dumps(memory_protocol.load_recorded_categories())

@mcp.tool("record")
def record_memory(
    content: Annotated[str, Field(description=(
        "The content parameter should reproduce the user's own words as closely as possible (quoting or lightly paraphrasing) so the stored memory reflects their exact intent and tone."
        )
    )],
    metadata: Annotated[Dict[str, Any], Field(
        description=(
            """
Metadata provides structured context for the memory. You should provide a dictionary like this:
{
    'source': string // Identifier for the originating client or channel (e.g., "Cursor", "Cline", "Claude Desktop", ...)
    'ai_model': string // Name and version of the AI model that generated this memory (e.g., "gpt-4-turbo-2025-05")
    'category': string // Broad classification of the memory (e.g., "personal_detail", "preference")
    'tags': [string] // List of keywords for fine-grained filtering (e.g., ["coding_style", "favorite_music"]) 
    'intent': string // Purpose or context (e.g., "reminder", "setup_preference") 
    'privacy_level': string // Sensitivity level (e.g., "public", "private", "sensitive")
}
            """
        )
    )] = None,
) -> List[int]:
    """
    This tool is invoked automatically when the assistant detects enduring, user-specific information—such as stable preferences, personal background facts, or recurring discussion topics—that can enrich subsequent responses.

    - Trigger: Automatically invoked when the assistant detects a stable user detail (e.g. preference, background fact, recurring topic).  
    - Precondition: 
        - The assistant SHOULD first call `retrieve(content, top_k)` to fetch top_k similar memories.  
        - If resource://recorded_memory_categories has not been called in the current conversation, the assistant should call it first to understand which memory categories already exist. The assistant should prefer using existing categories from the resource when constructing the metadata for the new memory.

    - Decision:  
        - If any retrieved memory has similarity really high, use `update(memory_id, new_content, metadata)`;  
        - Otherwise, use `record(content, metadata)`.  

    Returns a list of newly assigned memory IDs.
    """
    memory_protocol.update_recorded_categories(metadata)
    return memory_protocol.record_memory(content, metadata)

@mcp.tool("retrieve")
def retrieve_memory(
    query: Annotated[str, Field(description="A natural language query or key phrase used to search the memory store.")],
    top_k: Annotated[int, Field(description="Maximum number of relevant memory entries to return.", ge=5, le=100)] = 5
) -> List[Dict[str, Any]]:
    """
    Retrieve up to `top_k` memory entries that are most semantically similar to the given `query`.

    This tool enables contextual awareness by allowing the assistant to recall relevant user-specific information previously stored in memory—such as preferences, background details, ongoing projects, or recurring topics—based on semantic similarity to the input query.

    The assistant should automatically call this tool when additional context is needed to improve understanding or response quality, even without explicit user instruction. 

    To avoid unnecessary or irrelevant memory retrievals, the assistant should first check `resource://recorded_memory_categories` to understand what kinds of memory categories are currently available.

    Returns a list of memory entries, each containing:
      - `content`: The distilled memory text (as originally stored).
      - `metadata`: Structured metadata describing the memory, including fields such as `category`, 
        `tags`, `timestamp`, `source`, and other contextual details.

    Returns:
        List[Dict[str, Any]]: A list of memory entries ordered from most to least relevant.
    """
    return memory_protocol.retrieve_memory(query, top_k)

@mcp.tool("recent")
def get_recent_memories(
    limit: Annotated[int, Field(
        description="Maximum number of recent memories to retrieve.",
        ge=1, le=100
    )] = 5
) -> List[Dict[str, Any]]:
    """
    Retrieve the most recently recorded memory entries, up to `limit` items.

    The assistant should automatically call this function when composing responses that benefit from the freshest context—
    such as referencing what the user just said, recent preferences, or newly provided details.

    Each returned entry contains:
      - `content`: The stored memory text
      - `metadata`: Associated metadata (e.g., timestamp, category, context source)

    Returns:
      A list of memory dictionaries ordered from newest to oldest.
    """
    return memory_protocol.get_recent_memories(limit)

@mcp.tool("update")
def update_memory(
    memory_id: Annotated[int, Field(description="The ID of the memory to update")],
    new_content: Annotated[str, Field(description="The new content to replace the existing memory")],
    metadata: Annotated[Dict[str, Any], Field(
        description= """
Metadata provides structured context for the memory. You should provide a dictionary like this:
{
    'source': string // Identifier for the originating client or channel (e.g., "Cursor", "Cline", "Claude Desktop", ...)
    'ai_model': string // Name and version of the AI model that generated this memory, what is the name of the model?
    'category': string // Broad classification of the memory (e.g., "personal_detail", "preference")
    'tags': [string] // List of keywords for fine-grained filtering (e.g., ["coding_style", "favorite_music"]) 
    'intent': string // Purpose or context (e.g., "reminder", "setup_preference") 
    'privacy_level': string // Sensitivity level (e.g., "public", "private", "sensitive")
    'previous_versions': [string] // List of previous versions of the memory
}"""
    )] = None,
) -> bool:
    """
    Update an existing memory with new content and metadata.

    - Trigger: When there is an old memory that is similar to the new content, which can be checked whenever there is a new memory recorded.
    - Precondition: 
        - The assistant should first retrieve the existing memory with `retrieve(content, top_k)`
    - Decision:
        - If the old memory is similar to the new content, use `update(memory_id, new_content, metadata)`
        - Otherwise, use `record(content, metadata)`

    Args:
        memory_id: The ID of the memory to update
        new_content: The new content to replace the existing memory
        metadata: metadata for the updated memory

    Returns:
        True if the update was successful, raises an exception otherwise
    """
    return memory_protocol.update_memory(memory_id, new_content, metadata)

@mcp.tool("visualize")
def visualize_memories() -> str:
    """
    Create and return a URL or embedded HTML snippet for an interactive visualization of user memory embeddings.

    The visualization highlights semantic clusters and temporal trends among recorded memories, enabling the assistant or user to explore how different preferences or details relate. 
    The assistant should automatically call this tool when a visual overview of stored memories would improve context or transparency.
    After all, this is just a nice visualization, so don't use it too frequently.

    Returns:
      A string of a URL pointing to a hosted interactive visualization dashboard
    """
    return memory_protocol.visualize_memories()

@mcp.tool("delete")
def delete_memory(
    memory_id: Annotated[int, Field(description="The ID of the memory to delete")],
    confirmation: Annotated[bool, Field(description="Confirmation that you want to delete this memory")] = False
) -> bool:
    """
    Delete a memory by its ID.

    - Trigger: When the user explicitly requests to delete a specific memory.
    - Precondition: 
        - The assistant should first retrieve the memory with `retrieve(content, top_k)` to confirm it exists
        - The assistant should ask for user confirmation before proceeding
    - Decision:
        - If user confirms, use `delete(memory_id, confirmation=True)`
        - Otherwise, do not proceed with deletion

    Args:
        memory_id: The ID of the memory to delete
        confirmation: Must be True to proceed with deletion

    Returns:
        True if the deletion was successful, raises an exception otherwise
    """
    if not confirmation:
        raise ValueError("Deletion requires explicit confirmation")
    return memory_protocol.delete_memory(memory_id)

@mcp.tool("import_file")
def import_file(
    file_path: Annotated[str, Field(description="Path to the file to import")],
    metadata: Annotated[Dict[str, Any], Field(
        description="""
Optional metadata to override default import metadata. Default metadata is:
{
    'source': file_path,
    'file_name': filename,
    'ai_model': None,
    'category': 'external_import',
    'tags': [],
    'intent': 'bulk_import',
    'privacy_level': 'private'
}
"""
    )] = None
) -> List[int]:
    """
    Import a file into the memory database.

    - Trigger: When the user wants to import a file's contents into memory
    - Precondition: 
        - The file must exist and be readable
        - The file should be text-based (txt, md, etc.)
    - Decision:
        - For markdown files, use structured splitting based on headers
        - For other text files, use semantic chunking

    Args:
        file_path: Path to the file to import
        metadata: Optional metadata to override defaults

    If fails, check if it is the full path of the file, if not hint the user to provide the full path.

    Returns:
        List of memory IDs for the imported chunks
    """
    return memory_protocol.import_file(file_path, metadata)

@mcp.prompt("Save Chat History")
def save_chat() -> str:
    """
    Analyze the ongoing chat to identify and persist important user-specific information.
    """
    return "Based on the chat history, identify some of the important things and save them."

@mcp.prompt("Visualize (plot)")
def visualize_memories() -> str:
    """
    Create and return a URL or embedded HTML snippet for an interactive visualization of user memory embeddings.
    """
    return "Create and return a URL or embedded HTML snippet for an interactive visualization of user memory embeddings."

def main():
    """Entry point for the memory server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Memory Server using FastMCP")
    parser.add_argument("--host", default="localhost", help="Host to run the server on")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the server on")
    parser.add_argument("--log-level", default="ERROR", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                      help="Logging level")
    
    args = parser.parse_args()
    
    try:
        memory_protocol.initialize()
        
        # Update FastMCP configuration
        mcp.host = args.host
        mcp.port = args.port
        mcp.log_level = args.log_level
        
        mcp.run()
        # print('memory server started')
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    main() 