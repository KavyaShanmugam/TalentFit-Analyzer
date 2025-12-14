# Resume Scoring (JD vs Resume)

A small full-stack app that scores how well a resume matches a job description using an LLM.

## Features
- Upload Job Description as `.txt`
- Upload Resume as `.pdf`
- Backend extracts text, generates a rubric-based match score (0–100), and returns:
  - match_score
  - matched_skills
  - missing_or_weak_skills
  - explanation
  - recommendation

## Tech Stack
- Backend: FastAPI + Python
- Frontend: React (Vite)
- LLM: OpenAI (API key required)

# Project Structure
- `backend/` - FastAPI server
- `frontend/` - React UI

# Backend Setup (FastAPI)
1. Go to backend:
##
        cd backend


## Create venv and install dependencies:

bash
        
        python -m venv .venv

## Windows


        .venv\Scripts\activate

## macOS/Linux:

        source .venv/bin/activate
## 
    pip install -r requirements.txt

Add .env inside backend/:

    OPENAI_API_KEY=your_openai_key

## Run server:

    bash
    uvicorn main:app --reload --port 8000

# Frontend Setup (React + Vite)
Go to frontend:

    cd frontend

Install deps and run:

    npm install
    npm run dev
    Open the URL printed by Vite (usually http://localhost:5173).



## USAGE
- Upload JD .txt file

- Upload Resume .pdf file

- Click Analyze Match

## RESULT
- Match Score
- Matched skills
- Missing skills
- Profile Summary
- Recommendation