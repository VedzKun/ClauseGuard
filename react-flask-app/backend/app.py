import re
import os
import tempfile
import traceback
import json
from typing import List, Dict

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

from docx import Document
from PyPDF2 import PdfReader

app = Flask(__name__)
CORS(app)

def extract_text_from_pdf(file_path: str) -> str:
    try:
        reader = PdfReader(file_path)
        text = "\n".join([page.extract_text() or "" for page in reader.pages if page])
        return text
    except Exception as e:
        raise RuntimeError(f"Failed to extract text from PDF: {e}")

def extract_text_from_docx(file_path: str) -> str:
    try:
        doc = Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except Exception as e:
        raise RuntimeError(f"Failed to extract text from DOCX: {e}")

def extract_text(file_path: str) -> str:
    if file_path.endswith(".pdf"):
        return extract_text_from_pdf(file_path)
    elif file_path.endswith(".docx"):
        return extract_text_from_docx(file_path)
    else:
        raise ValueError("Unsupported file type. Use PDF or DOCX.")

def split_into_clauses(text: str) -> List[str]:
    sentences = re.split(r'(?<=[.;])\s+(?=[A-Z])', text.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 20]

def check_clause_risks(clause: str) -> List[Dict[str, str]]:
    risks = []
    lc = clause.lower()

    if "termination" in lc and not re.search(r"\d+ (day|month|year)s?", lc):
        risks.append({"risk": "⚠️ Unclear Termination: No clear notice period or timeline specified.", "severity": "Medium", "type": "Termination"})

    if "penalty" in lc and re.search(r"\d{2,}%|\$\d{3,}", lc):
        risks.append({"risk": "⚠️ High Penalty: Financial penalty amount seems unusually high.", "severity": "High", "type": "Penalty"})

    if "arbitration" in lc and "sole discretion" in lc:
        risks.append({"risk": "🚩 Biased Arbitration: Arbitration terms appear to favor one party.", "severity": "High", "type": "Arbitration"})

    if any(keyword in lc for keyword in ["agreement", "obligation", "responsibility", "party", "condition"]):
        if "indemnity" not in lc:
            risks.append({"risk": "📄 Missing Indemnity Clause: Document may lack protection against third-party claims.", "severity": "Medium", "type": "Indemnity"})
        if "liability" not in lc:
            risks.append({"risk": "📄 Missing Liability Clause: Absence of liability limits could be risky.", "severity": "Medium", "type": "Liability"})
        if "confidentiality" not in lc:
            risks.append({"risk": "📄 Missing Confidentiality Clause: Sensitive information might not be protected.", "severity": "Medium", "type": "Confidentiality"})

    return risks

def analyze_text(text: str):
    clauses = split_into_clauses(text)
    results = []
    for i, clause in enumerate(clauses):
        risks = check_clause_risks(clause)
        if risks:
            results.append({"index": i+1, "clause": clause, "risks": risks})
    return results

def group_risks(results):
    grouped = {}
    for item in results:
        for risk in item["risks"]:
            rtype = risk["type"]
            if rtype not in grouped:
                grouped[rtype] = []
            grouped[rtype].append({"clause": item["clause"], "risk": risk["risk"], "severity": risk["severity"], "index": item["index"]})
    return grouped

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    suffix = ".pdf" if file.filename.endswith(".pdf") else ".docx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(file.read())
        temp_path = tmp_file.name

    try:
        text = extract_text(temp_path)
        if not text.strip():
            return jsonify({"error": "No text could be extracted from the uploaded file. It might be scanned or encrypted."}), 400

        results = analyze_text(text)
        grouped = group_risks(results)

        return jsonify({
            "grouped_risks": grouped,
            "total_clauses": len(results)
        })
    except Exception as e:
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

if __name__ == '__main__':
    app.run(debug=True)