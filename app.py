# app.py
import os
import math
import asyncio
from datetime import datetime
from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash,
    make_response, jsonify, Response, stream_with_context
)
from beeai import Bee
from dotenv import load_dotenv
import pdfkit
import markdown as md
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import json
import zipfile
import io
import time
from queue import Queue
import threading

# Load .env (FLASK_SECRET_KEY)
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev_secret')

# initialize local embedder
embed_model = SentenceTransformer('all-MiniLM-L6-v2')
embed_dim   = embed_model.get_sentence_embedding_dimension()
vector_index = None
vector_meta  = []

# default threshold if none provided (50% relevance)
DEFAULT_THRESHOLD = 0.5

# Global progress tracking for bulk export
export_progress = {}

# Inject current year into all templates
@app.context_processor
def inject_now():
    return {'current_year': datetime.utcnow().year}

# Markdown filter
@app.template_filter('markdown')
def markdown_to_html(text):
    """Convert Markdown to HTML with fenced code and highlighting."""
    return md.markdown(
        text or '',
        extensions=['fenced_code', 'codehilite']
    )

# Bee client factory (returns None if not logged in)
def get_bee():
    api_key = session.get('api_key')
    return Bee(api_key) if api_key else None

def build_local_index():
    """(Re)builds a FAISS index over every conversation, fact, and todo."""
    global vector_index, vector_meta

    bee       = get_bee()
    items     = []
    convo_ids = []
    page      = 1
    api_limit = 100

    # 1) Gather all conversation IDs
    while True:
        payload = asyncio.run(bee.get_conversations('me', page=page, limit=api_limit))
        convos  = payload.get('conversations', [])
        if not convos:
            break
        convo_ids.extend(c['id'] for c in convos)
        page += 1

    # 2) Index each conversation's full text as one item
    for cid in convo_ids:
        full = asyncio.run(bee.get_conversation('me', cid))
        msgs = full.get('messages', [])
        if not msgs:
            continue
        text = ' '.join(m.get('text', '') for m in msgs)
        items.append({
            'type': 'conversation',
            'id':   cid,
            'text': text,
            'url':  url_for('conversation_detail', conversation_id=cid)
        })

    # 3) Index all facts
    page = 1
    while True:
        payload = asyncio.run(bee.get_facts('me', page=page, limit=1000))
        facts   = payload.get('facts', [])
        if not facts:
            break
        for f in facts:
            items.append({
                'type': 'fact',
                'id':   f['id'],
                'text': f.get('text',''),
                'url':  url_for('edit_fact', fact_id=f['id'])
            })
        page += 1

    # 4) Index all todos
    page = 1
    while True:
        payload = asyncio.run(bee.get_todos('me', page=page, limit=1000))
        todos   = payload.get('todos', [])
        if not todos:
            break
        for t in todos:
            items.append({
                'type': 'todo',
                'id':   t['id'],
                'text': t.get('text',''),
                'url':  url_for('edit_todo', todo_id=t['id'])
            })
        page += 1

    # 5) Embed & normalize
    texts      = [it['text'] for it in items]
    embeddings = embed_model.encode(texts, convert_to_numpy=True)
    norms      = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / norms

    # 6) Build FAISS index
    vector_index = faiss.IndexFlatIP(embed_dim)
    vector_index.add(embeddings)
    vector_meta  = items

# ——————————————————————————————————————————————————————————————
#  Auth / Dashboard routes
# ——————————————————————————————————————————————————————————————

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        session['api_key'] = request.form['api_key'].strip()
        bee = get_bee()
        try:
            payload = asyncio.run(bee.get_conversations('me', page=1, limit=1))
            if 'conversations' in payload:
                return redirect(url_for('dashboard'))
        except Exception:
            pass
        session.pop('api_key', None)
        return render_template('index.html', invalid_key=True)
    return render_template('index.html', invalid_key=False)

@app.route('/dashboard')
def dashboard():
    if not session.get('api_key'):
        return redirect(url_for('index'))
    return render_template('dashboard.html')


# ——————————————————————————————————————————————————————————————
#  Conversations
# ——————————————————————————————————————————————————————————————

@app.route('/conversations')
def conversations():
    bee = get_bee()
    if not bee:
        return redirect(url_for('index'))

    # UI page & page size
    ui_page = request.args.get('page', default=1, type=int)
    page_size = 10

    # 1) Fetch _all_ convos from Bee API via its own pagination
    all_convos = []
    api_page = 1
    api_limit = 100  # or whatever max the API allows per request
    while True:
        payload = asyncio.run(bee.get_conversations('me', page=api_page, limit=api_limit))
        batch = payload.get('conversations', [])
        if not batch:
            break
        all_convos.extend(batch)
        api_page += 1

    # 2) Compute UI pagination
    total = len(all_convos)
    total_pages = math.ceil(total / page_size)
    start = (ui_page - 1) * page_size
    end   = start + page_size
    page_convos = all_convos[start:end]

    return render_template(
        'conversations.html',
        conversations=page_convos,
        page=ui_page,
        total_pages=total_pages
    )

@app.route('/conversation/<int:conversation_id>')
def conversation_detail(conversation_id):
    bee = get_bee()
    if not bee:
        return redirect(url_for('index'))

    convo = asyncio.run(bee.get_conversation('me', conversation_id))
    return render_template('conversation_detail.html', convo=convo)

@app.route('/conversations/<int:conv_id>/end', methods=['POST'])
def end_conversation(conv_id):
    bee = get_bee()
    if not bee:
        return redirect(url_for('index'))

    asyncio.run(bee.end_conversation('me', conv_id))
    flash('Conversation ended successfully', 'success')
    return redirect(url_for('conversations'))

@app.route('/conversations/<int:conv_id>/retry', methods=['POST'])
def retry_conversation(conv_id):
    bee = get_bee()
    if not bee:
        return redirect(url_for('index'))

    asyncio.run(bee.retry_conversation('me', conv_id))
    flash('Conversation retried', 'info')
    return redirect(url_for('conversations'))

@app.route('/conversations/<int:conv_id>/delete', methods=['POST'])
def delete_conversation(conv_id):
    bee = get_bee()
    if not bee:
        return redirect(url_for('index'))

    asyncio.run(bee.delete_conversation('me', conv_id))
    flash('Conversation deleted', 'warning')
    return redirect(url_for('conversations'))

@app.route('/conversation/<int:conversation_id>/pdf')
def conversation_pdf(conversation_id):
    """Render a PDF of the full conversation."""
    bee = get_bee()
    if not bee:
        return redirect(url_for('index'))

    # fetch the same convo object as in the detail view
    convo = asyncio.run(bee.get_conversation('me', conversation_id))

    # render our PDF‐optimized template to HTML
    html = render_template('conversation_pdf.html', convo=convo)

    # convert to PDF
    pdf = pdfkit.from_string(html, False, options={'enable-local-file-access': None})

    # return as attachment
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = \
        f'attachment; filename=conversation_{conversation_id}.pdf'
    return response

# ——————————————————————————————————————————————————————————————
#  Bulk Export Feature
# ——————————————————————————————————————————————————————————————

def generate_conversation_pdf(bee, conversation_id):
    """Generate PDF for a single conversation."""
    convo = asyncio.run(bee.get_conversation('me', conversation_id))
    html = render_template('conversation_pdf.html', convo=convo)
    pdf = pdfkit.from_string(html, False, options={'enable-local-file-access': None})
    return pdf, convo

@app.route('/conversations/bulk-export/start', methods=['POST'])
def start_bulk_export():
    """Start the bulk export process."""
    bee = get_bee()
    if not bee:
        return jsonify({'error': 'Unauthorized'}), 401
    
    export_id = str(int(time.time()))
    export_progress[export_id] = {
        'status': 'fetching',
        'current': 0,
        'total': 0,
        'message': 'Fetching conversations...'
    }
    
    # Start the export in a background thread
    thread = threading.Thread(target=process_bulk_export, args=(bee, export_id))
    thread.daemon = True
    thread.start()
    
    return jsonify({'export_id': export_id})

def process_bulk_export(bee, export_id):
    """Process the bulk export in a background thread."""
    try:
        # Fetch all conversations
        all_convos = []
        api_page = 1
        api_limit = 100
        
        while True:
            payload = asyncio.run(bee.get_conversations('me', page=api_page, limit=api_limit))
            batch = payload.get('conversations', [])
            if not batch:
                break
            all_convos.extend(batch)
            api_page += 1
        
        total = len(all_convos)
        export_progress[export_id]['total'] = total
        export_progress[export_id]['status'] = 'processing'
        
        # Create in-memory zip file
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for i, conv in enumerate(all_convos):
                try:
                    export_progress[export_id]['current'] = i + 1
                    export_progress[export_id]['message'] = f'Processing conversation {i + 1} of {total}'
                    
                    # Generate PDF for this conversation
                    pdf_data, convo_detail = generate_conversation_pdf(bee, conv['id'])
                    
                    # Create a safe filename
                    title = convo_detail['conversation'].get('short_summary', f'Conversation {conv["id"]}')
                    # Clean the title for use as filename
                    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()[:50]
                    filename = f'conversation_{conv["id"]}_{safe_title}.pdf'
                    
                    # Add PDF to zip
                    zip_file.writestr(filename, pdf_data)
                    
                except Exception as e:
                    print(f"Error processing conversation {conv['id']}: {str(e)}")
                    # Continue with other conversations even if one fails
        
        # Store the zip buffer for download
        export_progress[export_id]['status'] = 'complete'
        export_progress[export_id]['message'] = 'Export complete!'
        export_progress[export_id]['data'] = zip_buffer.getvalue()
        
    except Exception as e:
        export_progress[export_id]['status'] = 'error'
        export_progress[export_id]['message'] = f'Export failed: {str(e)}'

@app.route('/conversations/bulk-export/progress/<export_id>')
def bulk_export_progress(export_id):
    """Get the progress of a bulk export."""
    if export_id not in export_progress:
        return jsonify({'error': 'Export not found'}), 404
    
    progress = export_progress[export_id]
    return jsonify({
        'status': progress['status'],
        'current': progress['current'],
        'total': progress['total'],
        'message': progress['message']
    })

@app.route('/conversations/bulk-export/download/<export_id>')
def download_bulk_export(export_id):
    """Download the completed bulk export."""
    if export_id not in export_progress:
        return jsonify({'error': 'Export not found'}), 404
    
    progress = export_progress[export_id]
    if progress['status'] != 'complete':
        return jsonify({'error': 'Export not complete'}), 400
    
    # Clean up the progress entry after sending
    zip_data = progress['data']
    del export_progress[export_id]
    
    # Return the zip file
    response = make_response(zip_data)
    response.headers['Content-Type'] = 'application/zip'
    response.headers['Content-Disposition'] = f'attachment; filename=bee_conversations_export_{export_id}.zip'
    return response

# ——————————————————————————————————————————————————————————————
#  Facts
# ——————————————————————————————————————————————————————————————

@app.route('/facts')
def facts():
    bee = get_bee()
    if not bee:
        return redirect(url_for('index'))

    # pull filters off the query‐string
    confirmed_q = request.args.get('confirmed')
    page       = request.args.get('page',  default=1,   type=int)
    limit      = request.args.get('limit', default=1000, type=int)

    # build the kwargs for get_facts
    bee_kwargs = {
        'page':  page,
        'limit': limit
    }
    if confirmed_q is not None:
        bee_kwargs['confirmed'] = confirmed_q.lower() in ('true','1','yes')

    # this now lines up with get_facts(self, userId, confirmed=None, page=None, limit=None)
    payload = asyncio.run(bee.get_facts('me', **bee_kwargs))
    facts   = payload.get('facts', [])

    return render_template('facts.html', facts=facts)

@app.route('/facts/new', methods=['GET', 'POST'])
def new_fact():
    bee = get_bee()
    if not bee:
        return redirect(url_for('index'))

    if request.method == 'POST':
        payload = {
            'text': request.form['text'],
            'confirmed': 'confirmed' in request.form
        }
        asyncio.run(bee.create_fact('me', payload))
        flash('Fact created', 'success')
        return redirect(url_for('facts'))

    return render_template('fact_form.html', action='Create', fact={})

@app.route('/facts/<int:fact_id>/edit', methods=['GET', 'POST'])
def edit_fact(fact_id):
    bee = get_bee()
    if not bee:
        return redirect(url_for('index'))

    if request.method == 'POST':
        payload = {
            'text': request.form['text'],
            'confirmed': 'confirmed' in request.form
        }
        asyncio.run(bee.update_fact('me', fact_id, payload))
        flash('Fact updated', 'success')
        return redirect(url_for('facts'))

    data = asyncio.run(bee.get_fact('me', fact_id))
    return render_template('fact_form.html', action='Edit', fact=data)

@app.route('/facts/<int:fact_id>/delete', methods=['POST'])
def delete_fact(fact_id):
    bee = get_bee()
    if not bee:
        return redirect(url_for('index'))

    asyncio.run(bee.delete_fact('me', fact_id))
    flash('Fact deleted', 'warning')
    return redirect(url_for('facts'))

# ——————————————————————————————————————————————————————————————
#  To‑Dos
# ——————————————————————————————————————————————————————————————

@app.route('/todos')
def todos():
    bee = get_bee()
    if not bee:
        return redirect(url_for('index'))

    # Fetch every page of to‑dos
    all_todos = []
    api_page  = 1
    api_limit = 100  # or whatever max the API allows

    while True:
        payload = asyncio.run(bee.get_todos('me', page=api_page, limit=api_limit))
        batch   = payload.get('todos', [])
        if not batch:
            break
        all_todos.extend(batch)
        api_page += 1

    # Split into pending vs completed
    pending   = [t for t in all_todos if not t.get('completed')]
    completed = [t for t in all_todos if     t.get('completed')]

    return render_template(
        'todos.html',
        pending=pending,
        completed=completed
    )

@app.route('/todos/new', methods=['GET', 'POST'])
def new_todo():
    bee = get_bee()
    if not bee:
        return redirect(url_for('index'))

    if request.method == 'POST':
        payload = {
            'text': request.form['text'],
            'completed': 'completed' in request.form
        }
        asyncio.run(bee.create_todo('me', payload))
        flash('To‑Do created', 'success')
        return redirect(url_for('todos'))

    return render_template('todo_form.html', action='Create', todo={})

@app.route('/todos/<int:todo_id>/edit', methods=['GET', 'POST'])
def edit_todo(todo_id):
    bee = get_bee()
    if not bee:
        return redirect(url_for('index'))

    if request.method == 'POST':
        payload = {
            'text': request.form['text'],
            'completed': 'completed' in request.form
        }
        asyncio.run(bee.update_todo('me', todo_id, payload))
        flash('To‑Do updated', 'success')
        return redirect(url_for('todos'))

    data = asyncio.run(bee.get_todo('me', todo_id))
    return render_template('todo_form.html', action='Edit', todo=data)

@app.route('/todos/<int:todo_id>/delete', methods=['POST'])
def delete_todo(todo_id):
    bee = get_bee()
    if not bee:
        return redirect(url_for('index'))

    asyncio.run(bee.delete_todo('me', todo_id))
    flash('To‑Do deleted', 'warning')
    return redirect(url_for('todos'))

# ——————————————————————————————————————————————————————————————
#  Locations
# ——————————————————————————————————————————————————————————————

@app.route('/locations')
def locations():
    bee = get_bee()
    if not bee:
        return redirect(url_for('index'))

    # UI pagination params
    ui_page   = request.args.get('page', default=1, type=int)
    page_size = 10

    # 1) Fetch _all_ locations from Bee via its own pagination
    all_locs  = []
    api_page  = 1
    api_limit = 100
    while True:
        payload = asyncio.run(
            bee.get_locations('me', page=api_page, limit=api_limit)
        )
        batch = payload.get('locations', [])
        if not batch:
            break
        all_locs.extend(batch)
        api_page += 1

    # 2) Slice out just the 10 we need for this UI page
    total       = len(all_locs)
    total_pages = math.ceil(total / page_size)
    start       = (ui_page - 1) * page_size
    end         = start + page_size
    page_locs   = all_locs[start:end]

    return render_template(
        'locations.html',
        locations   = page_locs,
        page        = ui_page,
        total_pages = total_pages
    )

@app.route('/api/search')
def api_search():
    if not session.get('api_key'):
        return jsonify({'error': 'Unauthorized'}), 401

    query = request.args.get('q', '').strip()
    try:
        cutoff = float(request.args.get('t', 50)) / 100.0
    except ValueError:
        cutoff = DEFAULT_THRESHOLD

    results = []
    if query:
        # Rebuild your FAISS index (convos, facts, todos)
        build_local_index()

        # 1) Vector search (skip sims < cutoff)
        q_emb = embed_model.encode([query], convert_to_numpy=True)
        q_emb = q_emb / np.linalg.norm(q_emb, axis=1, keepdims=True)
        sims, idxs = vector_index.search(q_emb, vector_index.ntotal)
        for sim, idx in zip(sims[0], idxs[0]):
            if sim < cutoff:
                continue
            entry = vector_meta[idx].copy()
            entry['score'] = float(sim)
            results.append(entry)

        # 2) Substring fallback across everything already in the index
        for item in vector_meta:
            if query.lower() in item['text'].lower() \
               and not any(r['url'] == item['url'] for r in results):
                hit = item.copy()
                hit['score'] = 1.0
                results.append(hit)

        # 3) SUMMARY‑LEVEL fallback: scan each conversation's summary text
        api_page = 1
        api_limit = 100
        while True:
            payload = asyncio.run(
                get_bee().get_conversations('me', page=api_page, limit=api_limit)
            )
            convos = payload.get('conversations', [])
            if not convos:
                break

            for c in convos:
                summary = c.get('summary', '') or ''
                if query.lower() in summary.lower():
                    url = url_for('conversation_detail', conversation_id=c['id'])
                    if not any(r['url'] == url for r in results):
                        # take first line / 200 chars of the summary
                        snippet = summary.strip().replace('\n', ' ')
                        snippet = (snippet[:200] + '…') if len(snippet) > 200 else snippet
                        results.append({
                            'type':  'conversation',
                            'id':     c['id'],
                            'text':   snippet,
                            'url':    url,
                            'score':  1.0
                        })
            api_page += 1

    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')