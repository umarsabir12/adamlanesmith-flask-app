ATTACHMENT QUIZ – INSTALLATION GUIDE
───────────────────────────────────────
This guide helps you set up the full multi-step quiz project (FC, SC, Likert) with Flask, PDF download, session storage, and styling.


1. PROJECT STRUCTURE
──────────────────────
project_folder/
│
├── app.py                  # Flask backend
├── data/
│   └── quiz_structure.json # All questions (FC, SC, Likert)
├── templates/
│   ├── fc_question.html    # One FC question per page (Typeform style)
│   ├── sc_section.html     # Scenario questions page
│   ├── likert_section.html # Likert-scale page
│   └── results.html        # Results page with PDF download
├── static/
│   └── style.css (optional) # Shared CSS (if used)
└── README.txt              # You're reading this!

2. REQUIREMENTS
─────────────────
You'll need Python 3.8+ installed.

Install dependencies in a virtual environment:

```bash
# Step into your project directory
cd your_project_folder


# Create virtual environment
python -m venv .venv


# Activate environment
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate


# Install required packages
pip install flask fpdf reportlab


# To Run
python app.py
