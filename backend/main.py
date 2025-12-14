import os
import io
import json
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from openai import OpenAI
from pypdf import PdfReader

# FastAPI file upload uses UploadFile + File(...) for multipart/form-data. [web:22]
# FastAPI CORS is enabled via CORSMiddleware. [web:59]

load_dotenv()

app = FastAPI(title="Candidate-Matching")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite default
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY missing. Put it in your environment or .env file.")

client = OpenAI(api_key=api_key)
MODEL = "gpt-4o-mini"


class ScoreResponse(BaseModel):
    match_score: int = Field(..., ge=0, le=100)
    explanation: str
    matched_skills: list[str]
    missing_or_weak_skills: list[str]
    recommendation: str


# Prompt call #1: scoring-only (must output ONLY an integer)
SCORE_PROMPT = """
You are a strict scoring engine for resume-vs-job-description matching.

Goal: Output ONLY a single integer from 0 to 100 (no JSON, no words, no punctuation).

Inputs you will receive:
- JOB DESCRIPTION text
- RESUME text

Step 1) Determine years of experience (YOE)
- Compute candidate YOE from resume (prefer explicit years, else infer from date ranges).
- If unclear, infer conservatively; if still unclear set experience_level="unknown".
- Map to experience_level:
  - fresher: 0 YOE
  - early_career: 0.5–2 YOE
  - experienced: >2 YOE
  - unknown: treat as early_career rubric

Step 2) Extract JD requirements
- Identify JD skills/technologies/tools (hard skills).
- Identify key responsibilities/experience requirements.
- Treat them as the reference set for matching.

Step 3) Apply rubric (total must equal 100)
Use exactly ONE rubric based on experience_level.

Rubric A) fresher (0 YOE):
- matching_skills: 35
- projects_using_jd_skills: 35
- relevant_education: 20
- internships: 10

Rubric B) early_career (0.5–2 YOE OR unknown):
- matching_skills: 40
- relevant_experience_quality: 30
- relevant_years_months: 15 (cap at 24 months)
- relevant_projects: 10
- education_or_certs: 5

Rubric C) experienced (>2 YOE):
- matching_skills: 45
- relevant_years_experience: 35
- total_years_experience: 10
- role_domain_alignment: 10

Step 4) Scoring rules (important)
- matching_skills: Score by coverage of JD hard skills found in resume (exact match or strong synonym). Partial coverage = partial points.
- Experience-related categories: Only count experience that matches the JD domain/role.
- relevant_years_months: Convert relevant experience to months; (months / 24) * 15, capped at 15.
- relevant_years_experience: Convert relevant years; scale linearly up to full points at 5+ relevant years (cap at 35).
- No fabrication: If the resume does not support a claim, do not award points.

Step 5) Output
- Output ONLY the final integer score 0–100.
"""


# Prompt call #2: analysis JSON (must reuse the provided match_score)
SYSTEM_PROMPT = """You are an ATS-style evaluator.
Compare a candidate resume to a job description.

A match_score has already been computed using a fixed rubric.
You MUST use the provided match_score exactly as given (do not change it).

Recommendation rules (must follow):
- If match_score >= 85:
  recommendation_label = "Strong fit — shortlist"
- If 70 <= match_score <= 84:
  recommendation_label = "Good fit — interview"
- If 55 <= match_score <= 69:
  recommendation_label = "Borderline — needs review"
- If match_score < 55:
  recommendation_label = "Not a fit — reject"

The recommendation field MUST be exactly:
"<recommendation_label>. Reason: <one key strength>; Gap: <one key missing/weak skill>."
Keep it one sentence.

Return ONLY valid JSON with keys:
match_score (0-100 integer),
explanation (1-3 sentences),
matched_skills (array of strings),
missing_or_weak_skills (array of strings),
recommendation (one sentence in the exact format above).
No extra text.
"""


def extract_text_from_txt(txt_bytes: bytes) -> str:
    return txt_bytes.decode("utf-8", errors="replace").strip()


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts).strip()


def clamp_int(n: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, n))


def parse_score_int(model_text: str) -> int:
    """
    Accepts the model output and extracts an integer score.
    We ask for "only an integer", but this hardens against accidental extra chars.
    """
    s = model_text.strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    if digits == "":
        raise ValueError(f"Could not parse score from: {model_text!r}")
    return clamp_int(int(digits), 0, 100)


@app.post("/score", response_model=ScoreResponse)
async def score(
    jd_file: UploadFile = File(...),
    resume_file: UploadFile = File(...),
):
    # 1) Validate content types (basic check)
    if jd_file.content_type not in ("text/plain", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="JD must be a .txt file.")
    if resume_file.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(status_code=400, detail="Resume must be a PDF.")

    # 2) Read bytes
    jd_bytes = await jd_file.read()
    pdf_bytes = await resume_file.read()

    if not jd_bytes:
        raise HTTPException(status_code=400, detail="Empty JD file uploaded.")
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty PDF uploaded.")

    # 3) Extract text
    jd_text = extract_text_from_txt(jd_bytes)
    resume_text = extract_text_from_pdf(pdf_bytes)

    if len(jd_text) < 20:
        raise HTTPException(status_code=400, detail="JD text is too short.")
    if len(resume_text) < 20:
        raise HTTPException(
            status_code=400,
            detail="Could not extract enough text from PDF (might be scanned/image-only).",
        )

    # 4) LLM calls
    try:
        common_user_prompt = f"JOB DESCRIPTION:\n{jd_text}\n\nRESUME:\n{resume_text}\n"

        # Call #1: get integer match_score (rubric-based)
        score_resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SCORE_PROMPT},
                {"role": "user", "content": common_user_prompt},
            ],
            temperature=0.0,
        )
        score_text = (score_resp.choices[0].message.content or "").strip()
        match_score = parse_score_int(score_text)

        # Call #2: get full JSON (force it to reuse match_score)
        analysis_resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"match_score: {match_score}\n\n{common_user_prompt}",
                },
            ],
            temperature=0.2,
        )

        content = (analysis_resp.choices[0].message.content or "").strip()
        data = json.loads(content)

        # Enforce rubric score even if the model tries to change it
        data["match_score"] = match_score

        # FastAPI will validate the response via response_model (Pydantic). [web:148]
        return data

    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="LLM did not return valid JSON.")
    except ValueError as e:
        raise HTTPException(status_code=502, detail=f"Could not parse match score: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}
