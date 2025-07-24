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
    letters_dir = os.path.join('public', 'samples2')
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

if __name__ == '__main__':
    app.run(debug=True, port=8001) 