from flask import Flask, jsonify, send_from_directory
import os
import json

app = Flask(__name__, static_folder='public')

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/favicon.ico')
def favicon():
    return '', 204  # No Content response for favicon

@app.route('/<path:path>')
def serve_public(path):
    return send_from_directory('public', path)

@app.route('/api/letters')
def get_letters():
    letters_dir = os.path.join('public', 'samples')
    letters = [f for f in os.listdir(letters_dir) if f.endswith('.pdf')]
    return jsonify(letters)

@app.route('/api/metadata')
def get_metadata():
    metadata_path = os.path.join('public', 'metadata', 'metadata.json')
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        return jsonify(metadata)
    return jsonify({})

@app.route('/api/html-parts/<letter_id>')
def get_html_parts(letter_id):
    """Get all HTML parts files that match the given letter ID"""
    html_parts_dir = os.path.join('public', 'html_parts')
    if not os.path.exists(html_parts_dir):
        return jsonify([])
    
    # Find all files that start with the letter_id
    matching_files = [f for f in os.listdir(html_parts_dir) 
                     if f.startswith(letter_id) and f.endswith('.html')]
    matching_files.sort()  # Sort for consistent ordering
    return jsonify(matching_files)

@app.route('/api/html-files/<letter_id>')
def get_html_files(letter_id):
    """Get HTML files from html_de and html_en directories for the given letter ID"""
    result = {}
    
    # Check html_de
    html_de_path = os.path.join('public', 'html_de', f'{letter_id}_.html')
    if os.path.exists(html_de_path):
        result['html_de'] = f'{letter_id}_.html'
    
    # Check html_en
    html_en_path = os.path.join('public', 'html_en', f'{letter_id}_.html')
    if os.path.exists(html_en_path):
        result['html_en'] = f'{letter_id}_.html'
    
    return jsonify(result)

@app.route('/api/chunks/<letter_id>')
def get_chunks(letter_id):
    """Get all image chunks that match the given letter ID"""
    chunks_dir = os.path.join('public', 'chunks')
    if not os.path.exists(chunks_dir):
        return jsonify([])
    
    # Find all files that start with the letter_id
    matching_chunks = [f for f in os.listdir(chunks_dir) 
                      if f.startswith(letter_id) and f.endswith('.jpg')]
    matching_chunks.sort()  # Sort for consistent ordering
    return jsonify(matching_chunks)

if __name__ == '__main__':
    app.run(debug=True, port=8001) 