import os

# 1. Ingestion & Cleaning
from ingestion.extractor import extract_text
from utils.text_cleaner import clean_text

# 2. Segmentation
from segmentation.section_detector import segment_resume

# 3. Feature Extractors
from features.experience_extractor import extract_experience
from features.skill_extractor import extract_skills
from features.project_extractor import extract_projects
from features.education_extractor import extract_education
from features.achievement_extractor import extract_achievements
from features.extracurricular_extractor import extract_extracurricular
from features.minor_extraction import extract_minor_features
from features.school_extractor import extract_school_marks

# 4. Scoring Engine
from scoring.final_score import compute_final_score


def infer_profession(text: str) -> str:
    """
    A lightweight heuristic classifier.
    Specific/Niche technical roles are placed at the TOP to prevent keyword shadowing.
    Added 'natural language processing' and standalone 'prompt' to bypass OCR font errors (AI vs Al).
    """
    text_lower = text.lower()
    
    # 1. Most Specific / Technical Roles First
    if "cybersecurity" in text_lower or "security analyst" in text_lower:
        return "Cybersecurity"
    elif "physician" in text_lower or "medical" in text_lower or "doctor" in text_lower:
        return "Medical / Healthcare"
    elif (
        "prompt" in text_lower
        or "artificial intelligence" in text_lower
        or "natural language processing" in text_lower
        or "machine learning" in text_lower
    ):
        return "AI & Machine Learning"
    elif "developer" in text_lower or "software" in text_lower or "engineer" in text_lower:
        return "Software Engineering"
        
    # 2. Broader Roles Second
    elif "design" in text_lower or "layout" in text_lower or "creative" in text_lower or "graphic" in text_lower:
        return "Design & Creative"
    elif "marketing" in text_lower or "sales" in text_lower or "seo" in text_lower:
        return "Marketing & Sales"
    elif "manager" in text_lower or "management" in text_lower:
        return "Business / Management"
        
    # 3. Fallback
    else:
        return "General / Uncategorized"


def process_resume(pdf_path: str, custom_weights: dict = None) -> dict:
    """
    The master orchestrator.
    Takes a PDF path, runs the entire deterministic pipeline, and returns the final score.
    """
    try:
        ingestion_result = extract_text(pdf_path)
        
        if isinstance(ingestion_result, dict):
            raw_text = ingestion_result.get("raw_text", "")
            fraud_flags = ingestion_result.get("fraud_flags", [])
        else:
            raw_text = ingestion_result
            fraud_flags = []
            
        cleaned_text = clean_text(raw_text)
        sections = segment_resume(cleaned_text)
        
        features = {
            "experience": extract_experience(sections),
            "skills": extract_skills(sections),
            "projects": extract_projects(sections),
            "education": extract_education(sections),
            "achievements": extract_achievements(sections),
            "extracurricular": extract_extracurricular(sections),
            "minor": extract_minor_features(sections, cleaned_text),
            "school": extract_school_marks(sections)
        }
        
        # Pass custom weights to scoring engine
        score_data = compute_final_score(features, custom_weights)
        
        # Inject the inferred profession for the UI dashboard
        score_data["profession"] = infer_profession(cleaned_text)
        
        score_data["status"] = "success"
        score_data["fraud_flags"] = fraud_flags
        
        # Updated fraud check: checks for both invisible AND microscopic text
        if "invisible_text" in fraud_flags or "microscopic_text" in fraud_flags:
            score_data["breakdown"]["WARNING"] = "Hidden/Microscopic text detected and ignored. Please remove this."
            score_data["status"] = "WARNING_ISSUED"

        return score_data

    except Exception as e:
        print(f"Error processing {pdf_path}: {e}")
        return {
            "status": "error",
            "error_message": str(e),
            "total_score": 0,
            "breakdown": {},
            "fresher": True,
            "completeness": 0,
            "fraud_flags": [],
            "profession": "Error Processing"
        }