import { useMemo, useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000/score";

export default function App() {
  const [jdFile, setJdFile] = useState(null);
  const [resumeFile, setResumeFile] = useState(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const score = result?.match_score ?? null;

  const scoreColor = useMemo(() => {
    if (score === null) return "#b45309"; // amber-ish
    if (score >= 80) return "#166534"; // green
    if (score >= 60) return "#b45309"; // amber
    return "#991b1b"; // red
  }, [score]);

  const handleAnalyze = async () => {
    setError("");
    setResult(null);

    if (!jdFile) return setError("Please upload Job Description (.txt).");
    if (!resumeFile) return setError("Please upload Resume (.pdf).");

    const formData = new FormData();
    formData.append("jd_file", jdFile);
    formData.append("resume_file", resumeFile);

    try {
      setLoading(true);
      const res = await fetch(API_URL, { method: "POST", body: formData });
      const data = await res.json();

      if (!res.ok) {
        setError(data?.detail || "Request failed");
        return;
      }
      setResult(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="container">
        <header className="header">
          <h1 className="title">TalentFit Analyzer</h1>
          <p className="subtitle">
            Analyze how well a candidate’s resume matches your job description using AI-powered insights
          </p>
        </header>

        <section className="uploadRow card">
          <div className="uploadCol">
            <label className="uploadLabel">Job Description</label>
            <div className="uploadBox">
              <div className="fileName">{jdFile ? jdFile.name : "No file selected"}</div>
              <div className="fileHint">.txt files only</div>
              <input
                className="fileInput"
                type="file"
                accept=".txt,text/plain"
                onChange={(e) => setJdFile(e.target.files?.[0] || null)}
              />
            </div>
          </div>

          <div className="uploadCol">
            <label className="uploadLabel">Resume</label>
            <div className="uploadBox">
              <div className="fileName">{resumeFile ? resumeFile.name : "No file selected"}</div>
              <div className="fileHint">.pdf files only</div>
              <input
                className="fileInput"
                type="file"
                accept="application/pdf"
                onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
              />
            </div>
          </div>
        </section>

        <div className="actions">
          <button className="primaryBtn" onClick={handleAnalyze} disabled={loading}>
            {loading ? "Analyzing..." : "Analyze Match"}
          </button>
        </div>

        {error && <div className="errorBox">{error}</div>}

        {result && (
          <>
            <section className="scoreCard card">
              <div className="scoreTitle">Match Score</div>
              <div className="scoreValue" style={{ color: scoreColor }}>
                {result.match_score}
                <span className="scoreOutOf">/100</span>
              </div>
            </section>

            <section className="twoCols">
              <div className="card">
                <div className="cardHeader good">
                  <span className="dot goodDot" />
                  Matched Skills
                </div>
                <div className="cardSub">
                  Skills found in both resume and job description
                </div>
                <div className="pillWrap">
                  {(result.matched_skills || []).map((s, i) => (
                    <span className="pill goodPill" key={`${s}-${i}`}>{s}</span>
                  ))}
                  {(result.matched_skills || []).length === 0 && (
                    <div className="emptyText">No matched skills detected.</div>
                  )}
                </div>
              </div>

              <div className="card">
                <div className="cardHeader bad">
                  <span className="dot badDot" />
                  Missing Skills
                </div>
                <div className="cardSub">
                  Required skills not found in the resume
                </div>
                <div className="pillWrap">
                  {(result.missing_or_weak_skills || []).map((s, i) => (
                    <span className="pill badPill" key={`${s}-${i}`}>{s}</span>
                  ))}
                  {(result.missing_or_weak_skills || []).length === 0 && (
                    <div className="emptyText">No missing skills detected.</div>
                  )}
                </div>
              </div>
            </section>

            <section className="twoCols">
              <div className="card">
                <div className="cardHeader plain">Profile Summary</div>
                <p className="cardText">{result.explanation}</p>
              </div>

              <div className="card">
                <div className="cardHeader plain">Hiring Recommendation</div>
                <p className="cardText">{result.recommendation}</p>
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  );
}
