import json
from openai import OpenAI

client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

def parse_email(subject, snippet):
    
    system_prompt = """
    You are an email parser for a job seeker. Output ONLY valid JSON. No markdown.
    {
      "is_active_process": true/false, 
      "is_rejection": true/false,
      "is_actionable_job_alert": true/false,
      "is_rubbish": true/false,
      "event_type": "technical_test", "interview", or null,
      "start_datetime": "ISO 8601 string or null",
      "end_datetime": "ISO 8601 string or null",
      "title": "Role or Company Name",
      "meeting_link": "Meeting URL or null"
    }
    """
    
    raw_prompt = f"Subject: {subject}\nSnippet: {snippet}"
    user_prompt = raw_prompt[:16000]

    response = client.chat.completions.create(
        model="local-model", # Ensure this matches your loaded model in LM Studio
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1, 
        max_tokens=800
    )
    
    raw_output = response.choices[0].message.content.strip()
    
    try:
        # Strip markdown if the model hallucinates it despite instructions
        if raw_output.startswith("```json"):
            raw_output = raw_output[7:-3].strip()
        return json.loads(raw_output)
    except json.JSONDecodeError:
        print(f"Failed to parse JSON: {raw_output}")
        return None

# Test it
if __name__ == "__main__":
    test_subject = "Invitation to Technical Interview - Python Developer"
    test_snippet = "We would like to invite you for a technical interview on April 22nd, 2026 from 10:00 AM to 11:30 AM CEST."
    print(parse_email(test_subject, test_snippet))