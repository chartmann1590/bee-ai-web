# Bee AI Web

A Flask-based web interface for [Bee AI](https://bee.computer), enabling you to:

- Log in using your Bee API key
- Browse, paginate, end/retry/delete conversations
- Export conversations as PDFs
- Manage "Facts" (CRUD operations and filtering)
- Manage "To-Dos" (CRUD operations)
- Browse paginated "Locations"

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

- **Python 3.10+**
- **pip** or **pipenv**
- **wkhtmltopdf** (for PDF export)

### Install System Dependencies

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
# Clone the repository
git clone https://github.com/chartmann1590/bee-ai-web.git
cd bee-ai-web

# Using pipenv
pipenv install
pipenv shell

# Or using venv
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

---

## Configuration

Create a `.env` file in the project root:

```dotenv
# Secret key for signing Flask session cookies
FLASK_SECRET_KEY=your_random_secret_here
```

> **Warning:** Without setting `FLASK_SECRET_KEY`, the app defaults to `dev_secret`, which is **insecure** for production.

---

## Running the App

Activate your virtual environment, then:

```bash
export FLASK_APP=app.py
export FLASK_ENV=development  # Optional for debug mode and auto-reload
flask run --host=0.0.0.0 --port=5000
```

Access the app at [http://localhost:5000](http://localhost:5000).

---

## Usage

1. **Login:** Paste your Bee API key on the home page and submit.
2. **Dashboard:** Navigate to various sections.
3. **Conversations:**
   - Lists conversations with pagination.
   - End, retry, or delete conversations.
   - Export conversations to PDF.
4. **Facts:**
   - View, filter (by "confirmed"), and paginate facts.
   - Perform CRUD operations.
5. **To-Dos:**
   - View all tasks.
   - Perform CRUD operations.
6. **Locations:**
   - Paginated location browsing.

---

## Getting Your Bee API Key

1. Visit the [Bee Developer Portal](https://developer.bee.computer/keys).
2. Sign in or create an account.
3. Under **API Keys**, click **Create new key**.
4. Copy and paste the key into the app login form.

---

## Project Structure

```
.
├── app.py
├── requirements.txt
├── .env.example        # Template for your .env file
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

- Sessions store API keys securely in signed cookies; they are not saved to disk.
- PDF export functionality relies on `wkhtmltopdf` and `pdfkit`.
- For production use, set `FLASK_ENV=production` and deploy with a WSGI server such as Gunicorn.

---

## License

MIT © Charles Hartmann

