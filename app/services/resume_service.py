"""
app/services/resume_service.py

Phase 5 — PDF resume parsing.

Pipeline:
  1. extract_text_from_pdf  — pdfplumber → raw text string
  2. extract_skills          — keyword scan against ~120 tech terms
  3. extract_projects        — heuristic section parser
  4. parse_resume            — orchestrates 1-3, returns MongoDB-ready dict

The raw text (truncated to 8 000 chars) is also stored so Phase 6
can pass it to Gemini without requiring a second upload.
"""

import io
import re
from datetime import datetime

import pdfplumber


# ── Technology keyword database ───────────────────────────────────────────────
# Canonical spellings — matching is case-insensitive, but we always
# return the canonical form (e.g. "React", not "react" or "REACT").

TECH_KEYWORDS: set[str] = {
    # ── Languages ────────────────────────────────────────────────────────────
    "Python", "JavaScript", "TypeScript", "Java", "C++", "C#",
    "Go", "Rust", "Ruby", "PHP", "Swift", "Kotlin", "Scala",
    "R", "MATLAB", "Dart", "Elixir", "Haskell", "Lua", "Perl",
    # ── Frontend ─────────────────────────────────────────────────────────────
    "React", "Vue", "Angular", "Next.js", "Nuxt.js", "Svelte",
    "HTML", "CSS", "Sass", "Tailwind", "Bootstrap",
    "Redux", "GraphQL", "Webpack", "Vite", "jQuery",
    "Material UI", "Chakra UI", "Framer Motion",
    # ── Backend ───────────────────────────────────────────────────────────────
    "Node.js", "Express", "FastAPI", "Django", "Flask",
    "Spring Boot", "Rails", "Laravel", "NestJS", "Gin", "Fiber",
    "ASP.NET", "Hapi", "Koa", "Fastify",
    # ── Databases ─────────────────────────────────────────────────────────────
    "MongoDB", "PostgreSQL", "MySQL", "SQLite", "Redis",
    "DynamoDB", "Firebase", "Supabase", "Elasticsearch",
    "Cassandra", "Neo4j", "Prisma", "SQLAlchemy", "Mongoose",
    # ── Cloud & DevOps ────────────────────────────────────────────────────────
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform",
    "Ansible", "GitHub Actions", "Jenkins", "CircleCI", "GitLab CI",
    "CI/CD", "Linux", "Nginx", "Apache", "Heroku", "Vercel", "Netlify",
    # ── ML / AI ───────────────────────────────────────────────────────────────
    "TensorFlow", "PyTorch", "Scikit-learn", "NumPy", "Pandas",
    "Keras", "OpenCV", "Hugging Face", "LangChain", "spaCy",
    "Matplotlib", "Seaborn", "Jupyter", "NLTK",
    # ── Mobile ────────────────────────────────────────────────────────────────
    "React Native", "Flutter", "Android", "iOS", "Expo",
    # ── Tools & General ───────────────────────────────────────────────────────
    "Git", "REST", "SQL", "NoSQL", "gRPC", "WebSockets",
    "Microservices", "Agile", "Scrum", "Postman", "Figma",
}

# Pre-build lowercase → canonical map so we iterate it once per call
_KEYWORD_MAP: dict[str, str] = {kw.lower(): kw for kw in TECH_KEYWORDS}


# ── Text extraction ───────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extract all text from a PDF using pdfplumber.

    Raises ValueError if no text is found — usually means the PDF is a
    scanned image rather than a digital/text-based document.
    """
    parts: list[str] = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                parts.append(page_text)

    full_text = "\n".join(parts).strip()

    if not full_text:
        raise ValueError(
            "No text could be extracted from this PDF. "
            "Please use a digital (text-based) PDF, not a scanned image."
        )

    return full_text


# ── Skill extraction ──────────────────────────────────────────────────────────

def extract_skills(text: str) -> list[str]:
    """
    Scan resume text for known technology keywords.

    Uses negative lookahead/lookbehind on [a-z] to avoid partial matches:
      'Flask'  matches, 'Reflask'  does not
      'Go'     matches, 'Django'   does not
      'Next.js' matches via re.escape → 'next\\.js'

    Returns a sorted, deduplicated list of canonical keyword names.
    """
    text_lower = text.lower()
    found: set[str] = set()

    for lower_kw, canonical_kw in _KEYWORD_MAP.items():
        # re.escape handles C++, C#, Next.js, CI/CD, etc.
        pattern = r"(?<![a-z])" + re.escape(lower_kw) + r"(?![a-z])"
        if re.search(pattern, text_lower):
            found.add(canonical_kw)

    return sorted(found)


# ── Project extraction ────────────────────────────────────────────────────────

# Section header that opens the projects block
_PROJECT_SECTION = re.compile(
    r"^(projects?|project experience|personal projects?|"
    r"academic projects?|key projects?|notable projects?|"
    r"selected projects?)\s*$",
    re.IGNORECASE,
)

# Section headers that close the projects block
_OTHER_SECTION = re.compile(
    r"^(experience|education|skills|certifications|awards|publications|"
    r"work experience|internship|achievements|interests|references|"
    r"volunteer|leadership|summary|objective)\s*$",
    re.IGNORECASE,
)


def extract_projects(text: str) -> list[dict]:
    """
    Heuristic extraction of project titles and descriptions.

    Strategy:
      1. Find a line matching _PROJECT_SECTION
      2. Read lines until the next _OTHER_SECTION or end of text
      3. Lines that look like titles (short, capitalised, no trailing
         punctuation, no bullet chars) become project entries
      4. Following lines fill in the description
      5. For each project, run extract_skills on its text

    Deliberately conservative — returns nothing rather than garbled data.
    Phase 6 (Gemini) will produce a more accurate extraction.
    """
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    # Find projects section start
    section_start: int | None = None
    for i, line in enumerate(lines):
        if _PROJECT_SECTION.match(line):
            section_start = i + 1
            break

    if section_start is None:
        return []

    projects: list[dict] = []
    current: dict | None = None

    for i in range(section_start, len(lines)):
        line = lines[i]

        # Stop at next major section
        if _OTHER_SECTION.match(line):
            break

        # A line looks like a project title if it:
        #   - is shorter than 70 characters
        #   - starts with an uppercase letter
        #   - doesn't end with sentence-ending punctuation
        #   - isn't a bullet / pipe / URL
        is_title = (
            len(line) < 70
            and line[0].isupper()
            and not line.endswith((".", ",", ";", ":"))
            and not line.startswith(("•", "-", "–", "—", "*", "|", "/"))
            and "|" not in line
            and "http" not in line.lower()
        )

        if is_title:
            if current:
                projects.append(current)
            current = {"name": line, "description": "", "technologies": []}
        elif current and len(current["description"]) < 250:
            sep = " " if current["description"] else ""
            current["description"] += sep + line

    if current:
        projects.append(current)

    # Scan each project for tech keywords
    for project in projects:
        project_text = f"{project['name']} {project['description']}"
        project["technologies"] = extract_skills(project_text)

    return projects[:8]   # cap at 8 projects


# ── Main entry point ──────────────────────────────────────────────────────────

def parse_resume(pdf_bytes: bytes) -> dict:
    """
    Parse a PDF resume into a MongoDB-ready dict.

    Returns:
    {
        "extracted_skills": [...],
        "projects":         [...],
        "technologies":     [...],  # same as extracted_skills for now
        "raw_text":         "...",  # first 8000 chars, used by Phase 6 Gemini call
        "uploaded_at":      datetime
    }

    Raises ValueError if the PDF contains no extractable text.
    Any other exception propagates to the router.
    """
    raw_text = extract_text_from_pdf(pdf_bytes)
    skills   = extract_skills(raw_text)
    projects = extract_projects(raw_text)

    return {
        "extracted_skills": skills,
        "projects":         projects,
        "technologies":     skills,          # Gemini refines this in Phase 6
        "raw_text":         raw_text[:8000], # stored for Gemini — not returned to client
        "uploaded_at":      datetime.utcnow(),
    }
