import fitz
import pdfplumber
from docx import Document
import subprocess
import platform
import os
import re

def extract_fitz_advanced(path):
    """
    Architect-level extraction using PyMuPDF.
    1. Uses 'dict' extraction to access spatial blocks and font metadata.
    2. Sorts blocks to naturally handle 2-column layouts without shredding reading order.
    3. Uses a Two-Pass Statistical Algorithm to detect Dark-Mode resumes vs ATS gaming (invisible text).
    """
    text = ""
    fraud_flags = []
    
    try:
        doc = fitz.open(path)
        
        # --- PASS 1: CONTEXTUAL COLOR DISTRIBUTION ---
        # We quickly scan the document to see if it's a "Dark Mode" resume or has heavy dark UI elements.
        white_char_count = 0
        total_char_count = 0
        
        for page in doc:
            page_data = page.get_text("dict", sort=True)
            for block in page_data.get("blocks", []):
                # Type 0 is text. Ignore images.
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        chars = len(span.get("text", "").strip())
                        total_char_count += chars
                        # Color 16777215 is 0xFFFFFF (Pure White)
                        if span.get("color") == 16777215:
                            white_char_count += chars
                            
        # If more than 15% of the text is white, it's a dark-mode/heavy-design resume, not a fraudster.
        is_dark_mode = False
        if total_char_count > 0 and (white_char_count / total_char_count) > 0.15:
            is_dark_mode = True

        # --- PASS 2: ACTUAL EXTRACTION & FRAUD DEFENSE ---
        for page in doc:
            page_data = page.get_text("dict", sort=True)
            
            for block in page_data.get("blocks", []):
                if block.get("type") != 0:
                    continue
                
                block_text = ""
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        
                        # 1. Context-Aware White Text Check
                        # Only flag as invisible text IF the document is NOT a dark-mode resume.
                        if span.get("color") == 16777215 and not is_dark_mode:
                            if "invisible_text" not in fraud_flags:
                                fraud_flags.append("invisible_text")
                            continue # Skip adding this cheating text
                            
                        # 2. Microscopic Text Check (Font size < 4 is unreadable to humans)
                        # We always run this, because even dark-mode resumes shouldn't have size 1 font.
                        if span.get("size", 10) < 4.0:
                            if "microscopic_text" not in fraud_flags:
                                fraud_flags.append("microscopic_text")
                            continue # Skip adding this cheating text
                        
                        block_text += span.get("text", "") + " "
                    block_text += "\n"
                
                # Append the cleanly extracted block to the main text, separated by a newline
                text += block_text.strip() + "\n\n"
                
    except Exception as e:
        print("PyMuPDF advanced extraction failed:", e)
        return "", []
        
    return text.strip(), fraud_flags

def extract_pdfplumber(path):
    text = ""
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                # layout=True attempts to preserve visual formatting
                text += page.extract_text(layout=True) or ""
    except Exception as e:
        print("pdfplumber failed:", e)
    return text, []

def extract_docx(path):
    text = ""
    try:
        doc = Document(path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    except Exception as e:
        print("docx failed:", e)
    return text, []

def extract_doc(path):
    text = ""
    system = platform.system()
    try:
        if system == "Darwin": 
            result = subprocess.run(['textutil', '-stdout', '-cat', 'txt', path], 
                                    capture_output=True, text=True, check=True)
            text = result.stdout
        elif system == "Windows":
            import win32com.client
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            doc = word.Documents.Open(os.path.abspath(path))
            text = doc.Content.Text
            doc.Close()
            word.Quit()
        else:
            result = subprocess.run(['antiword', path], 
                                    capture_output=True, text=True, check=True)
            text = result.stdout
    except Exception as e:
        print(f"System-level .doc extraction failed on {system}: {e}")
        print("Using binary string extraction fallback...")
        with open(path, 'rb') as f:
            raw_data = f.read()
        text = " ".join(re.findall(rb'[a-zA-Z0-9.,;:!? \n\t]{4,}', raw_data).decode('utf-8', errors='ignore'))
    
    return text, []

def extract_text(path):
    """
    Master router for file ingestion.
    Returns a dictionary to pass both the text and system-level flags down the pipeline.
    """
    ext = path.lower()
    text = ""
    fraud_flags = []
    
    if ext.endswith(".pdf"):
        text, fraud_flags = extract_fitz_advanced(path)
        # Fallback if PyMuPDF yields garbage or an empty string (e.g., scanned PDF)
        if len(text.strip()) < 500:
            print(f"Fallback to pdfplumber for {path}")
            fallback_text, _ = extract_pdfplumber(path)
            # Only use fallback if it actually found more text
            if len(fallback_text) > len(text):
                text = fallback_text
                
    elif ext.endswith(".docx"):
        text, fraud_flags = extract_docx(path)
    elif ext.endswith(".doc"):
        text, fraud_flags = extract_doc(path)
    else:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()
        except Exception:
            raise ValueError(f"Unsupported file type: {path}")

    return {
        "raw_text": text,
        "fraud_flags": fraud_flags
    }