"""
Comprehensive AI module for Django: embeddings, RAG, product recommendations, moderation.
All AI logic self-contained locally — no external service dependency.

Features:
- Embeddings: text vectorization via OpenAI
- Vector store: file-backed product index with search
- RAG: query + prompt building + LLM response
- Recommendations: semantic product ranking with LLM intent classification
- Smart clarification: AI asks follow-up questions for vague queries
- Conversation history: multi-turn context-aware responses
- Moderation: blocked keyword detection and counting
- Signals: auto-index products on save/delete
"""
import os
import re
import json
from typing import Optional, List, Dict, Any
from django.conf import settings
from django.db.models import Q
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from openai import OpenAI
from PyPDF2 import PdfReader

from .models import AISetting, BlockedKeyword, KnowledgePDF, UserQueryLog


# ---- Configuration ----
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY') or getattr(settings, 'OPENAI_API_KEY', None)
EMBEDDING_MODEL = getattr(settings, 'AI_EMBEDDING_MODEL', getattr(settings, 'OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small'))
CHAT_MODEL = getattr(settings, 'AI_CHAT_MODEL', getattr(settings, 'OPENAI_MODEL', 'gpt-4o-mini'))
VECTOR_STORE_PATH = getattr(settings, 'AI_VECTOR_STORE_PATH', getattr(settings, 'VECTOR_STORE_PATH', os.path.join(settings.BASE_DIR, 'data', 'ai-vector-store.json')))
BLOCKED_COUNTS_FILE = getattr(settings, 'AI_BLOCKED_COUNTS_FILE', os.path.join(settings.BASE_DIR, 'data', 'ai-blocked-counts.json'))

openai_client = None
last_openai_error: Optional[str] = None
if OpenAI and OPENAI_API_KEY:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        last_openai_error = str(e)
        openai_client = None


# ---- Vector Store (file-backed) ----
class VectorStore:
    """Simple JSON-backed vector store for products."""
    def __init__(self, path: str = VECTOR_STORE_PATH):
        self.path = path
        self._ensure_file()

    def _ensure_file(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, 'w', encoding='utf-8') as fh:
                json.dump({"chunks": []}, fh)

    def read(self) -> Dict[str, Any]:
        try:
            with open(self.path, 'r', encoding='utf-8') as fh:
                return json.load(fh)
        except Exception:
            return {"chunks": []}

    def write(self, data: Dict[str, Any]):
        try:
            self._ensure_file()
            with open(self.path, 'w', encoding='utf-8') as fh:
                json.dump(data, fh, indent=2)
        except Exception:
            pass

    def ingest_product(self, product_id: int, name: str, description: str, product_type: str, link: Optional[str], image_url: Optional[str], price: Optional[str]):
        """Index a product by embedding enriched, semantically rich content."""
        # Build rich text for better semantic matching
        price_text = f"Price: ${price}" if price and str(price).strip() not in ('', 'None', '0', '0.00') else "Price: contact for pricing"
        type_label = {
            'resource': 'resource book guide download',
            'consultancy': 'service program coaching webinar subscription',
            'ecommerce': 'product shop purchase item',
        }.get(product_type, product_type)
        content = (
            f"Product name: {name}. "
            f"Category: {type_label}. "
            f"{price_text}. "
            f"Description: {description or ''}."
        ).strip()
        embedding = embed_text(content)
        if not embedding:
            return {"error": "embedding failed"}

        store = self.read()
        store["chunks"] = [c for c in store["chunks"] if c.get("product_id") != product_id]
        store["chunks"].append({
            "id": f"product:{product_id}",
            "product_id": product_id,
            "name": name,
            "description": description,
            "product_type": product_type,
            "link": link,
            "image_url": image_url,
            "price": price,
            "content": content,
            "embedding": embedding,
        })
        self.write(store)
        return {"status": "ok", "product_id": product_id}

    def delete_product(self, product_id: int):
        """Remove product from vector store."""
        store = self.read()
        before = len(store["chunks"])
        store["chunks"] = [c for c in store["chunks"] if c.get("product_id") != product_id]
        self.write(store)
        return {"removed": before - len(store["chunks"])}

    def search(self, query_embedding: List[float], topK: int = 5, min_score: float = 0.35) -> List[Dict[str, Any]]:
        """Search vector store by cosine similarity."""
        store = self.read()
        scored = []
        for chunk in store["chunks"]:
            emb = chunk.get("embedding", [])
            if emb:
                score = cosine_similarity(query_embedding, emb)
                if score >= min_score:
                    scored.append({"score": score, **chunk})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:topK]


vector_store = VectorStore()


def load_active_ai_setting() -> Optional[AISetting]:
    try:
        return AISetting.get_active()
    except Exception:
        return None


def get_blocked_keywords() -> List[str]:
    try:
        return [keyword.word.lower() for keyword in BlockedKeyword.objects.all()]
    except Exception:
        return []


def get_active_pdf() -> Optional[KnowledgePDF]:
    try:
        return KnowledgePDF.objects.filter(is_active=True).order_by('-updated_at').first()
    except Exception:
        return None


def extract_pdf_text(pdf: KnowledgePDF) -> Optional[str]:
    if not pdf or PdfReader is None:
        return None

    try:
        reader = PdfReader(pdf.file.path)
        text_parts: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n\n".join(text_parts).strip()
    except Exception:
        return None


def _split_text_into_chunks(text: str, max_chars: int = 1200) -> List[str]:
    if not text:
        return []

    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n{2,}", text) if paragraph.strip()]
    chunks: List[str] = []
    for paragraph in paragraphs:
        while len(paragraph) > max_chars:
            chunk = paragraph[:max_chars]
            last_break = chunk.rfind(' ')
            if last_break > 0:
                chunk = paragraph[:last_break]
            chunks.append(chunk.strip())
            paragraph = paragraph[len(chunk):].strip()
        if paragraph:
            chunks.append(paragraph)

    return chunks


def search_pdf_knowledge(query: str, pdf: KnowledgePDF, topK: int = 3) -> List[Dict[str, Any]]:
    pdf_text = extract_pdf_text(pdf)
    if not pdf_text:
        return []

    query_embedding = embed_text(query)
    if not query_embedding:
        return []

    chunks = _split_text_into_chunks(pdf_text, max_chars=1200)
    scored: List[Dict[str, Any]] = []
    for chunk in chunks:
        embedding = embed_text(chunk)
        if not embedding:
            continue
        score = cosine_similarity(query_embedding, embedding)
        scored.append({
            'name': 'PDF context',
            'content': chunk,
            'score': score,
        })

    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored[:topK]


def build_ai_prompt(
    message: str,
    ai_setting: Optional[AISetting] = None,
    pdf_chunks: Optional[List[Dict[str, Any]]] = None,
    tone: str = 'helpful',
    response_length: str = 'medium',
) -> str:
    restriction_text = ai_setting.ai_restriction.strip() if ai_setting and ai_setting.ai_restriction else ''
    system_messages = ['You are a helpful AI assistant.']

    if restriction_text:
        system_messages.append(f'AI Restrictions: {restriction_text}')

    if response_length == 'short':
        system_messages.append('Keep the response concise and to the point.')
    elif response_length == 'long':
        system_messages.append('Provide a detailed and helpful response.')
    else:
        system_messages.append('Provide a clear, moderate-length response.')

    if pdf_chunks:
        system_messages.append(
            'Use the following PDF knowledge context to answer the user query. Only use the PDF information when it is relevant and helpful.'
        )
        for idx, chunk in enumerate(pdf_chunks, start=1):
            system_messages.append(f'Section {idx}: {chunk.get("content", "")}')

    system_messages.append('Do not include any unrelated information beyond the user request.')
    system_text = '\n\n'.join(system_messages)

    return f"{system_text}\n\nUser Query: {message}\n\nAnswer:"


def increment_query_counts(ai_setting: Optional[AISetting], success: bool = True) -> None:
    if ai_setting is None:
        return

    today = timezone.now().date()
    fields = []
    if ai_setting.today_date != today:
        ai_setting.today_date = today
        ai_setting.today_query_count = 0
        fields.extend(['today_date', 'today_query_count'])

    if success:
        ai_setting.today_query_count = (ai_setting.today_query_count or 0) + 1
        ai_setting.total_query_count = (ai_setting.total_query_count or 0) + 1
        fields.extend(['today_query_count', 'total_query_count'])

    if fields:
        ai_setting.save(update_fields=list(dict.fromkeys(fields)))


def save_query_log(message: str, response_text: str = '', is_blocked: bool = False) -> None:
    try:
        UserQueryLog.objects.create(
            query_text=message,
            response_text=response_text,
            is_blocked=is_blocked,
        )
    except Exception:
        pass


# ---- Embeddings ----
def embed_text(text: str) -> Optional[List[float]]:
    """Embed a single text string using OpenAI."""
    global last_openai_error
    last_openai_error = None
    if not openai_client:
        last_openai_error = "OpenAI client not configured"
        return None
    try:
        resp = openai_client.embeddings.create(input=[text], model=EMBEDDING_MODEL)
        return resp.data[0].embedding
    except Exception as e:
        last_openai_error = str(e)
        return None


def embed_texts(texts: List[str]) -> List[Optional[List[float]]]:
    """Embed multiple texts at once."""
    global last_openai_error
    last_openai_error = None
    if not openai_client:
        last_openai_error = "OpenAI client not configured"
        return [None] * len(texts)
    try:
        resp = openai_client.embeddings.create(input=texts, model=EMBEDDING_MODEL)
        return [item.embedding for item in resp.data]
    except Exception as e:
        last_openai_error = str(e)
        return [None] * len(texts)


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x ** 2 for x in a) ** 0.5
    mag_b = sum(x ** 2 for x in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _extract_search_terms(query: str) -> List[str]:
    tokens = re.findall(r"[a-zA-Z0-9]+", query.lower())
    stopwords = {
        'can', 'you', 'give', 'me', 'some', 'under', 'over', 'above', 'below', 'price',
        'buy', 'please', 'the', 'a', 'and', 'or', 'for', 'to', 'with', 'in', 'of',
        'product', 'products', 'recommend', 'suggest', 'show', 'find', 'need', 'want',
        'what', 'which', 'is', 'it', 'that', 'this', 'my', 'on', 'at', 'from', 'by',
        'if', 'do', 'does', 'are', 'be', 'your', 'would', 'like', 'please', 'thank'
    }
    return [t for t in tokens if t not in stopwords and not t.isdigit()]


# ---- RAG Prompt Building ----
def build_rag_prompt(query: str, context_chunks: List[Dict[str, Any]], tone: str = "helpful", response_length: str = "medium") -> str:
    """Build a RAG prompt from query and retrieved chunks."""
    context_text = "\n\n".join([
        f"Source: {chunk.get('name', 'Unknown')}\n{chunk.get('content', '')}"
        for chunk in context_chunks
    ])
    
    tone_hint = f"Respond in a {tone} tone." if tone else ""
    length_hint = ""
    if response_length == "short":
        length_hint = "Keep response brief (1-2 sentences)."
    elif response_length == "long":
        length_hint = "Provide a detailed response (3-5 sentences)."
    else:
        length_hint = "Provide a moderate response (2-3 sentences)."

    return f"""You are a helpful AI assistant. Use the provided context to answer the user's query.

{tone_hint}
{length_hint}

Context:
{context_text or "No context available."}

User Query: {query}

Answer:"""


# ---- RAG Query ----
def query_with_rag(
    query: str,
    topK: int = 5,
    min_score: float = 0.35,
    tone: str = "helpful",
    response_length: str = "medium",
    ai_setting: Optional[AISetting] = None,
    pdf_chunks: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Execute a RAG query: embed query, search, build prompt, call LLM."""
    global last_openai_error
    if not openai_client:
        return {"error": "OpenAI not configured"}

    query_embedding = embed_text(query)
    if not query_embedding:
        message = last_openai_error or "embedding failed"
        return {"error": f"embedding failed: {message}"}

    chunks = vector_store.search(query_embedding, topK=topK, min_score=min_score)
    prompt = build_ai_prompt(query, ai_setting=ai_setting, pdf_chunks=pdf_chunks, tone=tone, response_length=response_length)

    try:
        resp = openai_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=500,
        )
        answer = resp.choices[0].message.content
        source = 'pdf' if pdf_chunks else 'ai'
        return {
            "query": query,
            "answer": answer,
            "source": source,
            "sources": [{"name": c.get("name"), "score": round(c.get("score", 0), 3)} for c in (pdf_chunks or chunks)],
            "chunks_used": len(pdf_chunks or chunks),
        }
    except Exception as e:
        return {"error": str(e)}


# ---- Product Recommendations ----
def recommend_products(query: str, client_message: Optional[str] = None, topK: int = 5, candidates: Optional[List[Dict[str, Any]]] = None, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Recommend products by embedding and ranking."""
    context = client_message or query

    # if candidates provided, rank them locally
    if candidates:
        query_embedding = embed_text(context)
        if not query_embedding:
            return {"error": "embedding failed"}

        scored = []
        for cand in candidates:
            # apply filters
            if filters:
                if filters.get("product_type") and cand.get("product_type") != filters.get("product_type"):
                    continue
                if filters.get("is_published") is not None and cand.get("is_published") != filters.get("is_published"):
                    continue
                if filters.get("min_price"):
                    try:
                        price = float(cand.get("product_price", 0) or 0)
                        if filters.get("inclusive", True):
                            if price < filters.get("min_price"):
                                continue
                        else:
                            if price <= filters.get("min_price"):
                                continue
                    except Exception:
                        pass
                if filters.get("max_price"):
                    try:
                        price = float(cand.get("product_price", 0) or 0)
                        if filters.get("inclusive", True):
                            if price > filters.get("max_price"):
                                continue
                        else:
                            if price >= filters.get("max_price"):
                                continue
                    except Exception:
                        pass

            # embed candidate text
            text = f"{cand.get('name')} {cand.get('product_type')} {cand.get('description')}".strip()
            emb = embed_text(text)
            if emb:
                score = cosine_similarity(query_embedding, emb)
                scored.append({"item": cand, "score": score})

        scored.sort(key=lambda x: x["score"], reverse=True)
        results = scored[:topK if topK > 0 else 5]
        return {
            "query": query,
            "results": [
                {
                    "id": r["item"].get("id"),
                    "name": r["item"].get("name"),
                    "description": (r["item"].get("description", "") or "")[:300],
                    "score": round(r["score"], 3),
                    "image": r["item"].get("product_image"),
                    "url": r["item"].get("link"),
                }
                for r in results
            ]
        }

    # fallback: search vector store
    query_embedding = embed_text(context)
    if not query_embedding:
        return {"error": "embedding failed"}

    # Fetch more candidates to allow filtering (e.g. 2x topK)
    chunks = vector_store.search(query_embedding, topK=topK * 4 if topK > 0 else 20)
    if chunks:
        # Apply filters to chunks
        filtered_chunks = []
        for c in chunks:
            if filters:
                if filters.get("product_type") and c.get("product_type") != filters.get("product_type"):
                    continue
                if filters.get("min_price"):
                    try:
                        price = float(c.get("price", 0) or 0)
                        if filters.get("inclusive", True):
                            if price < filters.get("min_price"):
                                continue
                        else:
                            if price <= filters.get("min_price"):
                                continue
                    except Exception:
                        pass
                if filters.get("max_price"):
                    try:
                        price = float(c.get("price", 0) or 0)
                        if filters.get("inclusive", True):
                            if price > filters.get("max_price"):
                                continue
                        else:
                            if price >= filters.get("max_price"):
                                continue
                    except Exception:
                        pass
            filtered_chunks.append(c)

        chunks = filtered_chunks[:topK if topK > 0 else 5]
        if chunks:
            return {
                "query": query,
                "results": [
                    {
                        "id": c.get("product_id"),
                        "name": c.get("name"),
                        "description": c.get("description", "")[:300],
                        "score": round(c.get("score", 0), 3),
                        "image": c.get("image_url"),
                        "url": c.get("link"),
                        "price": str(c.get("price", "") or ""),
                    }
                    for c in chunks
                ]
            }

    # If the vector store is empty, fall back to a direct DB query for relevant products.
    Product = get_product_model()
    if Product is None:
        return {
            "query": query,
            "results": [],
        }

    qs = Product.objects.filter(is_published=True)
    if filters:
        if filters.get("min_price") is not None:
            qs = qs.filter(product_price__gte=filters["min_price"])
        if filters.get("max_price") is not None:
            qs = qs.filter(product_price__lte=filters["max_price"])

    terms = _extract_search_terms(query)
    if terms:
        q_filter = Q()
        for term in terms:
            q_filter |= Q(name__icontains=term) | Q(description__icontains=term) | Q(product_type__icontains=term)
        qs = qs.filter(q_filter)

    if not qs.exists() and filters:
        qs = Product.objects.filter(is_published=True)
        if filters.get("min_price") is not None:
            qs = qs.filter(product_price__gte=filters["min_price"])
        if filters.get("max_price") is not None:
            qs = qs.filter(product_price__lte=filters["max_price"])

    return {
        "query": query,
        "results": [
            {
                "id": p.id,
                "name": p.name,
                "description": (p.description or "")[:300],
                "score": None,
                "image": getattr(p.product_image, 'url', None),
                "url": p.link,
                "price": str(getattr(p, 'product_price', '') or ""),
            }
            for p in qs[:topK if topK > 0 else 5]
        ]
    }


# ---- Moderation / Blocked Keywords ----
def get_blocked_keywords() -> List[str]:
    """Get list of blocked keywords from settings."""
    kws = getattr(settings, 'AI_BLOCKED_KEYWORDS', None)
    if isinstance(kws, (list, tuple)):
        return [str(k).lower() for k in kws if k]
    return []


def _ensure_blocked_counts_file():
    d = os.path.dirname(BLOCKED_COUNTS_FILE)
    os.makedirs(d, exist_ok=True)
    if not os.path.exists(BLOCKED_COUNTS_FILE):
        with open(BLOCKED_COUNTS_FILE, 'w', encoding='utf-8') as fh:
            json.dump({}, fh)


def increment_blocked_counts(matched: List[str]):
    """Track count of blocked keyword matches."""
    try:
        _ensure_blocked_counts_file()
        with open(BLOCKED_COUNTS_FILE, 'r+', encoding='utf-8') as fh:
            data = json.load(fh)
            for k in matched:
                data[k] = data.get(k, 0) + 1
            fh.seek(0)
            json.dump(data, fh, indent=2)
            fh.truncate()
    except Exception:
        pass


def check_blocked(message: str) -> List[str]:
    """Check if message contains blocked keywords. Returns list of matched keywords."""
    if not message:
        return []
    kws = get_blocked_keywords()
    lower = message.lower()
    matched = []
    for kw in kws:
        if re.search(r"\b" + re.escape(kw) + r"\b", lower):
            if kw not in matched:
                matched.append(kw)
    return matched


def _parse_price_filters(message: str) -> Dict[str, Any]:
    """Parse price constraints like under 5000 or between 1000 and 3000."""
    filters: Dict[str, Any] = {}
    lower = message.lower()

    between_match = re.search(r'between\s+(\d+(?:\.\d+)?)\s+(?:and|-|to)\s+(\d+(?:\.\d+)?)', lower)
    if between_match:
        try:
            filters['min_price'] = float(between_match.group(1))
            filters['max_price'] = float(between_match.group(2))
            filters['inclusive'] = True
            return filters
        except ValueError:
            pass

    under_match = re.search(r'under\s+(\d+(?:\.\d+)?)', lower)
    if under_match:
        try:
            filters['max_price'] = float(under_match.group(1))
            filters['inclusive'] = False
        except ValueError:
            pass

    over_match = re.search(r'(?:over|above)\s+(\d+(?:\.\d+)?)', lower)
    if over_match:
        try:
            filters['min_price'] = float(over_match.group(1))
            filters['inclusive'] = False
        except ValueError:
            pass

    return filters


def _parse_top_k(message: str) -> Optional[int]:
    """Parse topK count requested in user message."""
    lower = message.lower()
    if re.search(r'\b(?:only\s+one|single|one|1)\s+products?\b', lower) or re.search(r'\b(?:only\s+one|single|just\s+one)\b', lower):
        return 1
    match = re.search(r'\b(\d+)\s+products?\b', lower)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    number_words = {
        'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
    }
    for word, num in number_words.items():
        if re.search(r'\b' + word + r'\s+products?\b', lower):
            return num
    return None


# ---- Intent Classification (LLM-powered) ----

_INTENT_CACHE: Dict[str, Dict[str, Any]] = {}

def _classify_query_intent(message: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """
    Use GPT to classify query intent and extract structured search parameters.
    Returns dict with keys:
      - intent: 'product_search' | 'general_question' | 'clarification_needed'
      - product_type_hint: 'resource' | 'consultancy' | 'ecommerce' | None
      - price_min: float | None
      - price_max: float | None
      - keywords: list of semantic search keywords
      - clarification_question: str (only when intent='clarification_needed')
      - enriched_query: str (rewritten query optimized for vector search)
    """
    if not openai_client:
        # Fallback: simple keyword-based detection
        lower = message.lower()
        indicators = ["assessment", "resource", "book", "webinar", "program", "subscribe",
                      "product", "buy", "price", "cost", "recommend", "suggest", "shop",
                      "need", "want", "looking", "find", "help", "church", "ministry",
                      "training", "curriculum", "download", "survey", "coaching"]
        is_product = any(tok in lower for tok in indicators)
        return {
            "intent": "product_search" if is_product else "general_question",
            "product_type_hint": None,
            "price_min": None,
            "price_max": None,
            "keywords": _extract_search_terms(message),
            "clarification_question": None,
            "enriched_query": message,
        }

    system_prompt = """You are an intelligent query classifier for a Black church resource marketplace.
The catalog includes:
- Assessments (church health surveys: assimilation, worship, leadership, youth, etc.) — type: resource, price ~$119
- Books & Research Reports (Black church studies, millennials & faith) — type: resource, price varies
- Digital Downloads (curriculum, templates, presentations) — type: resource
- Services & Programs (webinars, monthly subscriptions, coaching frameworks) — type: consultancy

Analyze the user's message and return a JSON object with these exact keys:
{
  "intent": "product_search" | "general_question" | "clarification_needed",
  "product_type_hint": "resource" | "consultancy" | null,
  "price_min": <number or null>,
  "price_max": <number or null>,
  "keywords": ["list", "of", "key", "concepts"],
  "clarification_question": "<question to ask user if unclear, else null>",
  "enriched_query": "<rewritten query optimized for semantic search>"
}

Rules:
- Use intent=product_search if the user wants to find, buy, or learn about any product/service.
- Use intent=clarification_needed ONLY if the query is extremely vague (e.g. just 'help' or 'something').
- Use intent=general_question for greetings, meta questions about the platform, etc.
- enriched_query should expand abbreviations and add relevant context for better vector matching.
- Return ONLY valid JSON. No explanation text."""

    messages = [{"role": "system", "content": system_prompt}]
    if conversation_history:
        for turn in conversation_history[-4:]:
            messages.append(turn)
    messages.append({"role": "user", "content": message})

    try:
        resp = openai_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
        parsed = json.loads(raw)
        # Merge price filters from regex as fallback
        regex_prices = _parse_price_filters(message)
        if regex_prices.get("min_price") and not parsed.get("price_min"):
            parsed["price_min"] = regex_prices["min_price"]
        if regex_prices.get("max_price") and not parsed.get("price_max"):
            parsed["price_max"] = regex_prices["max_price"]
        return parsed
    except Exception:
        # Fallback to simple detection
        lower = message.lower()
        indicators = ["assessment", "resource", "book", "webinar", "program", "church",
                      "ministry", "training", "curriculum", "download", "survey", "coaching",
                      "product", "buy", "price", "cost", "recommend", "suggest", "need", "want"]
        is_product = any(tok in lower for tok in indicators)
        return {
            "intent": "product_search" if is_product else "general_question",
            "product_type_hint": None,
            "price_min": None,
            "price_max": None,
            "keywords": _extract_search_terms(message),
            "clarification_question": None,
            "enriched_query": message,
        }


def _is_product_intent(message: str) -> bool:
    """Legacy fallback: infer if message intent is product-related (keyword-based)."""
    if not message:
        return False
    lower = message.lower()
    indicators = ["assessment", "resource", "book", "webinar", "program", "church",
                  "ministry", "training", "curriculum", "download", "survey", "coaching",
                  "product", "buy", "price", "cost", "recommend", "suggest", "shop",
                  "need", "want", "looking", "find"]
    return any(tok in lower for tok in indicators)


def handle_message(
    message: str,
    client_message: Optional[str] = None,
    candidates: Optional[List[Dict[str, Any]]] = None,
    filters: Optional[Dict[str, Any]] = None,
    topK: Optional[int] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Process a user message end-to-end with intelligent routing.

    Flow:
    1. Validate & moderate message.
    2. Classify intent using GPT (product_search / general_question / clarification_needed).
    3. If clarification_needed -> return a smart follow-up question.
    4. If product_search -> semantic vector search + optional LLM-generated summary.
    5. If general_question -> RAG with PDF knowledge base.
    6. Log query and update counters.

    Args:
        message: The user's message text.
        client_message: Optional override context for embedding.
        candidates: Optional pre-fetched product candidates.
        filters: Optional price/type filters.
        topK: Max products to return.
        conversation_history: List of {role, content} dicts for multi-turn context.
    """
    if not message or not str(message).strip():
        return {"error": "Message is required."}

    ai_setting = load_active_ai_setting()
    blocked_words = get_blocked_keywords()
    matched = [kw for kw in blocked_words if re.search(r"\b" + re.escape(kw) + r"\b", message.lower())]

    if matched:
        save_query_log(message, response_text="Blocked by keyword filter.", is_blocked=True)
        return {
            "blocked": True,
            "matched": matched,
            "count": len(matched),
            "answer": f"Your message contains restricted words: {', '.join(matched)}. Please rephrase.",
        }

    # Parse topK
    k = topK if isinstance(topK, int) and topK > 0 else (_parse_top_k(message) or 5)

    # ── LLM-powered intent classification ──
    intent_data = _classify_query_intent(message, conversation_history=conversation_history)
    intent = intent_data.get("intent", "general_question")
    enriched_query = intent_data.get("enriched_query") or message
    product_type_hint = intent_data.get("product_type_hint")

    # Build filters from intent + explicit overrides
    smart_filters: Dict[str, Any] = dict(filters or {})
    if intent_data.get("price_min") is not None:
        smart_filters.setdefault("min_price", intent_data["price_min"])
    if intent_data.get("price_max") is not None:
        smart_filters.setdefault("max_price", intent_data["price_max"])
    if product_type_hint:
        smart_filters.setdefault("product_type", product_type_hint)
    # Merge any regex-parsed price filters
    regex_filters = _parse_price_filters(message)
    for fk, fv in regex_filters.items():
        smart_filters.setdefault(fk, fv)

    result: Dict[str, Any] = {}

    # ── Route: needs clarification ──
    if intent == "clarification_needed" and not candidates:
        clarification_q = intent_data.get("clarification_question") or (
            "I'd love to help! Could you tell me a bit more about what you're looking for? "
            "For example, are you looking for a church assessment, a book, a training program, "
            "or something else? And do you have a budget in mind?"
        )
        save_query_log(message, response_text=clarification_q, is_blocked=False)
        increment_query_counts(ai_setting, success=True)
        return {
            "intent": "clarification_needed",
            "answer": clarification_q,
            "source": "clarification",
        }

    # ── Route: product search ──
    if candidates or intent == "product_search":
        try:
            result = recommend_products(
                query=enriched_query,
                client_message=client_message or enriched_query,
                topK=k,
                candidates=candidates,
                filters=smart_filters if smart_filters else None,
            )
        except Exception as e:
            result = {"error": f"recommendation failed: {str(e)}"}

        # If we got results, ask GPT to write a friendly summary
        if result.get("results") and openai_client:
            try:
                product_list = "\n".join([
                    f"- {r['name']} | ${r.get('price', 'N/A')} | {(r.get('description') or '')[:120]}"
                    for r in result["results"]
                ])
                history_ctx = ""
                if conversation_history:
                    history_ctx = "\n".join([
                        f"{t['role'].capitalize()}: {t['content']}"
                        for t in conversation_history[-4:]
                    ])

                summary_prompt = (
                    f"You are a helpful assistant for a Black church resource marketplace.\n"
                    f"{'Conversation so far:\n' + history_ctx + chr(10) if history_ctx else ''}"
                    f"The user asked: {message}\n\n"
                    f"Based on their request, here are the top matching products:\n{product_list}\n\n"
                    f"Write a warm, concise 2-3 sentence response introducing these results. "
                    f"Mention what they have in common with the user's need. "
                    f"Do not list every product — the UI will show them. End with an offer to refine."
                )
                summary_resp = openai_client.chat.completions.create(
                    model=CHAT_MODEL,
                    messages=[{"role": "user", "content": summary_prompt}],
                    temperature=0.5,
                    max_tokens=200,
                )
                result["answer"] = summary_resp.choices[0].message.content
            except Exception:
                pass  # summary is optional

        result["intent"] = "product_search"
        result["source"] = result.get("source", "vector_search")

    # ── Route: general question ──
    else:
        active_pdf = get_active_pdf()
        pdf_chunks = []
        if active_pdf:
            pdf_chunks = search_pdf_knowledge(message, active_pdf, topK=k)

        try:
            result = query_with_rag(
                message,
                topK=k,
                tone="helpful",
                response_length="medium",
                ai_setting=ai_setting,
                pdf_chunks=pdf_chunks if pdf_chunks else None,
            )
        except Exception as e:
            result = {"error": f"query failed: {str(e)}"}

        result["intent"] = "general_question"
        if active_pdf and pdf_chunks:
            result["source"] = "pdf_knowledge"
        elif result.get("source") is None:
            result["source"] = "direct_ai"

    if not result.get("error") and not result.get("blocked"):
        increment_query_counts(ai_setting, success=True)
        response_text = result.get("answer") or result.get("answer") or json.dumps(result)
        save_query_log(message, response_text=response_text, is_blocked=False)

    return result


# ---- Signal Handlers (auto-index products) ----
def _index_product_instance(instance):
    """Index a product from Django model instance."""
    try:
        vector_store.ingest_product(
            product_id=instance.id,
            name=instance.name,
            description=instance.description,
            product_type=instance.product_type,
            link=getattr(instance, 'link', None),
            image_url=getattr(instance, 'product_image', '') and instance.product_image.url,
            price=str(getattr(instance, 'product_price', None) or "")
        )
    except Exception:
        pass


def _remove_product_instance(instance):
    """Remove a product from vector store."""
    try:
        vector_store.delete_product(instance.id)
    except Exception:
        pass


def get_product_model():
    try:
        from admin_dashboard.models import Product
        return Product
    except Exception:
        pass

    return None


def _on_product_save(sender, instance, **kwargs):
    _index_product_instance(instance)


def _on_product_delete(sender, instance, **kwargs):
    _remove_product_instance(instance)


def register_signals():
    """Register Django signals to auto-index products on save/delete."""
    Product = get_product_model()
    if Product is None:
        return

    post_save.connect(_on_product_save, sender=Product, weak=False)
    post_delete.connect(_on_product_delete, sender=Product, weak=False)


# ---- Sync Products ----
def sync_all_products() -> Dict[str, int]:
    """Bulk-index all products from DB into vector store."""
    Product = get_product_model()
    if Product is None:
        return {"total": 0, "synced": 0}

    total = 0
    success = 0
    for p in Product.objects.all():
        total += 1
        try:
            _index_product_instance(p)
            success += 1
        except Exception:
            continue

    return {"total": total, "synced": success}


# ---- Convenience exports ----
__all__ = [
    'handle_message',
    'query_with_rag',
    'recommend_products',
    'check_blocked',
    'register_signals',
    'sync_all_products',
    'vector_store',
    'embed_text',
    'embed_texts',
]
