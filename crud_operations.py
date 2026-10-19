"""
crud_operations.py - Create / Read / Update / Delete operations for MediTrack (PyMongo).

Every function takes the `db` handle as first argument so it can be called from
main.py, from a notebook, or from the viva demo.
"""
from datetime import datetime

from pymongo import ASCENDING, DESCENDING, UpdateOne, ReturnDocument
from pymongo.errors import DuplicateKeyError, WriteError

from utils import show

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _parse_date(value):
    return value if isinstance(value, datetime) else datetime.strptime(value, "%Y-%m-%d")


# =============================================================================
# CREATE
# =============================================================================
def add_doctor(db, doctor: dict):
    """insert_one - add a new doctor. Raises WriteError if validation fails."""
    doctor.setdefault("is_active", True)
    doctor.setdefault("joined_on", datetime.now())
    return db.doctors.insert_one(doctor).inserted_id


def register_patient(db, patient: dict):
    """insert_one - register a patient. patient_code / phone must be unique."""
    patient.setdefault("is_active", True)
    patient.setdefault("allergies", [])
    patient.setdefault("chronic_conditions", [])
    patient.setdefault("registered_on", datetime.now())
    return db.patients.insert_one(patient).inserted_id


def add_medicines(db, medicines: list):
    """insert_many - bulk load of catalogue items (ordered=False continues on errors)."""
    return db.medicines.insert_many(medicines, ordered=False).inserted_ids


def next_appointment_code(db):
    """Atomic auto-increment using find_one_and_update + $inc (safe under concurrency)."""
    counter = db.counters.find_one_and_update(
        {"_id": "appointment_code"}, {"$inc": {"seq": 1}},
        upsert=True, return_document=ReturnDocument.AFTER)
    return f"APT{counter['seq']:05d}"


def book_appointment(db, patient_code, doctor_code, date, time_slot, reason, symptoms=None):
    """
    Business-logic insert:
      1. resolve patient & doctor by their business codes
      2. check the doctor works on that weekday
      3. insert; the partial unique index rejects a double-booking
    Returns (ok: bool, message: str).
    """
    date = _parse_date(date)
    patient = db.patients.find_one({"patient_code": patient_code, "is_active": True})
    doctor = db.doctors.find_one({"doctor_code": doctor_code, "is_active": True})
    if not patient or not doctor:
        return False, "Patient or doctor not found / inactive."
    if WEEKDAYS[date.weekday()] not in doctor["available_days"]:
        return False, f"{doctor['name']} does not consult on {WEEKDAYS[date.weekday()]}."

    appt = {
        "appointment_code": next_appointment_code(db),
        "patient_id": patient["_id"], "doctor_id": doctor["_id"],
        "appointment_date": date, "time_slot": time_slot, "status": "Scheduled",
        "reason": reason, "symptoms": symptoms or [],
        "created_at": datetime.now(),
    }
    try:
        db.appointments.insert_one(appt)
    except DuplicateKeyError:
        return False, f"Slot {time_slot} on {date:%d-%b-%Y} is already booked for {doctor['name']}."
    except WriteError as e:
        return False, f"Validation failed: {e.details.get('errmsg', e)}"
    return True, f"Booked {appt['appointment_code']} with {doctor['name']} on {date:%d-%b-%Y} at {time_slot}."


# =============================================================================
# READ
# =============================================================================
def find_patient_by_code(db, code):
    """find_one with a projection (hide internal id and timestamps)."""
    return db.patients.find_one({"patient_code": code}, {"_id": 0, "updated_at": 0})


def search_patients_by_name(db, text):
    """Case-insensitive regex search."""
    return list(db.patients.find({"name": {"$regex": text, "$options": "i"}},
                                 {"_id": 0, "patient_code": 1, "name": 1, "phone": 1}))


def doctors_by_specialization(db, spec):
    """Filter + sort (highest experience first)."""
    return list(db.doctors.find({"specialization": spec, "is_active": True},
                                {"_id": 0, "doctor_code": 1, "name": 1, "experience_years": 1,
                                 "consultation_fee": 1}).sort("experience_years", DESCENDING))


def patients_with_allergy(db, allergy):
    """Array membership match - matches if the array contains the value."""
    return list(db.patients.find({"allergies": allergy},
                                 {"_id": 0, "patient_code": 1, "name": 1, "allergies": 1}))


def patients_in_cities(db, cities, min_age_dob=None):
    """$in operator (+ optional $lte on date_of_birth, i.e. older than a given age)."""
    q = {"address.city": {"$in": cities}}
    if min_age_dob:
        q["date_of_birth"] = {"$lte": min_age_dob}
    return list(db.patients.find(q, {"_id": 0, "patient_code": 1, "name": 1, "address.city": 1}))


def appointments_in_range(db, start, end, status=None):
    """Range query with $gte / $lt on dates."""
    q = {"appointment_date": {"$gte": _parse_date(start), "$lt": _parse_date(end)}}
    if status:
        q["status"] = status
    return list(db.appointments.find(q, {"_id": 0, "appointment_code": 1, "appointment_date": 1,
                                         "time_slot": 1, "status": 1}).sort("appointment_date", ASCENDING))


def upcoming_schedule_for_doctor(db, doctor_code, from_date=None, limit=5):
    """Uses the compound index (doctor_id, appointment_date)."""
    doctor = db.doctors.find_one({"doctor_code": doctor_code})
    return list(db.appointments.find(
        {"doctor_id": doctor["_id"], "status": "Scheduled",
         "appointment_date": {"$gte": _parse_date(from_date or datetime.now())}},
        {"_id": 0, "appointment_code": 1, "appointment_date": 1, "time_slot": 1, "reason": 1}
    ).sort([("appointment_date", ASCENDING), ("time_slot", ASCENDING)]).limit(limit))


def patient_history(db, patient_code):
    """Visit history of one patient - uses (patient_id, appointment_date desc) index."""
    p = db.patients.find_one({"patient_code": patient_code})
    return list(db.appointments.find(
        {"patient_id": p["_id"], "status": "Completed"},
        {"_id": 0, "appointment_code": 1, "appointment_date": 1, "diagnosis": 1,
         "prescription.medicine_name": 1}).sort("appointment_date", DESCENDING))


def appointments_with_medicine(db, medicine_name):
    """$elemMatch on an embedded array of sub-documents."""
    return list(db.appointments.find(
        {"prescription": {"$elemMatch": {"medicine_name": medicine_name, "quantity": {"$gte": 10}}}},
        {"_id": 0, "appointment_code": 1, "diagnosis": 1}).limit(5))


def low_stock_medicines(db):
    """$expr lets us compare two fields of the SAME document."""
    return list(db.medicines.find({"$expr": {"$lte": ["$stock_quantity", "$reorder_level"]}},
                                  {"_id": 0, "name": 1, "stock_quantity": 1, "reorder_level": 1}))


def paginate_patients(db, page=1, page_size=5):
    """skip / limit pagination."""
    return list(db.patients.find({}, {"_id": 0, "patient_code": 1, "name": 1})
                .sort("patient_code", ASCENDING).skip((page - 1) * page_size).limit(page_size))


def text_search_patients(db, words):
    """Uses the text index on patients.name."""
    return list(db.patients.find({"$text": {"$search": words}}, {"_id": 0, "patient_code": 1, "name": 1}))


# =============================================================================
# UPDATE
# =============================================================================
def reschedule_appointment(db, appt_code, new_date, new_slot):
    """update_one + $set. The unique partial index still protects against clashes."""
    try:
        r = db.appointments.update_one(
            {"appointment_code": appt_code, "status": "Scheduled"},
            {"$set": {"appointment_date": _parse_date(new_date), "time_slot": new_slot,
                      "updated_at": datetime.now()}})
    except DuplicateKeyError:
        return False, "That slot is already taken."
    return (r.modified_count == 1), ("Rescheduled." if r.modified_count else "No scheduled appointment found.")


def cancel_appointment(db, appt_code, reason):
    r = db.appointments.update_one(
        {"appointment_code": appt_code, "status": "Scheduled"},
        {"$set": {"status": "Cancelled", "cancellation_reason": reason, "updated_at": datetime.now()}})
    return r.modified_count == 1


def complete_appointment(db, appt_code, diagnosis, prescription, payment_mode="Cash"):
    """
    Closes a visit: stores diagnosis + embedded prescription + payment and
    decrements pharmacy stock with ONE bulk_write ($inc by a negative number).
    """
    appt = db.appointments.find_one({"appointment_code": appt_code, "status": "Scheduled"})
    if not appt:
        return False
    doctor = db.doctors.find_one({"_id": appt["doctor_id"]})
    med_total = sum(i["quantity"] * i["unit_price"] for i in prescription)
    db.appointments.update_one({"_id": appt["_id"]}, {"$set": {
        "status": "Completed", "diagnosis": diagnosis, "prescription": prescription,
        "consultation_fee": doctor["consultation_fee"], "medicine_charges": round(med_total, 2),
        "payment": {"mode": payment_mode, "status": "Paid",
                    "amount": round(doctor["consultation_fee"] + med_total, 2)},
        "updated_at": datetime.now()}})
    db.medicines.bulk_write([
        UpdateOne({"name": i["medicine_name"], "stock_quantity": {"$gte": i["quantity"]}},
                  {"$inc": {"stock_quantity": -i["quantity"]}}) for i in prescription])
    return True


def add_allergy(db, patient_code, allergy):
    """$addToSet - adds only if not already present (no duplicates)."""
    return db.patients.update_one({"patient_code": patient_code},
                                  {"$addToSet": {"allergies": allergy},
                                   "$currentDate": {"updated_at": True}}).modified_count


def remove_allergy(db, patient_code, allergy):
    """$pull - removes matching array elements."""
    return db.patients.update_one({"patient_code": patient_code},
                                  {"$pull": {"allergies": allergy},
                                   "$currentDate": {"updated_at": True}}).modified_count


def update_patient_contact(db, patient_code, phone, city=None):
    """$set with dot-notation to change a field inside the embedded address."""
    changes = {"phone": phone}
    if city:
        changes["address.city"] = city
    return db.patients.update_one({"patient_code": patient_code},
                                  {"$set": changes, "$currentDate": {"updated_at": True}}).modified_count


def raise_fees_for_specialization(db, spec, percent):
    """
    update_many with an AGGREGATION-PIPELINE update (MongoDB 4.2+): the new fee is
    computed from the old value on the server and rounded to a whole rupee.
    """
    r = db.doctors.update_many(
        {"specialization": spec},
        [{"$set": {"consultation_fee": {"$round": [{"$multiply": ["$consultation_fee", 1 + percent / 100]}, 0]},
                   "updated_at": "$$NOW"}}])
    return r.modified_count


def restock_medicine(db, name, qty, unit_price=None, category="Supplement"):
    """UPSERT: increment stock if the medicine exists, otherwise create it."""
    update = {"$inc": {"stock_quantity": qty}, "$currentDate": {"updated_at": True},
              "$setOnInsert": {"category": category, "reorder_level": 20, "unit_price": unit_price or 10.0}}
    r = db.medicines.update_one({"name": name}, update, upsert=True)
    return "inserted" if r.upserted_id else "updated"


def mark_past_scheduled_as_noshow(db, before):
    """update_many - clean-up job for scheduled visits that already passed."""
    return db.appointments.update_many(
        {"status": "Scheduled", "appointment_date": {"$lt": _parse_date(before)}},
        {"$set": {"status": "No-Show"}, "$currentDate": {"updated_at": True}}).modified_count


# =============================================================================
# DELETE
# =============================================================================
def deactivate_patient(db, patient_code):
    """SOFT delete - keeps medical history intact (preferred in healthcare)."""
    return db.patients.update_one({"patient_code": patient_code},
                                  {"$set": {"is_active": False}}).modified_count


def delete_patient_if_no_history(db, patient_code):
    """HARD delete guarded by a referential check (MongoDB has no foreign keys)."""
    p = db.patients.find_one({"patient_code": patient_code})
    if not p:
        return "not found"
    if db.appointments.count_documents({"patient_id": p["_id"]}, limit=1):
        return "refused: patient has appointment history"
    return "deleted" if db.patients.delete_one({"_id": p["_id"]}).deleted_count else "not found"


def delete_appointment(db, appt_code):
    return db.appointments.delete_one({"appointment_code": appt_code}).deleted_count


def purge_cancelled_before(db, cutoff):
    """delete_many - archive/purge job for old cancelled bookings."""
    return db.appointments.delete_many({"status": "Cancelled",
                                        "appointment_date": {"$lt": _parse_date(cutoff)}}).deleted_count


def remove_and_return_medicine(db, name):
    """find_one_and_delete returns the removed document (useful for audit logs)."""
    return db.medicines.find_one_and_delete({"name": name}, projection={"_id": 0})


# =============================================================================
# Validation + index demos
# =============================================================================
def demo_validation(db):
    """Try inserting INVALID documents to prove the server-side validators work."""
    bad_docs = [
        ("doctors", "Fee below minimum & bad phone number", {
            "doctor_code": "DOC099", "name": "Dr. Test Case", "specialization": "Cardiology",
            "qualifications": ["MBBS"], "experience_years": 5, "consultation_fee": 20,
            "phone": "12345", "email": "test@meditrack.in", "available_days": ["Mon"],
            "is_active": True, "joined_on": datetime.now()}),
        ("patients", "Unknown gender, invalid blood group, 5-digit pincode", {
            "patient_code": "PAT9999", "name": "Invalid Patient", "gender": "Unknown",
            "date_of_birth": datetime(1990, 1, 1), "blood_group": "Z+", "phone": "9876543210",
            "address": {"city": "Amritsar", "state": "Punjab", "pincode": "1430"},
            "is_active": True, "registered_on": datetime.now()}),
        ("medicines", "Negative stock quantity", {
            "name": "Test Tablet", "category": "Analgesic", "unit_price": 5,
            "stock_quantity": -10, "reorder_level": 5}),
        ("appointments", "Completed visit without a diagnosis (cross-field rule)", {
            "appointment_code": "APT99999", "patient_id": db.patients.find_one()["_id"],
            "doctor_id": db.doctors.find_one()["_id"], "appointment_date": datetime(2026, 12, 1),
            "time_slot": "10:00", "status": "Completed", "reason": "Fever",
            "created_at": datetime.now()}),
        ("appointments", "Invalid time slot (25:61) and unknown extra field", {
            "appointment_code": "APT99998", "patient_id": db.patients.find_one()["_id"],
            "doctor_id": db.doctors.find_one()["_id"], "appointment_date": datetime(2026, 12, 1),
            "time_slot": "25:61", "status": "Scheduled", "reason": "Fever",
            "created_at": datetime.now(), "hacker_field": True}),
    ]
    results = []
    for coll, label, doc in bad_docs:
        try:
            db[coll].insert_one(doc)
            results.append((coll, label, "INSERTED (validation did NOT fire!)"))
            db[coll].delete_one({"_id": doc["_id"]})
        except WriteError as e:
            results.append((coll, label, f"REJECTED - code {e.code} (DocumentValidationFailure)"))
    return results


def demo_index_usage(db):
    """explain() proves the compound index is used instead of a collection scan."""
    doc = db.doctors.find_one({"doctor_code": "DOC003"})
    q = {"doctor_id": doc["_id"], "appointment_date": {"$gte": datetime(2026, 1, 1)}}
    plan = db.appointments.find(q).explain()["queryPlanner"]["winningPlan"]
    stage = plan
    stages = []
    while stage:
        stages.append(stage.get("stage") or stage.get("indexName"))
        if stage.get("stage") == "IXSCAN":
            stages.append(f"index={stage.get('indexName')}")
        stage = stage.get("inputStage")
    return stages
