import os, smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()
usuario = os.getenv("SMTP_EMAIL")
senha = os.getenv("SMTP_APP_PASSWORD")

msg = MIMEText("Teste simples.")
msg["Subject"] = "Teste AAPM"
msg["From"] = usuario
msg["To"] = usuario

with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
    s.login(usuario, senha)
    s.sendmail(usuario, [usuario], msg.as_string())
print("Enviado!")