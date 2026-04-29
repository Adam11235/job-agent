import sqlite3
import json
from openai import OpenAI
from playwright.sync_api import sync_playwright

# Setup LM Studio Client
client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")

def get_job_and_profile(job_id):
    """Fetches the specific job and builds the candidate profile."""
    # 1. Get Job
    conn_jobs = sqlite3.connect("job_agent.db")
    conn_jobs.row_factory = sqlite3.Row
    cursor_jobs = conn_jobs.cursor()
    cursor_jobs.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job = cursor_jobs.fetchone()
    conn_jobs.close()

    # 2. Get Profile
    conn_skills = sqlite3.connect("skills.db")
    cursor_skills = conn_skills.cursor()
    
    cursor_skills.execute("SELECT skill_name FROM it_skills")
    skills = [row[0] for row in cursor_skills.fetchall()]
    
    cursor_skills.execute("SELECT name, company_name FROM experience")
    experience = [f"{row[0]} at {row[1]}" for row in cursor_skills.fetchall()]
    
    conn_skills.close()

    return job, {"skills": skills, "experience": experience}

def analyze_union(job, profile):
    """AI function to extract common and uncommon elements."""
    print("🧠 Analyzing skill gaps and intersections...")
    
    system_prompt = """
    You are an analytical ATS engine. Compare the CANDIDATE PROFILE to the JOB REQUIREMENTS.
    Separate the skills and experience into 'common' (what the candidate has that the job wants) 
    and 'uncommon' (what the job wants but the candidate lacks).
    
    Output ONLY valid JSON. No markdown formatting.
    {
        "common_skills": ["skill1", "skill2"],
        "common_experience": ["exp1"],
        "uncommon_skills": ["missing1", "missing2"],
        "uncommon_experience": ["missing_exp1"]
    }
    """

    user_prompt = f"""
    --- CANDIDATE PROFILE ---
    Skills: {', '.join(profile['skills'])}
    Experience: {'; '.join(profile['experience'])}

    --- JOB REQUIREMENTS ---
    {job['requirements']}
    {job['extra_requirements']}
    """

    response = client.chat.completions.create(
        model="local-model",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1,
        max_tokens=500
    )
    
    result_text = response.choices[0].message.content.strip()
    if result_text.startswith("```json"):
        result_text = result_text.replace("```json", "").replace("```", "").strip()
        
    return json.loads(result_text)

def generate_cover_letter(union_data, job):
    """Generates the text for the cover letter based on your exact structure."""
    
    com_exp = ", ".join(union_data.get('common_experience', [])) or "relevant foundational experience"
    com_skills = ", ".join(union_data.get('common_skills', [])) or "strong technical fundamentals"
    
    uncom_exp = ", ".join(union_data.get('uncommon_experience', [])) or "new industry challenges"
    uncom_skills = ", ".join(union_data.get('uncommon_skills', [])) or "your specific tech stack"

    letter = f"""
Dear Hiring Manager at {job['title'].split()[-1] if job['title'] else 'the Company'},

I am super motivated to join your team. I have {com_exp} and I have proven previously to have {com_skills}. 

I am eager to work on {uncom_exp} and learn {uncom_skills}. I believe my strong foundational skills will allow me to onboard quickly and contribute to your projects.

Best regards,
Adam
    """
    return letter.strip()

def generate_cv_html(union_data, profile):
    """Asks the AI to format an HTML Europass CV using strictly existing data."""
    print("📝 Drafting strict 1-page HTML CV...")
    
    system_prompt = """
    You are a CV formatting engine. Create a clean, modern HTML document formatted like a Europass CV.
    
    STRICT RULES:
    1. ONE PAGE ONLY (keep it concise).
    2. DO NOT CREATE NEW SKILLS. DO NOT CREATE NEW EXPERIENCE. Use strictly the provided data.
    3. Make it highly readable and formatted for an A4 sheet.
    4. Include embedded CSS for styling (fonts, margins, colors).
    5. Highlight the "Common Skills" as key strengths.
    
    Return ONLY the raw HTML code. Do not wrap it in ```html markdown tags.
    """

    user_prompt = f"""
    Candidate Name: Adam
    
    All Available Skills: {', '.join(profile['skills'])}
    All Available Experience: {'; '.join(profile['experience'])}
    
    Highlighted Common Skills for this specific job: {', '.join(union_data.get('common_skills', []))}
    """

    response = client.chat.completions.create(
        model="local-model",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2, # Slightly higher for creative HTML formatting
        max_tokens=2000
    )
    
    html = response.choices[0].message.content.strip()
    if html.startswith("```html"):
        html = html.replace("```html", "").replace("```", "").strip()
    return html

def create_pdfs(job_id):
    """Orchestrates the process and uses Playwright to print to PDF."""
    job, profile = get_job_and_profile(job_id)
    if not job:
        print("❌ Job not found.")
        return

    # 1. AI Union
    union_data = analyze_union(job, profile)
    
    # 2. Cover Letter
    cover_letter = generate_cover_letter(union_data, job)
    print("\n--- COVER LETTER GENERATED ---")
    print(cover_letter)
    print("------------------------------\n")

    # 3. CV HTML
    cv_html = generate_cv_html(union_data, profile)

    # 4. Convert HTML to PDF using Playwright
    print("🖨️  Converting HTML to PDF...")
    pdf_filename = f"CV_Adam_Job_{job_id}.pdf"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(cv_html)
        # Print perfectly to A4 format
        page.pdf(path=pdf_filename, format="A4", print_background=True, margin={"top": "1cm", "bottom": "1cm", "left": "1cm", "right": "1cm"})
        browser.close()

    print(f"✅ Success! Saved your tailored CV as {pdf_filename}")

if __name__ == "__main__":
    # Replace '1' with whichever job ID you want to apply for!
    create_pdfs(job_id=1)