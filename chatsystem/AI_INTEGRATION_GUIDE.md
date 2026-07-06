# AI Integration Guide for `admin_dashboard/ai.py`

## ✅ What's Included (Everything in ONE file)

- **Embeddings**: Direct OpenAI API (text-embedding-3-small)
- **Vector Store**: File-backed JSON at `data/ai-vector-store.json`
- **RAG Engine**: Query embedding → semantic search → LLM response with sources
- **Product Recommendations**: Semantic ranking with price/type/publish filters
- **Moderation**: Blocked keyword detection + frequency counting
- **Auto-Indexing**: Django signals (post_save/post_delete on Product model)
- **Prompts**: Dynamic prompt building with customizable tone/length
- **Message Router**: `handle_message()` - main entry point (moderation → intent → AI)

---

## 🚀 Quick Setup (3 Steps)

### 1. **Add to Django Settings** (`settings.py`)
```python
# OpenAI Config
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')  # Set in .env or production env vars
AI_EMBEDDING_MODEL = 'text-embedding-3-small'  # (optional)
AI_CHAT_MODEL = 'gpt-4o-mini'  # (optional)

# Blocked keywords (optional)
AI_BLOCKED_KEYWORDS = ['spam', 'abuse', 'profanity']  # customize as needed

# Storage paths (optional - defaults to data/ folder)
AI_VECTOR_STORE_PATH = os.path.join(BASE_DIR, 'data', 'ai-vector-store.json')
AI_BLOCKED_COUNTS_FILE = os.path.join(BASE_DIR, 'data', 'ai-blocked-counts.json')
```

### 2. **Ensure `apps.py` Calls Signal Registration**
```python
# admin_dashboard/apps.py
from django.apps import AppConfig

class AdminDashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'admin_dashboard'
 
    def ready(self):
        try:
            from . import ai as ai_module
            ai_module.register_signals()  # Auto-index products on save/delete
        except Exception:
            pass
```

### 3. **Update `requirements.txt`**
```
openai>=1.0.0
```
Then: `pip install -r requirements.txt`

---

## 💻 Usage in Views/APIs

### **Option A: Simple Message Handling** (Recommended - uses moderation → intent → AI)
```python
from admin_dashboard.ai import handle_message

def chat_view(request):
    user_query = request.data.get('message')
    
    # Auto-routes: moderation → product intent or RAG
    result = handle_message(user_query)
    
    if result.get('blocked'):
        return Response({
            'error': result['reply'],
            'matched_keywords': result['matched']
        }, status=400)
    
    # Product recommendation
    if 'results' in result:
        return Response({'products': result['results']})
    
    # RAG response
    if 'answer' in result:
        return Response({
            'answer': result['answer'],
            'sources': result['sources']
        })
    
    return Response(result)
```

### **Option B: Recommend Products** (Direct - with candidates/filters)
```python
from admin_dashboard.ai import recommend_products
from admin_dashboard.models import Product

def get_recommendations(request):
    query = request.data.get('query')
    
    # Get all published products
    candidates = Product.objects.filter(is_published=True).values()
    
    result = recommend_products(
        query=query,
        candidates=list(candidates),
        topK=5,
        filters={'is_published': True}
    )
    
    return Response(result)
```

### **Option C: RAG Query** (Direct - search vector store + LLM)
```python
from admin_dashboard.ai import query_with_rag

def general_query(request):
    query = request.data.get('query')
    
    result = query_with_rag(
        query=query,
        topK=5,
        tone='helpful',
        response_length='medium'
    )
    
    return Response(result)
```

### **Option D: Check Moderation Only**
```python
from admin_dashboard.ai import check_blocked, increment_blocked_counts

def moderate_message(request):
    message = request.data.get('message')
    
    matched = check_blocked(message)
    if matched:
        increment_blocked_counts(matched)
        return Response({'blocked': True, 'matched': matched}, status=400)
    
    return Response({'blocked': False})
```

---

## 🔄 Bulk Sync (CLI or Management Command)

### **Sync All Products into Vector Store**
```python
from admin_dashboard.ai import sync_all_products

result = sync_all_products()
# Returns: {'total': 10, 'synced': 9}
```

### **Via Django Management Command**
```bash
python manage.py sync_products_to_ai
```

---

## 📊 Main Entry Points

| Function | Purpose | Input | Output |
|----------|---------|-------|--------|
| `handle_message(msg, ...)` | **Main router** - moderation → intent → AI | string | dict with `blocked`/`answer`/`results`/`error` |
| `recommend_products(query, ...)` | Rank products by semantic similarity | string + candidates | dict with `results` (scored products) |
| `query_with_rag(query, ...)` | RAG: embed → search → LLM | string | dict with `answer` + `sources` |
| `check_blocked(msg)` | Detect restricted words | string | list of matched keywords |
| `register_signals()` | Register Django post_save/delete hooks | — | auto-indexes products |
| `sync_all_products()` | Bulk-index all DB products | — | dict with `total`/`synced` count |
| `embed_text(text)` | Embed single text | string | list (vector) or None |
| `embed_texts(texts)` | Embed batch | list[string] | list[list] (vectors) |

---

## 🔧 Configuration Reference

| Setting | Default | Purpose |
|---------|---------|---------|
| `OPENAI_API_KEY` | env var | **Required** - your OpenAI API key |
| `AI_EMBEDDING_MODEL` | text-embedding-3-small | Embedding model |
| `AI_CHAT_MODEL` | gpt-4o-mini | LLM for RAG responses |
| `AI_BLOCKED_KEYWORDS` | [] | List of restricted words |
| `AI_VECTOR_STORE_PATH` | `data/ai-vector-store.json` | Where to store product vectors |
| `AI_BLOCKED_COUNTS_FILE` | `data/ai-blocked-counts.json` | Track blocked word violations |

---

## ⚠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| **"OpenAI not configured"** | Set `OPENAI_API_KEY` env var and install `openai>=1.0.0` |
| **Embeddings slow** | Normal (first sync slower). Products auto-index on save after. |
| **Vector store empty** | Run `sync_all_products()` or create new products (auto-indexes via signals) |
| **Moderation not working** | Add `AI_BLOCKED_KEYWORDS` to `settings.py` |

---

## 📦 File Structure
```
revri-remote/
├── admin_dashboard/
│   ├── ai.py                  ← Drop this file here
│   ├── apps.py                ← Ensure ready() calls register_signals()
│   ├── models.py              ← Product model
│   └── views.py               ← Import and use ai functions
├── requirements.txt           ← Add: openai>=1.0.0
└── manage.py
```

---

## ✅ Final Checklist Before Deployment

- [ ] `OPENAI_API_KEY` set in environment
- [ ] `openai` package installed (`pip install -r requirements.txt`)
- [ ] `apps.py` calls `ai.register_signals()` in `ready()`
- [ ] Optional: Add `AI_BLOCKED_KEYWORDS` to settings if needed
- [ ] Optional: Run `python manage.py sync_products_to_ai` to index existing products
- [ ] Test with simple API call: `handle_message("recommend sunglasses")`

---

## 🎯 No External Dependencies!
This module:
- ✅ Uses **local JSON** for vector store (no database needed)
- ✅ Calls **OpenAI directly** (no backend service needed)
- ✅ **Auto-indexes** via Django signals
- ✅ **Self-contained** in ONE file
- ✅ **Zero micro-service complexity**

Just drop `ai.py` in `admin_dashboard/` and you're done! 🚀
