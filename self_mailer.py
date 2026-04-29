import smtplib
import os
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

# Użyj nowych nazw zmiennych, aby Windows nie wstawiał tam Twojego imienia
EMAIL_ADDRESS = os.getenv('MY_MAIL')
EMAIL_PASSWORD = os.getenv('MY_PASS')

msg = EmailMessage()
msg['Subject'] = 'Python Developer - Job Interview - 15th May 2026'
msg['From'] = EMAIL_ADDRESS
msg['To'] = 'the3017@gmail.com'
msg.set_content('ily kitten')
try:
    # Port 465 WYMAGA SMTP_SSL i NIE używa starttls()
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)
        print("Success! Email sent.")
except Exception as e:
    print(f"Login Failed: {e}")