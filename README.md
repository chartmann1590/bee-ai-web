```markdown
# bee‑ai‑web

A Flask‑based web interface for Bee AI (https://bee.computer) that lets you

- login with your Bee API key  
- browse, paginate, end/retry/delete conversations  
- export any conversation as a PDF  
- manage “Facts” (CRUD + filter)  
- manage “To‑Dos” (CRUD)  
- browse paginated “Locations”

---

## Table of Contents

- [Prerequisites](#prerequisites)  
- [Installation](#installation)  
- [Configuration](#configuration)  
- [Running the App](#running-the-app)  
- [Usage](#usage)  
- [Getting Your Bee API Key](#getting-your-bee-api-key)  
- [Project Structure](#project-structure)  
- [Notes](#notes)  
- [License](#license)  

---

## Prerequisites

- **Python 3.10+**  
- **pip** (or **pipenv**)  
- **wkhtmltopdf** (for PDF export)

### Install system dependencies

<details>
<summary>Ubuntu / Debian</summary>

```bash
sudo apt-get update
sudo apt-get install -y wkhtmltopdf
```

</details>

<details>
<summary>macOS (Homebrew)</summary>

```bash
brew install wkhtmltopdf
```

</details>

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/chartmann1590/bee-ai-web.git
cd bee-ai-web

# 2a. Using pipenv
pipenv install
pipenv shell

# 2b. Or using venv
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

---

## Configuration

Create a file named `.env` in the project root:

```dotenv
# Secret for signing Flask session cookies
FLASK_SECRET_KEY=your_random_secret_here
```

> **Warning:** If you don’t set `FLASK_SECRET_KEY`, the app falls back to `dev_secret`, which is **not** secure for production.

---

## Running the App

With your virtual environment activated:

```bash
export FLASK_APP=app.py
export FLASK_ENV=development    # optional: enables debug + auto‑reload
flask run --host=0.0.0.0 --port=5000
```

Then open your browser to `http://localhost:5000`.

---

## Usage

1. **Login**  
   On the home page, paste your Bee API key and submit.  

2. **Dashboard**  
   From here you can navigate to all sections.

3. **Conversations**  
   - Lists 10 per page (UI pagination).  
   - Buttons to End / Retry / Delete each conversation.  
   - “Export PDF” link to download the full conversation as a PDF.  

4. **Facts**  
   - View, filter by “confirmed”, and paginate (via URL params).  
   - Create, Edit, and Delete.  

5. **To‑Dos**  
   - View all to‑dos.  
   - Create, Edit, and Delete.  

6. **Locations**  
   - Lists 10 per page (UI pagination).  

---

## Getting Your Bee API Key

1. Visit the **Bee developer portal** at  
   https://developer.bee.computer/keys  
2. Sign in (or sign up).  
3. Under **API Keys**, click **Create new key**.  
4. Copy the key and paste it into the login form.

---

## Project Structure

```
.
├── app.py
├── requirements.txt
├── .env.example        ← Copy to “.env” and fill in
├── .gitignore
├── templates/
│   ├── index.html
│   ├── dashboard.html
│   ├── conversations.html
│   ├── conversation_detail.html
│   ├── conversation_pdf.html
│   ├── facts.html
│   ├── fact_form.html
│   ├── todos.html
│   ├── todo_form.html
│   └── locations.html
└── static/
    ├── css/
    └── js/
```

---

## Notes

- **Sessions** store your API key in a signed cookie — it’s never written to disk.  
- **PDF export** relies on `wkhtmltopdf` + `pdfkit`.  
- For production, switch `FLASK_ENV=production` and run under a WSGI server (e.g. Gunicorn).

---

## License

MIT © Charles Hartmann
```