"""
seed_data.py - Generates a realistic, reproducible dataset for MediTrack.

Result (random.seed fixed, so every run gives the same data):
    8 doctors, 21 medicines, 45 patients, ~200 appointments
"""
import random
from datetime import datetime, timedelta

import config

TODAY = datetime(2026, 10, 18)          # reference "today" for the seed data
WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ----------------------------------------------------------------------------
# Reference data
# ----------------------------------------------------------------------------
DOCTORS = [
    # code, name, specialization, qualifications, exp, fee, days
    ("DOC001", "Dr. Ananya Sharma", "General Medicine", ["MBBS", "MD (Medicine)"], 12, 500, ["Mon", "Tue", "Wed", "Thu", "Fri"]),
    ("DOC002", "Dr. Rajesh Verma", "General Medicine", ["MBBS", "DNB"], 20, 600, ["Mon", "Wed", "Fri", "Sat"]),
    ("DOC003", "Dr. Harpreet Singh Gill", "Cardiology", ["MBBS", "MD", "DM (Cardiology)"], 18, 1200, ["Tue", "Thu", "Sat"]),
    ("DOC004", "Dr. Meera Kapoor", "Dermatology", ["MBBS", "MD (Dermatology)"], 9, 800, ["Mon", "Tue", "Thu", "Fri"]),
    ("DOC005", "Dr. Sandeep Arora", "Pediatrics", ["MBBS", "MD (Pediatrics)"], 15, 700, ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]),
    ("DOC006", "Dr. Gurpreet Kaur Sidhu", "Orthopedics", ["MBBS", "MS (Ortho)"], 14, 900, ["Wed", "Thu", "Fri", "Sat"]),
    ("DOC007", "Dr. Vikram Malhotra", "ENT", ["MBBS", "MS (ENT)"], 11, 750, ["Mon", "Tue", "Wed", "Fri"]),
    ("DOC008", "Dr. Simran Bedi", "Gynecology", ["MBBS", "MS (OBG)"], 16, 1000, ["Mon", "Tue", "Thu", "Sat"]),
]

# name, category, unit_price, stock, reorder_level, rx_required
MEDICINES = [
    ("Paracetamol 500mg", "Analgesic", 2.0, 600, 100, False),
    ("Paracetamol Syrup 125mg/5ml", "Analgesic", 48.0, 70, 25, False),
    ("Ibuprofen 400mg", "Analgesic", 3.5, 320, 80, False),
    ("Diclofenac Gel", "Analgesic", 85.0, 18, 30, False),          # LOW STOCK
    ("Amoxicillin 500mg", "Antibiotic", 9.0, 260, 60, True),
    ("Azithromycin 500mg", "Antibiotic", 22.0, 140, 50, True),
    ("Doxycycline 100mg", "Antibiotic", 11.0, 90, 40, True),
    ("Cetirizine 10mg", "Antihistamine", 2.5, 500, 100, False),
    ("Pantoprazole 40mg", "Antacid", 6.5, 380, 80, True),
    ("Metformin 500mg", "Antidiabetic", 1.8, 700, 150, True),
    ("Amlodipine 5mg", "Antihypertensive", 2.2, 450, 100, True),
    ("Losartan 50mg", "Antihypertensive", 4.0, 12, 60, True),       # LOW STOCK
    ("Atorvastatin 10mg", "Statin", 5.0, 400, 90, True),
    ("Calamine Lotion", "Dermatological", 70.0, 45, 20, False),
    ("Zinc Syrup", "Supplement", 55.0, 60, 25, False),
    ("Vitamin D3 60K", "Supplement", 28.0, 25, 40, False),          # LOW STOCK
    ("Calcium + D3", "Supplement", 7.0, 330, 80, False),
    ("Montelukast 10mg", "Respiratory", 14.0, 210, 50, True),
    ("Salbutamol Inhaler", "Respiratory", 140.0, 38, 15, True),
    ("ORS Sachet", "Rehydration", 21.0, 150, 50, False),
    ("Levothyroxine 50mcg", "Hormonal", 3.0, 300, 70, True),
]
PRICE = {m[0]: m[2] for m in MEDICINES}

# Clinical templates per specialization:
# (diagnosis, symptoms, [(medicine, dosage, frequency, doses_per_day, days)])   doses_per_day 0 => 1 unit pack
CLINICAL = {
    "General Medicine": [
        ("Viral Fever", ["fever", "body ache", "headache"],
         [("Paracetamol 500mg", "1 tablet", "Thrice daily", 3, 5), ("Cetirizine 10mg", "1 tablet", "Once daily at night", 1, 5)]),
        ("Acute Gastritis", ["abdominal pain", "acidity", "nausea"],
         [("Pantoprazole 40mg", "1 tablet", "Once daily before breakfast", 1, 14), ("ORS Sachet", "1 sachet", "As needed", 0, 3)]),
        ("Upper Respiratory Infection", ["cough", "sore throat", "runny nose"],
         [("Azithromycin 500mg", "1 tablet", "Once daily", 1, 3), ("Cetirizine 10mg", "1 tablet", "Once daily at night", 1, 5)]),
        ("Type 2 Diabetes Follow-up", ["fatigue", "frequent urination"],
         [("Metformin 500mg", "1 tablet", "Twice daily after meals", 2, 30)]),
    ],
    "Cardiology": [
        ("Hypertension", ["headache", "dizziness"],
         [("Amlodipine 5mg", "1 tablet", "Once daily", 1, 30), ("Losartan 50mg", "1 tablet", "Once daily", 1, 30)]),
        ("Dyslipidemia", ["routine check-up", "family history"],
         [("Atorvastatin 10mg", "1 tablet", "Once daily at night", 1, 30)]),
    ],
    "Dermatology": [
        ("Allergic Dermatitis", ["itching", "skin rash"],
         [("Cetirizine 10mg", "1 tablet", "Once daily", 1, 7), ("Calamine Lotion", "Apply locally", "Twice daily", 0, 7)]),
        ("Acne Vulgaris", ["pimples", "oily skin"],
         [("Doxycycline 100mg", "1 capsule", "Once daily", 1, 21)]),
    ],
    "Pediatrics": [
        ("Childhood Viral Fever", ["fever", "poor appetite"],
         [("Paracetamol Syrup 125mg/5ml", "5 ml", "Thrice daily", 0, 4)]),
        ("Acute Diarrhea", ["loose motions", "dehydration"],
         [("ORS Sachet", "1 sachet", "After each loose stool", 0, 3), ("Zinc Syrup", "5 ml", "Once daily", 0, 14)]),
        ("Childhood Asthma", ["wheezing", "night cough"],
         [("Montelukast 10mg", "1/2 tablet", "Once daily at night", 1, 30), ("Salbutamol Inhaler", "2 puffs", "As needed", 0, 30)]),
    ],
    "Orthopedics": [
        ("Lumbar Spondylosis", ["back pain", "stiffness"],
         [("Ibuprofen 400mg", "1 tablet", "Twice daily after meals", 2, 7), ("Diclofenac Gel", "Apply locally", "Twice daily", 0, 10)]),
        ("Vitamin D Deficiency", ["bone pain", "fatigue"],
         [("Vitamin D3 60K", "1 sachet", "Once weekly", 0, 56), ("Calcium + D3", "1 tablet", "Once daily", 1, 60)]),
    ],
    "ENT": [
        ("Allergic Rhinitis", ["sneezing", "nasal block"],
         [("Montelukast 10mg", "1 tablet", "Once daily at night", 1, 14), ("Cetirizine 10mg", "1 tablet", "Once daily", 1, 14)]),
        ("Acute Sinusitis", ["facial pain", "nasal discharge"],
         [("Amoxicillin 500mg", "1 capsule", "Thrice daily", 3, 5)]),
    ],
    "Gynecology": [
        ("PCOS", ["irregular periods", "weight gain"],
         [("Metformin 500mg", "1 tablet", "Twice daily after meals", 2, 30)]),
        ("Hypothyroidism", ["fatigue", "weight gain", "hair fall"],
         [("Levothyroxine 50mcg", "1 tablet", "Empty stomach, morning", 1, 30)]),
    ],
}

MALE_FIRST = ["Aman", "Rohit", "Gurdeep", "Karan", "Manpreet", "Vishal", "Arjun", "Harsh", "Jasvir", "Nikhil", "Pardeep", "Tarun"]
FEMALE_FIRST = ["Simran", "Priya", "Jaspreet", "Kavya", "Navneet", "Pooja", "Riya", "Anjali", "Mehak", "Sukhmani", "Ishita", "Ritu"]
LAST = ["Singh", "Kaur", "Sharma", "Gill", "Kumar", "Dhillon", "Mehra", "Chopra", "Bajwa", "Sandhu", "Garg", "Thakur", "Walia"]
CITIES = [("Amritsar", "143001"), ("Jalandhar", "144001"), ("Ludhiana", "141001"),
          ("Phagwara", "144401"), ("Patiala", "147001"), ("Kapurthala", "144601")]
BLOOD = ["A+", "A-", "B+", "B-", "AB+", "O+", "O+", "O-", "B+", "A+"]
ALLERGIES = ["Penicillin", "Dust", "Pollen", "Peanuts", "Sulfa drugs", "Lactose"]
CHRONIC = ["Hypertension", "Type 2 Diabetes", "Asthma", "Hypothyroidism", "Arthritis"]
PAY_MODES = ["Cash", "UPI", "UPI", "Card", "Insurance"]
REASONS = {
    "General Medicine": ["Fever and body ache", "Stomach pain", "Cough and cold", "Routine check-up"],
    "Cardiology": ["Chest discomfort", "BP monitoring", "Cholesterol review"],
    "Dermatology": ["Skin rash", "Acne treatment", "Itching on arms"],
    "Pediatrics": ["Child has fever", "Loose motions", "Night cough in child"],
    "Orthopedics": ["Lower back pain", "Knee pain", "Weakness and bone pain"],
    "ENT": ["Blocked nose", "Sinus pain", "Frequent sneezing"],
    "Gynecology": ["Irregular periods", "Thyroid follow-up", "General consultation"],
}
SLOTS = [f"{h:02d}:{m:02d}" for h in range(9, 17) for m in (0, 30) if (h, m) not in [(13, 0), (13, 30)]]


def _age(dob, ref=TODAY):
    return (ref - dob).days / 365.25


def build_doctors():
    docs = []
    for i, (code, name, spec, quals, exp, fee, days) in enumerate(DOCTORS):
        slug = name.lower().replace("dr. ", "").replace(" ", ".")
        docs.append({
            "doctor_code": code, "name": name, "specialization": spec,
            "qualifications": quals, "experience_years": exp, "consultation_fee": fee,
            "phone": f"98{15000000 + i * 7919:08d}"[:10],
            "email": f"{slug}@meditrack.in", "available_days": days,
            "is_active": True, "joined_on": datetime(2024 - i % 3, 1 + i, 10),
        })
    return docs


def build_medicines():
    return [{"name": n, "category": c, "unit_price": p, "stock_quantity": s,
             "reorder_level": r, "requires_prescription": rx}
            for n, c, p, s, r, rx in MEDICINES]


def build_patients(rng, n=45):
    patients, used_phones = [], set()
    for i in range(1, n + 1):
        gender = rng.choice(["Male", "Female"])
        first = rng.choice(MALE_FIRST if gender == "Male" else FEMALE_FIRST)
        last = rng.choice(LAST)
        # ensure a healthy mix: first 9 patients are children, rest adults/seniors
        if i <= 9:
            dob = TODAY - timedelta(days=rng.randint(1 * 365, 13 * 365))
        else:
            dob = TODAY - timedelta(days=rng.randint(18 * 365, 80 * 365))
        phone = None
        while phone is None or phone in used_phones:
            phone = f"{rng.choice('6789')}{rng.randint(0, 999999999):09d}"
        used_phones.add(phone)
        city, pin = rng.choice(CITIES)
        doc = {
            "patient_code": f"PAT{i:04d}",
            "name": f"{first} {last}",
            "gender": gender,
            "date_of_birth": dob,
            "blood_group": rng.choice(BLOOD),
            "phone": phone,
            "email": f"{first.lower()}.{last.lower()}{i}@example.com",
            "address": {"street": f"House {rng.randint(1, 400)}, Sector {rng.randint(1, 40)}",
                        "city": city, "state": "Punjab", "pincode": pin},
            "emergency_contact": {"name": f"{rng.choice(MALE_FIRST)} {last}",
                                  "phone": f"9{rng.randint(0, 999999999):09d}",
                                  "relation": rng.choice(["Father", "Mother", "Spouse", "Brother"])},
            "allergies": rng.sample(ALLERGIES, 1) if rng.random() < 0.35 else [],
            "chronic_conditions": rng.sample(CHRONIC, rng.choice([1, 1, 2])) if (i > 9 and _age(dob) > 40 and rng.random() < 0.5) else [],
            "is_active": True,
            "registered_on": datetime(2025, rng.randint(1, 12), rng.randint(1, 28)),
        }
        patients.append(doc)
    return patients


def _eligible(spec, patients):
    if spec == "Pediatrics":
        return [p for p in patients if _age(p["date_of_birth"]) < 14]
    adults = [p for p in patients if _age(p["date_of_birth"]) >= 14]
    if spec == "Gynecology":
        return [p for p in adults if p["gender"] == "Female"]
    return adults


def build_appointments(rng, doctors, patients, n=200):
    """doctors / patients must already contain their MongoDB _id values."""
    appts, used_keys, seq = [], set(), 0
    medicine_price = PRICE
    start, end = datetime(2026, 1, 5), datetime(2026, 11, 14)
    span = (end - start).days
    attempts = 0
    while len(appts) < n and attempts < n * 20:
        attempts += 1
        doc = rng.choice(doctors)
        pool = _eligible(doc["specialization"], patients)
        pat = rng.choice(pool)
        date = start + timedelta(days=rng.randint(0, span))
        if WEEKDAY_NAMES[date.weekday()] not in doc["available_days"]:
            continue
        slot = rng.choice(SLOTS)
        key = (doc["_id"], date, slot)
        if key in used_keys:
            continue
        used_keys.add(key)
        seq += 1

        if date < TODAY:
            status = rng.choices(["Completed", "Cancelled", "No-Show"], [78, 12, 10])[0]
        else:
            status = rng.choices(["Scheduled", "Cancelled"], [90, 10])[0]

        spec = doc["specialization"]
        a = {
            "appointment_code": f"APT{seq:05d}",
            "patient_id": pat["_id"], "doctor_id": doc["_id"],
            "appointment_date": date, "time_slot": slot, "status": status,
            "reason": rng.choice(REASONS[spec]),
            "created_at": date - timedelta(days=rng.randint(1, 14), hours=-rng.randint(0, 5)),
        }
        if status == "Completed":
            diag, symptoms, meds = rng.choice(CLINICAL[spec])
            items, med_total = [], 0.0
            for name, dosage, freq, per_day, days in meds:
                qty = per_day * days if per_day else 1
                items.append({"medicine_name": name, "dosage": dosage, "frequency": freq,
                              "duration_days": days, "quantity": qty,
                              "unit_price": medicine_price[name]})
                med_total += qty * medicine_price[name]
            fee = doc["consultation_fee"]
            a.update({
                "symptoms": symptoms, "diagnosis": diag, "prescription": items,
                "consultation_fee": fee, "medicine_charges": round(med_total, 2),
                "payment": {"mode": rng.choice(PAY_MODES),
                            "status": rng.choices(["Paid", "Pending"], [92, 8])[0],
                            "amount": round(fee + med_total, 2)},
            })
        elif status == "Cancelled":
            a["cancellation_reason"] = rng.choice(["Patient unavailable", "Doctor on leave",
                                                   "Feeling better", "Rescheduled by patient"])
        appts.append(a)
    return appts


def seed(db, n_patients=45, n_appointments=200):
    """Insert the full dataset into an (already set-up) database."""
    rng = random.Random(config.SEED)

    db.doctors.insert_many(build_doctors())
    db.medicines.insert_many(build_medicines())
    db.patients.insert_many(build_patients(rng, n_patients))

    doctors = list(db.doctors.find())
    patients = list(db.patients.find())
    appointments = build_appointments(rng, doctors, patients, n_appointments)
    db.appointments.insert_many(appointments)

    # Sequence generator used by crud_operations.book_appointment()
    db.counters.replace_one({"_id": "appointment_code"}, {"_id": "appointment_code", "seq": len(appointments)}, upsert=True)

    return {
        "doctors": db.doctors.count_documents({}),
        "medicines": db.medicines.count_documents({}),
        "patients": db.patients.count_documents({}),
        "appointments": db.appointments.count_documents({}),
    }
