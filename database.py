"""
database.py - Connection, schema validation and indexes for MediTrack.

Collections
-----------
doctors       : clinic doctors (reference data)
patients      : registered patients (with embedded address / emergency contact)
medicines     : pharmacy catalogue with stock levels
appointments  : one document per visit; prescription and payment are EMBEDDED
counters      : atomic sequence generator for appointment codes

Validation is implemented with MongoDB's native $jsonSchema (server side), so
bad data is rejected no matter which client inserts it.
"""
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ServerSelectionTimeoutError

import config

# ----------------------------------------------------------------------------
# Reusable enumerations
# ----------------------------------------------------------------------------
SPECIALIZATIONS = ["General Medicine", "Cardiology", "Dermatology", "Pediatrics",
                   "Orthopedics", "ENT", "Gynecology", "Neurology"]
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
APPT_STATUS = ["Scheduled", "Completed", "Cancelled", "No-Show"]
PAY_MODES = ["Cash", "UPI", "Card", "Insurance"]
PAY_STATUS = ["Paid", "Pending", "Refunded"]
MED_CATEGORIES = ["Analgesic", "Antibiotic", "Antihistamine", "Antacid", "Antidiabetic",
                  "Antihypertensive", "Statin", "Dermatological", "Supplement",
                  "Respiratory", "Hormonal", "Rehydration"]

PHONE_RE = "^[6-9][0-9]{9}$"                      # Indian mobile number
EMAIL_RE = "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$"
TIME_RE = "^([01][0-9]|2[0-3]):[0-5][0-9]$"       # 24h HH:MM

# ----------------------------------------------------------------------------
# $jsonSchema validators
# ----------------------------------------------------------------------------
DOCTOR_VALIDATOR = {"$jsonSchema": {
    "bsonType": "object",
    "required": ["doctor_code", "name", "specialization", "qualifications",
                 "experience_years", "consultation_fee", "phone", "email",
                 "available_days", "is_active", "joined_on"],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "objectId"},
        "doctor_code": {"bsonType": "string", "pattern": "^DOC[0-9]{3}$",
                        "description": "e.g. DOC001"},
        "name": {"bsonType": "string", "minLength": 3, "maxLength": 80},
        "specialization": {"enum": SPECIALIZATIONS},
        "qualifications": {"bsonType": "array", "minItems": 1,
                           "items": {"bsonType": "string"}},
        "experience_years": {"bsonType": ["int", "long"], "minimum": 0, "maximum": 60},
        "consultation_fee": {"bsonType": ["int", "long", "double"], "minimum": 100, "maximum": 5000},
        "phone": {"bsonType": "string", "pattern": PHONE_RE},
        "email": {"bsonType": "string", "pattern": EMAIL_RE},
        "available_days": {"bsonType": "array", "minItems": 1, "uniqueItems": True,
                           "items": {"enum": WEEKDAYS}},
        "is_active": {"bsonType": "bool"},
        "joined_on": {"bsonType": "date"},
        "updated_at": {"bsonType": "date"},
    },
}}

PATIENT_VALIDATOR = {"$jsonSchema": {
    "bsonType": "object",
    "required": ["patient_code", "name", "gender", "date_of_birth", "blood_group",
                 "phone", "address", "is_active", "registered_on"],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "objectId"},
        "patient_code": {"bsonType": "string", "pattern": "^PAT[0-9]{4}$"},
        "name": {"bsonType": "string", "minLength": 3, "maxLength": 80},
        "gender": {"enum": ["Male", "Female", "Other"]},
        "date_of_birth": {"bsonType": "date"},
        "blood_group": {"enum": BLOOD_GROUPS},
        "phone": {"bsonType": "string", "pattern": PHONE_RE},
        "email": {"bsonType": "string", "pattern": EMAIL_RE},
        "address": {
            "bsonType": "object",
            "required": ["city", "state", "pincode"],
            "additionalProperties": False,
            "properties": {
                "street": {"bsonType": "string"},
                "city": {"bsonType": "string"},
                "state": {"bsonType": "string"},
                "pincode": {"bsonType": "string", "pattern": "^[0-9]{6}$"},
            },
        },
        "emergency_contact": {
            "bsonType": "object",
            "required": ["name", "phone", "relation"],
            "properties": {
                "name": {"bsonType": "string"},
                "phone": {"bsonType": "string", "pattern": PHONE_RE},
                "relation": {"bsonType": "string"},
            },
        },
        "allergies": {"bsonType": "array", "items": {"bsonType": "string"}},
        "chronic_conditions": {"bsonType": "array", "items": {"bsonType": "string"}},
        "is_active": {"bsonType": "bool"},
        "registered_on": {"bsonType": "date"},
        "updated_at": {"bsonType": "date"},
    },
}}

MEDICINE_VALIDATOR = {"$jsonSchema": {
    "bsonType": "object",
    "required": ["name", "category", "unit_price", "stock_quantity", "reorder_level"],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "objectId"},
        "name": {"bsonType": "string", "minLength": 2},
        "category": {"enum": MED_CATEGORIES},
        "unit_price": {"bsonType": ["int", "long", "double"], "minimum": 0},
        "stock_quantity": {"bsonType": ["int", "long"], "minimum": 0},
        "reorder_level": {"bsonType": ["int", "long"], "minimum": 0},
        "requires_prescription": {"bsonType": "bool"},
        "updated_at": {"bsonType": "date"},
    },
}}

_PRESCRIPTION_ITEM = {
    "bsonType": "object",
    "required": ["medicine_name", "dosage", "frequency", "duration_days",
                 "quantity", "unit_price"],
    "properties": {
        "medicine_name": {"bsonType": "string"},
        "dosage": {"bsonType": "string"},
        "frequency": {"bsonType": "string"},
        "duration_days": {"bsonType": ["int", "long"], "minimum": 1, "maximum": 365},
        "quantity": {"bsonType": ["int", "long"], "minimum": 1},
        "unit_price": {"bsonType": ["int", "long", "double"], "minimum": 0},
    },
}

APPOINTMENT_VALIDATOR = {"$and": [
    {"$jsonSchema": {
        "bsonType": "object",
        "required": ["appointment_code", "patient_id", "doctor_id", "appointment_date",
                     "time_slot", "status", "reason", "created_at"],
        "additionalProperties": False,
        "properties": {
            "_id": {"bsonType": "objectId"},
            "appointment_code": {"bsonType": "string", "pattern": "^APT[0-9]{5}$"},
            "patient_id": {"bsonType": "objectId"},
            "doctor_id": {"bsonType": "objectId"},
            "appointment_date": {"bsonType": "date"},
            "time_slot": {"bsonType": "string", "pattern": TIME_RE},
            "status": {"enum": APPT_STATUS},
            "reason": {"bsonType": "string", "minLength": 3, "maxLength": 200},
            "symptoms": {"bsonType": "array", "items": {"bsonType": "string"}},
            "diagnosis": {"bsonType": "string", "minLength": 3},
            "prescription": {"bsonType": "array", "items": _PRESCRIPTION_ITEM},
            "consultation_fee": {"bsonType": ["int", "long", "double"], "minimum": 0},
            "medicine_charges": {"bsonType": ["int", "long", "double"], "minimum": 0},
            "payment": {
                "bsonType": "object",
                "required": ["mode", "status", "amount"],
                "properties": {
                    "mode": {"enum": PAY_MODES},
                    "status": {"enum": PAY_STATUS},
                    "amount": {"bsonType": ["int", "long", "double"], "minimum": 0},
                },
            },
            "cancellation_reason": {"bsonType": "string"},
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"},
        },
    }},
    # Cross-field business rule ($jsonSchema cannot express "if/then"):
    # a COMPLETED visit must always carry a diagnosis.
    {"$or": [{"status": {"$ne": "Completed"}},
             {"diagnosis": {"$type": "string"}}]},
]}

VALIDATORS = {
    "doctors": DOCTOR_VALIDATOR,
    "patients": PATIENT_VALIDATOR,
    "medicines": MEDICINE_VALIDATOR,
    "appointments": APPOINTMENT_VALIDATOR,
}


# ----------------------------------------------------------------------------
# Connection
# ----------------------------------------------------------------------------
def get_db():
    """Connect to MongoDB (PyMongo) and return the project database."""
    client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
    except ServerSelectionTimeoutError:
        raise SystemExit(
            f"\n[ERROR] Cannot reach MongoDB at {config.MONGO_URI}.\n"
            "Start the MongoDB service (or set MONGO_URI to your Atlas string) and retry."
        )
    return client[config.DB_NAME]


# ----------------------------------------------------------------------------
# Schema + index creation
# ----------------------------------------------------------------------------
def _ensure_collection(db, name, validator):
    options = dict(validator=validator, validationLevel="strict", validationAction="error")
    if name in db.list_collection_names():
        db.command("collMod", name, **options)          # update existing validator
    else:
        db.create_collection(name, **options)


def create_indexes(db):
    db.doctors.create_index("doctor_code", unique=True, name="uq_doctor_code")
    db.doctors.create_index([("specialization", ASCENDING), ("is_active", ASCENDING)],
                            name="ix_spec_active")

    db.patients.create_index("patient_code", unique=True, name="uq_patient_code")
    db.patients.create_index("phone", unique=True, name="uq_patient_phone")
    db.patients.create_index("address.city", name="ix_city")
    db.patients.create_index([("name", "text")], name="tx_patient_name")

    db.medicines.create_index("name", unique=True, name="uq_medicine_name")

    db.appointments.create_index("appointment_code", unique=True, name="uq_appt_code")
    db.appointments.create_index([("patient_id", ASCENDING), ("appointment_date", DESCENDING)],
                                 name="ix_patient_history")
    db.appointments.create_index([("doctor_id", ASCENDING), ("appointment_date", ASCENDING)],
                                 name="ix_doctor_schedule")
    db.appointments.create_index("status", name="ix_status")
    # Prevents double-booking: one ACTIVE (Scheduled) appointment per doctor/date/slot.
    db.appointments.create_index(
        [("doctor_id", ASCENDING), ("appointment_date", ASCENDING), ("time_slot", ASCENDING)],
        unique=True, name="uq_no_double_booking",
        partialFilterExpression={"status": "Scheduled"})


def setup_database(db, drop_existing=False):
    """Create collections with validators and indexes."""
    if drop_existing:
        for name in list(VALIDATORS) + ["counters", "monthly_revenue_report"]:
            db.drop_collection(name)
    for name, validator in VALIDATORS.items():
        _ensure_collection(db, name, validator)
    create_indexes(db)
    return sorted(db.list_collection_names())
