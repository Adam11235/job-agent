from fetch_mail import fetch_todays_emails
from mail_parser import parse_email
from calendar_scheduler import schedule_job_event 
from job_scraper import scrape_job_offer, save_to_database

def run_agent():
    print("🤖 Starting Job Agent...")
    print("📥 Fetching inbox...")
    emails = fetch_todays_emails()
    
    if not emails:
        print("No new emails to process today.")
        return

    print(f"Found {len(emails)} emails. Sending to Gemma for analysis...\n")
    
    for email in emails:
        subject = email['subject']
        snippet = email['content']
        
        print(f"--- Subject: {subject} ---")
        
        ai_result = parse_email(subject, snippet)
        
        if ai_result:
            if ai_result.get('is_rejection'):
                print("🛑 VERDICT: Job Rejection.")
                print(f"Role/Company: {ai_result.get('title')}")
                # TODO: Update the database entry for this job to status 'rejected'
                
            elif ai_result.get('is_actionable_job_alert'):
                print("📝 VERDICT: Actionable Job Offer Digest! (Buffering Links)")
                
                job_links = email.get('links', [])
                
                if not job_links:
                    print("⚠️ No valid job links found in email body.")
                    continue
                
                # 1. Append links to text file buffer
                with open("pending_links.txt", "a") as f:
                    for link in job_links:
                        f.write(link + "\n")
                print(f"✅ Buffered {len(job_links)} links to pending_links.txt")
                
            elif ai_result.get('is_actionable_job_alert'):
                print("📝 VERDICT: Actionable Job Offer Digest! (Routing to Scraper)")
                
                # Now we expect a list of links
                job_links = ai_result.get('job_links', [])
                
                if not job_links:
                    print("⚠️ No valid job links extracted by AI.")
                
                for link in job_links:
                    if link and link.startswith("http"):
                        scraped_data = scrape_job_offer(link)
                        save_to_database(scraped_data)
                
            elif ai_result.get('is_rubbish'):
                print("🗑️ VERDICT: Rubbish / Social Noise. Ignoring.")
                
            else:
                print("❌ VERDICT: Not job related.")

    print("\n🕸️ Starting Scraper from Buffer...")
    
    try:
        with open("pending_links.txt", "r") as f:
            all_links = [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        all_links = []

    if all_links:
        BATCH_SIZE = 10 # Change this to process more at once
        
        links_to_scrape = all_links[:BATCH_SIZE]
        remaining_links = all_links[BATCH_SIZE:]

        for link in links_to_scrape:
            scraped_data = scrape_job_offer(link)
            # Only save if data was returned (not skipped or failed)
            if scraped_data and scraped_data.get('status') != 'failed_scrape':
                save_to_database(scraped_data)

        # Overwrite buffer, dropping the links we just processed
        with open("pending_links.txt", "w") as f:
            for link in remaining_links:
                f.write(link + "\n")
                
        print(f"✅ Processed {len(links_to_scrape)} links. {len(remaining_links)} left in buffer.")

if __name__ == "__main__":
    run_agent()