from flask import Flask, render_template, request, redirect, session
from dotenv import load_dotenv
from groq import Groq
from fpdf import FPDF
import sqlite3
import os
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ---------------- DATABASE ----------------
def create_database():
    conn = sqlite3.connect('patients.db')
    c = conn.cursor()

    c.execute('''
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fullname TEXT,
        email TEXT UNIQUE,
        password TEXT
    )
    ''')

    conn.commit()
    conn.close()


create_database()


# ---------------- HOME ----------------
@app.route('/')
def home():
    return render_template('home.html')


# ---------------- REGISTER ----------------
@app.route('/register')
def register():
    return render_template('register.html')


@app.route('/register_user', methods=['POST'])
def register_user():
    fullname = request.form['fullname']
    email = request.form['email']
    password = request.form['password']

    conn = sqlite3.connect('patients.db')
    c = conn.cursor()

    try:
        c.execute(
            "INSERT INTO users(fullname, email, password) VALUES (?, ?, ?)",
            (fullname, email, password)
        )
        conn.commit()
        conn.close()
        return redirect('/login')

    except sqlite3.IntegrityError:
        conn.close()
        return "Email already exists! Please login."


# ---------------- LOGIN ----------------
@app.route('/login')
def login():
    return render_template('login.html')


@app.route('/login_user', methods=['POST'])
def login_user():
    email = request.form['email']
    password = request.form['password']

    conn = sqlite3.connect('patients.db')
    c = conn.cursor()

    c.execute(
        "SELECT * FROM users WHERE email=? AND password=?",
        (email, password)
    )

    user = c.fetchone()
    conn.close()

    if user:
        session['user'] = user[1]
        return redirect('/dashboard')
    else:
        return "Invalid Email or Password"


# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')

    return render_template(
        'dashboard.html',
        username=session['user']
    )


# ---------------- AI REPORT GENERATION ----------------
@app.route('/submit', methods=['POST'])
def submit():
    if 'user' not in session:
        return redirect('/login')

    name = request.form['name']
    age = request.form['age']
    gender = request.form['gender']
    symptoms = request.form['symptoms']
    duration = request.form['duration']
    history = request.form['history']
    medicines = request.form['medicines']
    allergies = request.form['allergies']

    prompt = f"""
Generate a professional doctor-ready patient intake summary.

Patient Details:
Name: {name}
Age: {age}
Gender: {gender}

Symptoms:
{symptoms}

Duration:
{duration}

Medical History:
{history}

Current Medicines:
{medicines}

Allergies:
{allergies}

Provide the output in this format:

1. Patient Overview
2. Main Symptoms
3. Duration of Symptoms
4. Medical History
5. Current Medicines
6. Allergies
7. Severity Level: Mild / Moderate / Critical
8. Possible Condition
9. Suggested Doctor Specialist
10. Doctor Notes

Important:
Do not give a final diagnosis.
Only generate a pre-consultation summary for doctor review.
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a medical intake assistant. Do not provide final diagnosis. Generate doctor-ready intake summaries only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        summary = response.choices[0].message.content

    except Exception as e:
        return f"AI Error: {e}"

    if not os.path.exists("reports"):
        os.makedirs("reports")

    safe_name = name.replace(" ", "_")
    filename = f"reports/{safe_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Patient Symptom Intake Report", ln=True, align="C")

    pdf.ln(10)
    pdf.set_font("Arial", size=12)

    pdf.multi_cell(0, 10, f"""
Patient Name: {name}
Age: {age}
Gender: {gender}

Symptoms: {symptoms}
Duration: {duration}

Medical History: {history}
Current Medicines: {medicines}
Allergies: {allergies}

AI Generated Summary:

{summary}
""")

    pdf.output(filename)

    return render_template(
        'result.html',
        summary=summary,
        report=filename
    )


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')


# ---------------- RUN APP ----------------
if __name__ == '__main__':
    app.run(debug=True, port=5000)