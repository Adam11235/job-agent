import sqlite3
import json
from openai import OpenAI

# Setup LM Studio Client
client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")

def upgrade_job_database():
    """Adds match_score and match_reasoning columns if they don't exist yet."""
    conn = sqlite3.connect("job_agent.db")
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN match_score REAL")
        cursor.execute("ALTER TABLE jobs ADD COLUMN match_reasoning TEXT")
        conn.commit()
        print("🔧 Upgraded job_agent.db with matching columns.")
    except sqlite3.OperationalError:
        # Columns likely already exist
        pass
    finally:
        conn.close()

def load_candidate_profile():
    """Reads skills.db and formats the candidate profile into a clean string."""
    try:
        conn = sqlite3.connect('skills.db')
        cursor = conn.cursor()
        
        # Get IT Skills
        cursor.execute("SELECT skill_name, proficiency_level FROM it_skills")
        it_skills = ", ".join([f"{row[0]} ({row[1]}/5.0)" for row in cursor.fetchall()])
        
        # Get Experience
        cursor.execute("SELECT name, duration, company_name FROM experience")
        experience = "; ".join([f"{row[0]} at {row[2]} ({row[1]})" for row in cursor.fetchall()])
        
        # Get Education
        cursor.execute("SELECT university, major, degree FROM education")
        education = "; ".join([f"{row[0]} - {row[1]} ({row[2]})" for row in cursor.fetchall()])
        
        conn.close()
        
        profile = f"""
        EDUCATION: {education}
        EXPERIENCE: {experience}
        TECH SKILLS: {it_skills}
        """
        return profile.strip()
    except Exception as e:
        print(f"❌ Error loading skills.db: {e}. Did you run skills.py first?")
        return None

def evaluate_match(candidate_profile, job):
    """Sends the profile and job to LM Studio to get a match score."""
    
    # Safely truncate job details to fit in context window and save processing time
    job_details = f"""
    TITLE: {job['title']}
    REQUIREMENTS: {str(job['requirements'])[:1500]}
    EXTRA REQUIREMENTS: {str(job['extra_requirements'])[:1000]}
    DESCRIPTION: {str(job['description'])[:1500]}
    """

    system_prompt = """
    Jesteś bezlitosnym, korporacyjnym systemem ATS (Applicant Tracking System) oraz rygorystycznym Rekruterem IT.
    Porównaj PROFIL KANDYDATA z OFERTĄ PRACY. Oceń dopasowanie w skali od 0.0 (brak dopasowania) do 1.0 (idealne dopasowanie).
    
    ZASADY PUNKTACJI (BĄDŹ BARDZO SUROWY - MODELE ZAZWYCZAJ SĄ ZBYT OPTYMISTYCZNE):
    1. LATA DOŚWIADCZENIA (Główna Kara): Jeśli oferta wymaga np. 2-3 lat doświadczenia komercyjnego (Mid/Regular), a kandydat ma tylko staże (Internship) lub projekty uczelniane, natychmiast ODJMIJ 0.3 do 0.4 punktu z maksymalnej oceny.
    2. WYMAGANIA KLUCZOWE (Must-have): Jeśli kandydat nie ma w stacku technologii wymienionej jako główny wymóg, maksymalna ocena to 0.5.
    3. Skala Ocen:
       - 0.90 - 1.00: 100% zgodności stacku ORAZ wymaganych lat komercyjnego doświadczenia.
       - 0.70 - 0.89: Solidny match, brakuje tylko drobnych narzędzi "nice to have", lata doświadczenia się zgadzają.
       - 0.50 - 0.69: Kandydat Junior/Stażysta aplikujący na stanowisko Regular/Mid. Zna technologie, ale brakuje mu lat "w boju".
       - 0.00 - 0.49: Całkowity brak dopasowania lub gigantyczna przepaść w doświadczeniu (np. student aplikujący na Seniora).

    Zwróć TYLKO poprawny JSON. Żadnego markdown, żadnego tekstu pobocznego.
    {
      "match_score": 0.45,
      "reasoning": "Kandydat ma mocny stack w C/C++ i Pythonie, ale oferta wymaga 3 lat doświadczenia w branży Automotive, którego kandydat nie posiada (tylko doświadczenie stażowe)."
    }
    """

    user_prompt = f"--- CANDIDATE PROFILE ---\n{candidate_profile}\n\n--- JOB OFFER ---\n{job_details}"

    try:
        response = client.chat.completions.create(
            model="local-model",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=300
        )
        
        result_text = response.choices[0].message.content.strip()
        # Clean up in case the model adds markdown code blocks
        if result_text.startswith("```json"):
            result_text = result_text.replace("```json", "").replace("```", "").strip()
            
        result_json = json.loads(result_text)
        return result_json.get("match_score", 0.0), result_json.get("reasoning", "No reasoning provided.")
        
    except Exception as e:
        print(f"⚠️ Error evaluating job {job['id']}: {e}")
        return 0.0, "Evaluation failed."

def run_matcher():
    upgrade_job_database()
    profile = load_candidate_profile()
    
    if not profile:
        return

    conn = sqlite3.connect("job_agent.db")
    conn.row_factory = sqlite3.Row # Allows accessing columns by name
    cursor = conn.cursor()
    
    # Fetch jobs that haven't been scored yet and didn't fail scraping
    cursor.execute("SELECT * FROM jobs WHERE match_score IS NULL AND status != 'failed_scrape'")
    unscored_jobs = cursor.fetchall()
    
    if not unscored_jobs:
        print("✅ All jobs in the database have already been evaluated!")
        conn.close()
        return

    print(f"🧠 Found {len(unscored_jobs)} unscored jobs. Starting AI evaluation...")

    for job in unscored_jobs:
        print(f"\nEvaluating: {job['title']}...")
        score, reasoning = evaluate_match(profile, job)
        
        print(f"Score: {score}/1.0 -> {reasoning}")
        
        # Save score back to database
        cursor.execute('''
            UPDATE jobs 
            SET match_score = ?, match_reasoning = ? 
            WHERE id = ?
        ''', (score, reasoning, job['id']))
        conn.commit()

    conn.close()
    print("\n🎉 Evaluation complete!")

if __name__ == "__main__":
    run_matcher()