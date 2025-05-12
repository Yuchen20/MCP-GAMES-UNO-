import asyncio
from pathlib import Path
from typing import List, Dict, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter
from memory import MemoryProtocol, get_app_dir
import aiofiles
import json
from datetime import datetime

class TextLoader:
    def __init__(self, memory_protocol: MemoryProtocol):
        self.memory_protocol = memory_protocol
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50
        )
    
    async def load_text_file(self, file_path: str, metadata: Dict[str, Any] = None) -> List[int]:
        """
        Load a text file, split it into chunks, and store in memory.
        
        Args:
            file_path: Path to the text file
            metadata: Optional metadata to attach to all chunks
            
        Returns:
            List of memory IDs for the stored chunks
        """
        try:
            # Read the text file
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            # Split into chunks
            chunks = self.text_splitter.split_text(content)
            
            # Prepare metadata
            base_metadata = {
                "source": str(file_path),
                "file_name": Path(file_path).name,
                "load_timestamp": datetime.now().isoformat(),
                "chunk_count": len(chunks)
            }
            if metadata:
                base_metadata.update(metadata)
            
            # Store each chunk
            memory_ids = []
            for i, chunk in enumerate(chunks):
                chunk_metadata = base_metadata.copy()
                chunk_metadata["chunk_index"] = i
                
                # Record the chunk in memory
                result = await self.memory_protocol.record_memory(
                    content=chunk,
                    metadata=chunk_metadata
                )
                memory_ids.append(result)
            
            return memory_ids
            
        except Exception as e:
            print(f"Error loading text file: {str(e)}")
            raise
    
    async def load_directory(self, directory_path: str, file_pattern: str = "*.txt", metadata: Dict[str, Any] = None) -> Dict[str, List[int]]:
        """
        Load all matching text files from a directory.
        
        Args:
            directory_path: Path to the directory
            file_pattern: Glob pattern for files to load
            metadata: Optional metadata to attach to all chunks
            
        Returns:
            Dictionary mapping file paths to lists of memory IDs
        """
        directory = Path(directory_path)
        results = {}
        
        for file_path in directory.glob(file_pattern):
            try:
                memory_ids = await self.load_text_file(str(file_path), metadata)
                results[str(file_path)] = memory_ids
            except Exception as e:
                print(f"Error loading {file_path}: {str(e)}")
                continue
        
        return results

async def main():
    # Initialize memory protocol
    memory_protocol = MemoryProtocol()
    await memory_protocol.initialize()
    
    # Create text loader
    loader = TextLoader(memory_protocol)
    
    # Example usage
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if Path(file_path).is_file():
            # Load single file
            memory_ids = await loader.load_text_file(
                file_path,
                metadata={"source_type": "command_line_input"}
            )
            print(f"Loaded {len(memory_ids)} chunks from {file_path}")
        elif Path(file_path).is_dir():
            # Load directory
            results = await loader.load_directory(
                file_path,
                metadata={"source_type": "command_line_input"}
            )
            total_chunks = sum(len(ids) for ids in results.values())
            print(f"Loaded {total_chunks} chunks from {len(results)} files in {file_path}")
        else:
            print(f"Error: {file_path} is not a valid file or directory")
    else:
        print("Please provide a file or directory path as an argument")

if __name__ == "__main__":
    import sys
    asyncio.run(main()) 