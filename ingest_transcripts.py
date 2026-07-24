import os
import sys
import glob
import json
import re
import zipfile
import xml.etree.ElementTree as ET

# Setup Django environment
sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_root.settings')
import django
django.setup()

from chatsystem.ai import embed_text

TRANSCRIPT_DIR = os.path.abspath('Transcribed videos')
OUTPUT_STORE_PATH = os.path.abspath('data/transcript-vector-store.json')

def read_txt(path: str) -> str:
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading TXT {path}: {e}")
        return ""

def read_docx(path: str) -> str:
    try:
        with zipfile.ZipFile(path) as z:
            xml_content = z.read('word/document.xml')
            tree = ET.fromstring(xml_content)
            paragraphs = []
            for p in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                texts = [node.text for node in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if node.text]
                if texts:
                    paragraphs.append(''.join(texts))
            return '\n'.join(paragraphs)
    except Exception as e:
        print(f"Error reading DOCX {path}: {e}")
        return ""

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150):
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start += (chunk_size - overlap)
    return chunks

def main():
    print(f"Scanning transcript files in: {TRANSCRIPT_DIR}")
    txt_files = glob.glob(os.path.join(TRANSCRIPT_DIR, '**/*.txt'), recursive=True)
    docx_files = glob.glob(os.path.join(TRANSCRIPT_DIR, '**/*.docx'), recursive=True)

    all_files = txt_files + docx_files
    print(f"Found {len(txt_files)} TXT files and {len(docx_files)} DOCX files (Total: {len(all_files)})")

    chunks_data = []

    for idx, fpath in enumerate(all_files, 1):
        fname = os.path.basename(fpath)
        rel_dir = os.path.relpath(os.path.dirname(fpath), TRANSCRIPT_DIR)
        
        if fpath.endswith('.txt'):
            raw_text = read_txt(fpath)
        else:
            raw_text = read_docx(fpath)

        if not raw_text:
            continue

        raw_chunks = chunk_text(raw_text, chunk_size=1000, overlap=150)
        print(f"[{idx}/{len(all_files)}] Processing {fname} ({rel_dir}): {len(raw_chunks)} text chunks")

        for c_idx, chunk in enumerate(raw_chunks, 1):
            chunks_data.append({
                "id": f"{fname}_{c_idx}",
                "file_name": fname,
                "category": rel_dir if rel_dir != "." else "Webinars",
                "text": chunk,
            })

    print(f"\nTotal text chunks generated: {len(chunks_data)}")
    print("Generating vector embeddings using OpenAI...")

    vector_items = []
    failed_count = 0

    for idx, item in enumerate(chunks_data, 1):
        if idx % 50 == 0 or idx == len(chunks_data):
            print(f"Embedding chunk {idx}/{len(chunks_data)}...")

        emb = embed_text(item["text"])
        if emb:
            source_label = item["file_name"].replace('.txt', '').replace('.docx', '')
            vector_items.append({
                "id": item["id"],
                "file_name": item["file_name"],
                "source": source_label,
                "category": item["category"],
                "content": item["text"],   # 'content' matches search_transcripts() field name
                "embedding": emb,
            })
        else:
            failed_count += 1

    os.makedirs(os.path.dirname(OUTPUT_STORE_PATH), exist_ok=True)
    with open(OUTPUT_STORE_PATH, 'w', encoding='utf-8') as f:
        json.dump({"chunks": vector_items}, f)  # 'chunks' matches search_transcripts() key

    print(f"\nSuccessfully created transcript vector store: {OUTPUT_STORE_PATH}")
    print(f"Total indexed chunks: {len(vector_items)} (Failed: {failed_count})")

if __name__ == "__main__":
    main()
