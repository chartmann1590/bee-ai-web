#!/usr/bin/env python3
"""
Bee AI Conversation Batch Export Tool
Exports all conversations from Bee AI as individual PDF files.
"""

import os
import sys
import subprocess
import asyncio
import time
from datetime import datetime
from pathlib import Path

def check_python_version():
    """Ensure Python 3.10+ is being used."""
    if sys.version_info < (3, 10):
        print("Error: Python 3.10 or higher is required.")
        print(f"Current version: {sys.version}")
        sys.exit(1)

def setup_virtual_environment():
    """Create and activate a virtual environment if it doesn't exist."""
    venv_dir = Path("export_venv")
    
    if not venv_dir.exists():
        print("Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        print("✓ Virtual environment created")
    else:
        print("✓ Virtual environment already exists")
    
    # Get the path to the Python executable in the virtual environment
    if sys.platform == "win32":
        python_path = venv_dir / "Scripts" / "python.exe"
        pip_path = venv_dir / "Scripts" / "pip.exe"
    else:
        python_path = venv_dir / "bin" / "python"
        pip_path = venv_dir / "bin" / "pip"
    
    return str(python_path), str(pip_path)

def install_requirements(pip_path):
    """Install required packages in the virtual environment."""
    print("\nInstalling required packages...")
    
    # Create a minimal requirements file for just the export functionality
    export_requirements = """beeai
python-dotenv
pdfkit
markdown
"""
    
    with open("export_requirements.txt", "w") as f:
        f.write(export_requirements)
    
    try:
        subprocess.run([pip_path, "install", "-r", "export_requirements.txt"], check=True)
        print("✓ All packages installed successfully")
    finally:
        # Clean up temporary requirements file
        if os.path.exists("export_requirements.txt"):
            os.remove("export_requirements.txt")

def check_wkhtmltopdf():
    """Check if wkhtmltopdf is installed."""
    try:
        subprocess.run(["wkhtmltopdf", "--version"], 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL, 
                      check=True)
        print("✓ wkhtmltopdf is installed")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("\n⚠️  Warning: wkhtmltopdf is not installed!")
        print("PDF export requires wkhtmltopdf. Please install it:")
        print("  Ubuntu/Debian: sudo apt-get install wkhtmltopdf")
        print("  macOS: brew install wkhtmltopdf")
        print("  Windows: Download from https://wkhtmltopdf.org/downloads.html")
        return False

def get_api_key():
    """Prompt user for their Bee API key."""
    print("\n" + "="*50)
    print("Bee AI Conversation Batch Export Tool")
    print("="*50)
    print("\nTo get your API key:")
    print("1. Visit https://developer.bee.computer/keys")
    print("2. Sign in or create an account")
    print("3. Create a new key and copy it\n")
    
    api_key = input("Enter your Bee API key: ").strip()
    
    if not api_key:
        print("Error: API key cannot be empty")
        sys.exit(1)
    
    return api_key

def confirm_export():
    """Ask user to confirm the export operation."""
    print("\n⚠️  This will export ALL your Bee AI conversations as PDF files.")
    print("Depending on the number of conversations, this may take some time.")
    
    response = input("\nDo you want to continue? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y']:
        print("Export cancelled.")
        sys.exit(0)

def run_export(python_path, api_key):
    """Run the actual export process."""
    export_script = '''
import os
import sys
import asyncio
import time
from datetime import datetime
from pathlib import Path
from beeai import Bee
import pdfkit
import markdown as md

async def export_conversations(api_key):
    """Export all conversations as PDF files."""
    bee = Bee(api_key)
    
    # Create export directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_dir = Path(f"bee_export_{timestamp}")
    export_dir.mkdir(exist_ok=True)
    
    print(f"\\nExport directory: {export_dir}")
    print("\\nFetching conversations...")
    
    # Fetch all conversations
    all_convos = []
    page = 1
    limit = 100
    
    while True:
        try:
            payload = await bee.get_conversations('me', page=page, limit=limit)
            batch = payload.get('conversations', [])
            if not batch:
                break
            all_convos.extend(batch)
            page += 1
        except Exception as e:
            print(f"\\nError fetching conversations: {e}")
            return
    
    total = len(all_convos)
    print(f"Found {total} conversations to export\\n")
    
    if total == 0:
        print("No conversations found.")
        return
    
    # Export each conversation
    success_count = 0
    error_count = 0
    
    for i, conv in enumerate(all_convos, 1):
        try:
            print(f"[{i}/{total}] Exporting conversation {conv['id']}...", end='', flush=True)
            
            # Fetch full conversation
            full_conv = await bee.get_conversation('me', conv['id'])
            
            # Generate HTML for PDF
            html = generate_pdf_html(full_conv)
            
            # Create safe filename
            title = full_conv['conversation'].get('short_summary', f"Conversation {conv['id']}")
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()[:50]
            filename = f"conversation_{conv['id']}_{safe_title}.pdf"
            filepath = export_dir / filename
            
            # Convert to PDF
            options = {
                'enable-local-file-access': None,
                'encoding': 'UTF-8',
                'page-size': 'A4',
                'margin-top': '0.75in',
                'margin-right': '0.75in',
                'margin-bottom': '0.75in',
                'margin-left': '0.75in',
            }
            
            pdfkit.from_string(html, str(filepath), options=options)
            
            print(" ✓")
            success_count += 1
            
        except Exception as e:
            print(f" ✗ Error: {e}")
            error_count += 1
            continue
    
    # Summary
    print(f"\\n{'='*50}")
    print(f"Export completed!")
    print(f"  Successfully exported: {success_count}")
    print(f"  Errors: {error_count}")
    print(f"  Export location: {export_dir.absolute()}")
    print(f"{'='*50}")

def generate_pdf_html(convo):
    """Generate HTML for PDF export."""
    conversation = convo.get('conversation', {})
    messages = convo.get('messages', [])
    
    # Convert markdown to HTML
    def markdown_to_html(text):
        return md.markdown(text or '', extensions=['fenced_code', 'codehilite'])
    
    # Build HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Conversation {conversation.get('id', 'Unknown')}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }}
            h1 {{
                color: #2c3e50;
                border-bottom: 2px solid #3498db;
                padding-bottom: 10px;
            }}
            .metadata {{
                background: #f8f9fa;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 20px;
            }}
            .message {{
                margin-bottom: 20px;
                padding: 15px;
                border-radius: 5px;
            }}
            .message.human {{
                background: #e3f2fd;
                border-left: 4px solid #2196f3;
            }}
            .message.assistant {{
                background: #f5f5f5;
                border-left: 4px solid #757575;
            }}
            .message-header {{
                font-weight: bold;
                margin-bottom: 10px;
                color: #555;
            }}
            pre {{
                background: #f4f4f4;
                padding: 10px;
                border-radius: 3px;
                overflow-x: auto;
            }}
            code {{
                background: #f4f4f4;
                padding: 2px 4px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
            }}
        </style>
    </head>
    <body>
        <h1>{conversation.get('short_summary', 'Conversation')}</h1>
        
        <div class="metadata">
            <p><strong>ID:</strong> {conversation.get('id', 'Unknown')}</p>
            <p><strong>Created:</strong> {conversation.get('created_at', 'Unknown')}</p>
            <p><strong>Updated:</strong> {conversation.get('updated_at', 'Unknown')}</p>
            <p><strong>Message Count:</strong> {conversation.get('message_count', 0)}</p>
        </div>
    """
    
    # Add messages
    for msg in messages:
        role = msg.get('role', 'unknown')
        text = markdown_to_html(msg.get('text', ''))
        
        role_class = 'human' if role == 'human' else 'assistant'
        role_label = 'You' if role == 'human' else 'Bee'
        
        html += f"""
        <div class="message {role_class}">
            <div class="message-header">{role_label}</div>
            <div class="message-content">{text}</div>
        </div>
        """
    
    html += """
    </body>
    </html>
    """
    
    return html

# Run the export
if __name__ == "__main__":
    api_key = sys.argv[1]
    asyncio.run(export_conversations(api_key))
'''
    
    # Write the export script to a temporary file
    with open("_export_runner.py", "w") as f:
        f.write(export_script)
    
    try:
        # Run the export script with the virtual environment's Python
        subprocess.run([python_path, "_export_runner.py", api_key], check=True)
    finally:
        # Clean up temporary file
        if os.path.exists("_export_runner.py"):
            os.remove("_export_runner.py")

def main():
    """Main execution flow."""
    print("Bee AI Batch Export Tool")
    print("========================\n")
    
    # Check Python version
    check_python_version()
    
    # Setup virtual environment
    python_path, pip_path = setup_virtual_environment()
    
    # Install requirements
    install_requirements(pip_path)
    
    # Check for wkhtmltopdf
    if not check_wkhtmltopdf():
        response = input("\nContinue anyway? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("Export cancelled.")
            sys.exit(0)
    
    # Get API key
    api_key = get_api_key()
    
    # Confirm export
    confirm_export()
    
    # Run export
    print("\nStarting export process...")
    run_export(python_path, api_key)
    
    print("\n✨ Done! Check your export folder for the PDF files.")

if __name__ == "__main__":
    main()