#!/usr/bin/env python3
"""
PDF Filename Generator Script

Two-stage process:
1. Generate content summaries for each PDF in parallel
2. Send all summaries to GPT-4o-mini to get contextually differentiated filenames
3. Rename files with the suggested names

This ensures filenames are differentiated within the folder context.
"""

import os
import sys
import argparse
from pathlib import Path
import base64
from io import BytesIO
from typing import List, Set, Optional, Tuple, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import json

try:
    from pdf2image import convert_from_path
    from PIL import Image
    import openai
except ImportError as e:
    print(f"Missing required packages. Please install: {e}")
    print("Run: uv pip install pdf2image pillow openai")
    sys.exit(1)


class PDFFilenameGenerator:
    def __init__(self, api_key: str, max_resolution: int = 2000, dry_run: bool = False, max_workers: int = 100):
        """Initialize the PDF filename generator.
        
        Args:
            api_key: OpenAI API key
            max_resolution: Maximum width/height for images sent to API
            dry_run: If True, only show what would be renamed without actually doing it
            max_workers: Maximum number of parallel workers
        """
        self.client = openai.OpenAI(api_key=api_key, max_retries=3, timeout=300)
        self.max_resolution = max_resolution
        self.dry_run = dry_run
        self.max_workers = max_workers
        
    def resize_image(self, image: Image.Image) -> Image.Image:
        """Resize image to fit within max_resolution while maintaining aspect ratio."""
        width, height = image.size
        max_dim = max(width, height)
        
        if max_dim <= self.max_resolution:
            return image
            
        scale = self.max_resolution / max_dim
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    def image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string."""
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)
        return base64.b64encode(buffer.getvalue()).decode()
    
    def extract_pdf_pages(self, pdf_path: Path, max_pages: int = 3) -> List[Image.Image]:
        """Extract first few pages from PDF as images.
        
        Args:
            pdf_path: Path to PDF file
            max_pages: Maximum number of pages to extract
            
        Returns:
            List of PIL Images
        """
        try:
            # Convert PDF pages to images (DPI 200 for good quality)
            pages = convert_from_path(pdf_path, dpi=200, first_page=1, last_page=max_pages)
            
            # Resize images to fit within resolution limits
            resized_pages = [self.resize_image(page) for page in pages]
            
            return resized_pages
        except Exception as e:
            print(f"Error extracting pages from {pdf_path}: {e}")
            return []
    
    def generate_content_summary(self, pdf_path: Path) -> Optional[Tuple[str, str]]:
        """Generate a content summary for a PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Tuple of (filename, summary) or None if failed
        """
        print(f"[{threading.current_thread().name}] Generating summary for: {pdf_path.name}")
        
        # Extract pages
        images = self.extract_pdf_pages(pdf_path)
        if not images:
            print(f"[{threading.current_thread().name}] Failed to extract pages from {pdf_path.name}")
            return None
        
        print(f"[{threading.current_thread().name}] Extracted {len(images)} page(s) from {pdf_path.name}")
        
        # Convert images to base64
        image_data = []
        for i, img in enumerate(images):
            b64_image = self.image_to_base64(img)
            image_data.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64_image}",
                    "detail": "high"
                }
            })
        
        # Generate summary prompt
        summary_prompt = f"""
        Analyze this historical document/letter and create a 2-4 sentence summary focusing on content that would be useful for creating a descriptive filename.

        Focus on:
        - Key people mentioned (names, titles, roles)
        - Specific topics, subjects, or themes discussed
        - Important dates, places, or institutions
        - Unique identifying content or events
        - Mathematical/scientific concepts if present
        - Any specific requests, applications, or correspondence purposes

        Avoid generic terms like "historical document", "letter", "manuscript" - focus on the specific, unique content.

        Original filename: {pdf_path.name}

        Provide ONLY the summary, no additional text.
        """
        
        try:
            messages = [
                {
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": summary_prompt},
                        *image_data
                    ]
                }
            ]
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=200,
                temperature=0.5
            )
            
            summary = response.choices[0].message.content.strip()
            print(f"[{threading.current_thread().name}] Generated summary for {pdf_path.name}")
            
            return (pdf_path.name, summary)
            
        except Exception as e:
            print(f"[{threading.current_thread().name}] Error generating summary for {pdf_path.name}: {e}")
            return None
    
    def generate_batch_filenames(self, summaries: Dict[str, str]) -> Optional[Dict[str, str]]:
        """Generate differentiated filenames for all files based on their summaries.
        
        Args:
            summaries: Dict mapping original filename to content summary
            
        Returns:
            Dict mapping original filename to suggested filename, or None if failed
        """
        print("Generating differentiated filenames for all documents...")
        
        # Create the batch prompt
        files_info = []
        for i, (filename, summary) in enumerate(summaries.items(), 1):
            files_info.append(f"{i}. {filename}:\n   {summary}")
        
        files_text = "\n\n".join(files_info)
        
        batch_prompt = f"""
        I have {len(summaries)} historical documents that need descriptive filenames. These are all related documents in the same collection, so the filenames should DIFFERENTIATE between them rather than repeating common information.

        Here are the document summaries:

        {files_text}

        Requirements for filenames:
        - Format: firstword_secondword_thirdword (add fourthword only if absolutely necessary)
        - Use lowercase letters and underscores only
        - Make filenames DESCRIPTIVE and DIFFERENTIATING within this specific collection
        - If most documents share common elements (like author, institution, time period), DON'T repeat those in every filename
        - Focus on what makes each document UNIQUE compared to the others
        - Avoid generic terms: "historical", "document", "letter", "manuscript", "archive", "record"
        - Each filename must be unique

        Respond with a JSON object mapping each original filename to its suggested new filename:
        {{
            "original1.pdf": "suggested_name_one",
            "original2.pdf": "suggested_name_two",
            ...
        }}

        Respond with ONLY the JSON, no additional text.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": batch_prompt}],
                max_tokens=1000,
                temperature=0.7
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Parse JSON response (handle potential markdown wrapping)
            try:
                # Remove potential markdown code blocks
                clean_text = response_text
                if clean_text.startswith('```json'):
                    clean_text = clean_text[7:]  # Remove ```json
                if clean_text.startswith('```'):
                    clean_text = clean_text[3:]   # Remove ```
                if clean_text.endswith('```'):
                    clean_text = clean_text[:-3]  # Remove trailing ```
                clean_text = clean_text.strip()
                
                filename_mapping = json.loads(clean_text)
                
                # Clean up suggested names
                cleaned_mapping = {}
                for original, suggested in filename_mapping.items():
                    # Clean up the suggested name
                    cleaned_name = suggested.lower().replace('-', '_')
                    cleaned_name = ''.join(c for c in cleaned_name if c.isalnum() or c == '_')
                    # Remove .pdf extension if present
                    cleaned_name = cleaned_name.replace('.pdf', '').replace('_pdf', '')
                    cleaned_mapping[original] = cleaned_name
                
                print(f"Generated {len(cleaned_mapping)} differentiated filenames")
                return cleaned_mapping
                
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON response: {e}")
                print(f"Response was: {response_text}")
                return None
                
        except Exception as e:
            print(f"Error generating batch filenames: {e}")
            return None
    
    def rename_file(self, old_path: Path, new_name: str) -> bool:
        """Rename a file to the new suggested name.
        
        Args:
            old_path: Current path of the file
            new_name: New filename (without extension)
            
        Returns:
            True if successful, False otherwise
        """
        new_path = old_path.parent / f"{new_name}.pdf"
        
        if self.dry_run:
            print(f"[DRY RUN] Would rename: {old_path.name} -> {new_path.name}")
            return True
        
        try:
            old_path.rename(new_path)
            print(f"✅ Renamed: {old_path.name} -> {new_path.name}")
            return True
        except Exception as e:
            print(f"❌ Failed to rename {old_path.name}: {e}")
            return False
    
    def process_folder(self, folder_path: Path, output_mapping: bool = True) -> None:
        """Process all PDFs in a folder using two-stage process.
        
        Args:
            folder_path: Path to folder containing PDFs
            output_mapping: Whether to output a mapping file
        """
        if not folder_path.exists() or not folder_path.is_dir():
            print(f"Error: {folder_path} is not a valid directory")
            return
        
        # Find all PDF files
        pdf_files = list(folder_path.glob("*.pdf"))
        if not pdf_files:
            print(f"No PDF files found in {folder_path}")
            return
        
        print(f"Found {len(pdf_files)} PDF file(s) to process")
        print(f"Using up to {min(self.max_workers, len(pdf_files))} parallel workers for summary generation")
        if self.dry_run:
            print("🔍 DRY RUN MODE - No files will actually be renamed")
        else:
            print("⚠️  DESTRUCTIVE MODE - Files will be renamed immediately!")
        print("-" * 70)
        
        start_time = time.time()
        
        # STAGE 1: Generate summaries in parallel
        print("STAGE 1: Generating content summaries...")
        print("-" * 40)
        
        summaries = {}
        processed_count = 0
        
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(pdf_files))) as executor:
            # Submit all summary generation tasks
            future_to_pdf = {executor.submit(self.generate_content_summary, pdf_file): pdf_file for pdf_file in pdf_files}
            
            # Process completed summaries as they finish
            for future in as_completed(future_to_pdf):
                pdf_file = future_to_pdf[future]
                processed_count += 1
                
                try:
                    result = future.result()
                    if result:
                        filename, summary = result
                        summaries[filename] = summary
                    
                    print(f"Summary progress: {processed_count}/{len(pdf_files)} files processed")
                    
                except Exception as e:
                    print(f"Error processing {pdf_file.name}: {e}")
        
        summary_time = time.time()
        
        if not summaries:
            print("No summaries generated. Aborting.")
            return
        
        print(f"\nSummaries generated in {summary_time - start_time:.2f} seconds")
        print(f"Successfully processed: {len(summaries)}/{len(pdf_files)} files")
        
        # Show generated summaries
        print("\n" + "="*70)
        print("GENERATED SUMMARIES:")
        print("="*70)
        for filename, summary in summaries.items():
            print(f"\n📄 {filename}:")
            print(f"   {summary}")
        
        # STAGE 2: Generate batch filenames
        print("\n" + "-" * 70)
        print("STAGE 2: Generating differentiated filenames...")
        print("-" * 40)
        
        filename_mapping = self.generate_batch_filenames(summaries)
        if not filename_mapping:
            print("Failed to generate filename mappings. Aborting.")
            return
        
        batch_time = time.time()
        print(f"Batch filename generation completed in {batch_time - summary_time:.2f} seconds")
        
        # Show proposed mappings
        print("\n" + "="*70)
        print("PROPOSED FILENAME MAPPINGS:")
        print("="*70)
        for original, suggested in filename_mapping.items():
            print(f"📄 {original} -> {suggested}.pdf")
        
        # STAGE 3: Apply renamings
        print("\n" + "-" * 70)
        print("STAGE 3: Applying filename changes...")
        print("-" * 40)
        
        successful_renames = 0
        final_mapping = {}
        
        for original_name, suggested_name in filename_mapping.items():
            pdf_path = folder_path / original_name
            if pdf_path.exists():
                if self.rename_file(pdf_path, suggested_name):
                    successful_renames += 1
                    final_mapping[original_name] = f"{suggested_name}.pdf"
            else:
                print(f"⚠️  File not found: {original_name}")
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Output final results
        print("\n" + "=" * 70)
        print("PROCESSING COMPLETE")
        print("=" * 70)
        print(f"Total processing time: {total_time:.2f} seconds")
        print(f"  - Summary generation: {summary_time - start_time:.2f} seconds")
        print(f"  - Batch filename generation: {batch_time - summary_time:.2f} seconds")
        print(f"  - File renaming: {end_time - batch_time:.2f} seconds")
        print(f"Average time per file: {total_time/len(pdf_files):.2f} seconds")
        
        if final_mapping:
            action_word = "Would be renamed" if self.dry_run else "Successfully renamed"
            print(f"\n{action_word} files:")
            for original, new_name in sorted(final_mapping.items()):
                status = "🔍" if self.dry_run else "✅"
                print(f"  {status} {original} -> {new_name}")
            
            print(f"\nSummary: {successful_renames}/{len(filename_mapping)} files processed successfully")
            
            # Save detailed mapping file
            if output_mapping:
                suffix = "_dry_run" if self.dry_run else ""
                mapping_file = folder_path / f"filename_mapping{suffix}.txt"
                with open(mapping_file, 'w') as f:
                    f.write("PDF Filename Generation Report\n")
                    f.write("=" * 50 + "\n")
                    f.write(f"Processing time: {total_time:.2f} seconds\n")
                    f.write(f"Files processed: {len(final_mapping)}/{len(pdf_files)}\n")
                    f.write("=" * 50 + "\n\n")
                    
                    f.write("SUMMARIES:\n")
                    f.write("-" * 30 + "\n")
                    for filename, summary in summaries.items():
                        f.write(f"\n{filename}:\n{summary}\n")
                    
                    f.write("\n" + "=" * 50 + "\n")
                    f.write("FILENAME MAPPINGS:\n")
                    f.write("-" * 30 + "\n")
                    for original, new_name in sorted(final_mapping.items()):
                        f.write(f"{original} -> {new_name}\n")
                        
                print(f"\nDetailed report saved to: {mapping_file}")
        else:
            print("No files were successfully processed.")


def main():
    parser = argparse.ArgumentParser(
        description="Generate contextually differentiated filenames for PDFs using two-stage AI processing"
    )
    parser.add_argument(
        "folder", 
        type=str, 
        help="Path to folder containing PDF files"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="OpenAI API key (or set OPENAI_API_KEY environment variable)"
    )
    parser.add_argument(
        "--max-resolution",
        type=int,
        default=2000,
        help="Maximum image resolution for API calls (default: 2000)"
    )
    parser.add_argument(
        "--no-mapping-file",
        action="store_true",
        help="Don't create a mapping file with results"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be renamed without actually renaming files"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=100,
        help="Maximum number of parallel workers for summary generation (default: 100)"
    )
    
    args = parser.parse_args()
    
    # Get API key
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OpenAI API key required.")
        print("Either pass --api-key or set OPENAI_API_KEY environment variable")
        sys.exit(1)
    
    # Create generator and process folder
    generator = PDFFilenameGenerator(api_key, args.max_resolution, args.dry_run, args.max_workers)
    folder_path = Path(args.folder)
    
    # Safety confirmation for destructive mode
    if not args.dry_run:
        print("⚠️  WARNING: This will immediately rename all PDF files in the folder!")
        response = input("Are you sure you want to continue? (yes/no): ").lower().strip()
        if response not in ['yes', 'y']:
            print("Operation cancelled.")
            return
    
    try:
        generator.process_folder(folder_path, not args.no_mapping_file)
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
