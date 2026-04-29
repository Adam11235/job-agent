import sqlite3
import re
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup

DB_NAME = "job_agent.db"

def setup_database():
    """Creates the database and tables if they don't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE,
            title TEXT,
            description TEXT,
            requirements TEXT,
            extra_requirements TEXT,
            external_apply_link TEXT,
            contact_mail TEXT,
            contact_phone TEXT,
            company_address TEXT,
            remote_status TEXT,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

def extract_emails_and_phones(text):
    """Simple regex to find emails and basic phone numbers in text."""
    emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
    phones = re.findall(r'(?:\+48)?\s?\d{3}[-\s]?\d{3}[-\s]?\d{3}', text)
    return ", ".join(set(emails)), ", ".join(set(phones))

def scrape_job_offer(url):
    """Scrapes the job offer using Playwright, Stealth (v2), and BeautifulSoup."""
    print(f"🕸️ Scraping: {url}")
    
    # --- NEW V2 STEALTH WRAPPER ---
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            page.goto(url, timeout=30000)
            page.wait_for_selector('h1', timeout=15000)
            html = page.content()
        except Exception as e:
            print(f"❌ Failed or Blocked by Anti-Bot: {url}")
            browser.close()
            return {
                "link": url, "title": "Scrape Failed (Timeout/Blocked)", 
                "description": "", "requirements": "", "extra_requirements": "",
                "external_apply_link": "None", "contact_mail": "None", 
                "contact_phone": "None", "company_address": "None",
                "remote_status": "None", "status": "failed_scrape"
            }
            
        browser.close()

    # Parse the rendered HTML with BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    full_text = soup.get_text(separator=' ')
    contact_mail, contact_phone = extract_emails_and_phones(full_text)

    title = soup.find('h1').text.strip() if soup.find('h1') else "Unknown Title"
    
    # Extract Remote Status
    remote_status = "Office"
    if re.search(r'(?i)praca zdalna|100% remote|w pełni zdalna', full_text):
        remote_status = "Remote"
    elif re.search(r'(?i)praca hybrydowa|hybrid', full_text):
        remote_status = "Hybrid"

    # Extract Location / Address
    location_element = soup.find(attrs={"data-test": "text-workplace-address"}) or soup.find(attrs={"data-test": "text-region"})
    company_address = location_element.text.strip() if location_element else "Unknown Location"

    # Extract standard sections
    req_section = soup.find(attrs={"data-test": "section-requirements"})
    requirements = req_section.text.strip() if req_section else ""

    extra_req_section = soup.find(attrs={"data-test": "section-technologies-expected"})
    extra_reqs = extra_req_section.text.strip() if extra_req_section else ""
    
    # --- NEW FILTER ---
    if not extra_reqs:
        print(f"⏭️ Skipping: No extra requirements found for {url}")
        return None
    
    extra_req_section = soup.find(attrs={"data-test": "section-technologies-expected"})
    extra_reqs = extra_req_section.text.strip() if extra_req_section else ""
    
    desc_section = soup.find(attrs={"data-test": "section-responsibilities"})
    description = desc_section.text.strip() if desc_section else ""

    # Check for external apply link
    external_apply_link = "None"
    apply_button = soup.find('a', string=re.compile(r'(?i)Aplikuj na stronie pracodawcy'))
    if apply_button and apply_button.has_attr('href'):
        external_apply_link = apply_button['href']

    return {
        "link": url,
        "title": title,
        "description": description,
        "requirements": requirements,
        "extra_requirements": extra_reqs,
        "external_apply_link": external_apply_link,
        "contact_mail": contact_mail or "None",
        "contact_phone": contact_phone or "None",
        "company_address": company_address,
        "remote_status": remote_status,
        "status": "new offer"
    }

def save_to_database(job_data):
    """Saves the scraped data to SQLite, ignoring duplicates."""
    if not job_data: return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO jobs (
                link, title, description, requirements, extra_requirements, 
                external_apply_link, contact_mail, contact_phone, 
                company_address, remote_status, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            job_data['link'], job_data['title'], job_data['description'], 
            job_data['requirements'], job_data['extra_requirements'], 
            job_data['external_apply_link'], job_data['contact_mail'], 
            job_data['contact_phone'], job_data['company_address'], 
            job_data['remote_status'], job_data['status']
        ))
        conn.commit()
        print(f"💾 Saved to DB: {job_data['title']} ({job_data['remote_status']})")
    except sqlite3.IntegrityError:
        print(f"⏩ Duplicate offer skipped.")
    finally:
        conn.close()

# Initialize DB when the script is imported
setup_database()