#!/bin/bash

echo "ChunkExtractor - Multiple Usage Examples"
echo "========================================"

source .venv/bin/activate

echo ""
echo "1. Extracting chunks from single PDF (saves to public/chunks/):"
./.venv/bin/python chunk_extractor.py public/samples/Hs_91_676-687-pages-6.pdf

echo ""
echo "2. Extracting chunks from all PDFs in folder (saves to public/chunks/):"
./.venv/bin/python chunk_extractor.py public/samples/

echo ""
echo "3. Visualizing single image with colored boxes:"
./.venv/bin/python chunk_extractor.py --visualize public/hidden_extracted/anmeldung_page_1.jpg

echo ""
echo "4. Visualizing single PDF with colored boxes (opens windows):"
# ./.venv/bin/python chunk_extractor.py --visualize public/samples/Hs_91_676-687-pages-6.pdf

echo ""
echo "5. Visualizing all PDFs in folder with colored boxes (opens many windows):"
# ./.venv/bin/python chunk_extractor.py --visualize public/samples/

echo ""
echo "All processing complete!" 