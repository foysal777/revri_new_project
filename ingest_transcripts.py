import os
import sys
import glob
import json
import re
import zipfile
import xml.etree.ElementTree as ET
import PyPDF2

# Setup Django environment
sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_root.settings')
import django
django.setup()

from chatsystem.ai import embed_text

ATTACHMENTS_DIR = os.path.abspath('revbri-attachments')
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

def read_pdf(path: str) -> str:
    try:
        reader = PyPDF2.PdfReader(path)
        text_parts = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
        return '\n\n'.join(text_parts).strip()
    except Exception as e:
        print(f"Error reading PDF {path}: {e}")
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

def ingest_all():
    print("=== Ingesting all knowledge files (Webinars + New Attachments) ===")
    
    files_to_process = []
    
    # 1. Transcribed videos
    for ext in ['*.txt', '*.docx']:
        files_to_process.extend(glob.glob(os.path.join(TRANSCRIPT_DIR, '**', ext), recursive=True))
        
    # 2. revbri-attachments
    for ext in ['*.txt', '*.docx', '*.pdf']:
        files_to_process.extend(glob.glob(os.path.join(ATTACHMENTS_DIR, '**', ext), recursive=True))
        
    print(f"Found total {len(files_to_process)} files for ingestion.")

    chunks_data = []

    for idx, fpath in enumerate(files_to_process, 1):
        fname = os.path.basename(fpath)
        rel_dir = "New Reports & Monograph" if "revbri-attachments" in fpath else os.path.relpath(os.path.dirname(fpath), TRANSCRIPT_DIR)
        
        if fpath.endswith('.txt'):
            raw_text = read_txt(fpath)
        elif fpath.endswith('.docx'):
            raw_text = read_docx(fpath)
        elif fpath.endswith('.pdf'):
            raw_text = read_pdf(fpath)
        else:
            continue

        if not raw_text:
            continue

        raw_chunks = chunk_text(raw_text, chunk_size=1000, overlap=150)
        print(f"[{idx}/{len(files_to_process)}] Processing {fname} ({rel_dir}): {len(raw_chunks)} text chunks")

        for c_idx, chunk in enumerate(raw_chunks, 1):
            chunks_data.append({
                "id": f"{fname}_{c_idx}",
                "file_name": fname,
                "category": rel_dir if rel_dir != "." else "Webinars",
                "text": chunk,
            })

    print(f"\nTotal text chunks generated: {len(chunks_data)}")

    # Check existing vector store
    existing_chunks_by_id = {}
    if os.path.exists(OUTPUT_STORE_PATH):
        try:
            with open(OUTPUT_STORE_PATH, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
                for c in old_data.get('chunks', []):
                    existing_chunks_by_id[c['id']] = c
            print(f"Loaded {len(existing_chunks_by_id)} pre-existing embedded chunks.")
        except Exception as e:
            print(f"Notice: Could not load existing vector store: {e}")

    vector_items = []
    new_embeddings_needed = 0

    for idx, item in enumerate(chunks_data, 1):
        chunk_id = item["id"]
        if chunk_id in existing_chunks_by_id:
            vector_items.append(existing_chunks_by_id[chunk_id])
        else:
            new_embeddings_needed += 1
            if new_embeddings_needed % 20 == 0 or idx == len(chunks_data):
                print(f"Embedding new chunk {idx}/{len(chunks_data)}...")

            emb = embed_text(item["text"])
            if emb:
                source_label = item["file_name"].replace('.txt', '').replace('.docx', '').replace('.pdf', '')
                vector_items.append({
                    "id": item["id"],
                    "file_name": item["file_name"],
                    "source": source_label,
                    "category": item["category"],
                    "content": item["text"],
                    "embedding": emb,
                })

    os.makedirs(os.path.dirname(OUTPUT_STORE_PATH), exist_ok=True)
    with open(OUTPUT_STORE_PATH, 'w', encoding='utf-8') as f:
        json.dump({"chunks": vector_items}, f)

    print(f"\nSuccessfully updated transcript vector store: {OUTPUT_STORE_PATH}")
    print(f"Total indexed chunks in store: {len(vector_items)} (New embedded: {new_embeddings_needed})")

if __name__ == "__main__":
    ingest_all()
