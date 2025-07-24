from text_extractor import convert_chunks_to_html, unite_chunks, translate_all_files
from file_renamer import PDFFilenameGenerator
from chunk_extractor import ChunkExtractor
from pathlib import Path
import os


# Initialize the chunk extractor and process PDF files
# api_key = os.getenv('OPENAI_API_KEY')
# extractor = ChunkExtractor(api_key=api_key)
# extractor.process_folder(Path("public/samples/"), visualize=False, parallelize=True)
convert_chunks_to_html("public/chunks")
unite_chunks("public/html_parts", parallelize=True)
translate_all_files("public/html_de", "public/html_en", parallelize=True)