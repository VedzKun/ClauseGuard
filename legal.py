# legal_risk_analyzer.py (Streamlit UI Version with Risk Grouping, Filtering, Summary Export)

import re
import os
from typing import List, Dict
import tempfile
import traceback
import json

import streamlit as st
from docx import Document
from PyPDF2 import PdfReader

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

def main():
    st.title("📄 Legal Risk Analyzer")
    st.write("Upload a legal document (PDF or DOCX) and identify potential risk clauses.")

    uploaded_file = st.file_uploader("Choose a file", type=["pdf", "docx"])

    if uploaded_file is not None:
        suffix = ".pdf" if uploaded_file.name.endswith(".pdf") else ".docx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(uploaded_file.read())
            temp_path = tmp_file.name

        try:
            text = extract_text(temp_path)
            if not text.strip():
                st.warning("No text could be extracted from the uploaded file. It might be scanned or encrypted.")
                return

            st.subheader("📃 Extracted Text Preview")
            st.text_area("Preview", text[:3000], height=200)

            results = analyze_text(text)
            grouped = group_risks(results)

            severity_filter = st.multiselect("Filter by severity:", ["High", "Medium"], default=["High", "Medium"])

            if results:
                st.subheader("📊 Risk Summary Report")
                for rtype, items in grouped.items():
                    filtered = [r for r in items if r["severity"] in severity_filter]
                    if filtered:
                        st.markdown(f"### 🔹 {rtype} Risks")
                        for r in filtered:
                            st.markdown(f"**Clause {r['index']}:**")
                            st.write(r["clause"])
                            st.markdown(f"- {r['risk']} ({r['severity']})")
                            st.markdown("---")

                export_data = {
                    "summary": grouped,
                    "filtered_by": severity_filter,
                    "total_clauses": len(results)
                }
                st.download_button(
                    label="📥 Download Risk Report (JSON)",
                    data=json.dumps(export_data, indent=2),
                    file_name="risk_report.json",
                    mime="application/json"
                )
            else:
                st.success("No major risks detected in the document.")
        except Exception as e:
            st.error("An error occurred during processing.")
            st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
