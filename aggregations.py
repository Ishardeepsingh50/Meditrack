"""
aggregations.py - Analytical aggregation pipelines for MediTrack.

Each pipeline is stored in the REPORTS list as:
    (key, title, business question, collection, pipeline)

so the same definitions are used by main.py, by the report, and in the viva.
Requires MongoDB 5.0+ (for $setWindowFields); everything else works on 4.4+.
"""
from datetime import datetime

NOW = datetime.now()
MS_PER_YEAR = 365.25 * 24 * 60 * 60 * 1000

# -----------------------------------------------------------------------------
# 1. Revenue per doctor    ($match -> $group -> $lookup -> $unwind -> $project -> $sort)
# -----------------------------------------------------------------------------
DOCTOR_REVENUE = [
    {"$match": {"status": "Completed", "payment.status": "Paid"}},
    {"$group": {"_id": "$doctor_id",
                "total_revenue": {"$sum": "$payment.amount"},
                "consultations": {"$sum": 1},
                "avg_bill": {"$avg": "$payment.amount"}}},
    {"$lookup": {"from": "doctors", "localField": "_id", "foreignField": "_id", "as": "doctor"}},
    {"$unwind": "$doctor"},
    {"$project": {"_id": 0, "doctor": "$doctor.name", "specialization": "$doctor.specialization",
                  "consultations": 1, "total_revenue": {"$round": ["$total_revenue", 2]},
                  "avg_bill": {"$round": ["$avg_bill", 2]}}},
    {"$sort": {"total_revenue": -1}},
]

# -----------------------------------------------------------------------------
# 2. Monthly appointment trend    (date operator + conditional counting)
# -----------------------------------------------------------------------------
MONTHLY_TREND = [
    {"$group": {"_id": {"$dateToString": {"format": "%Y-%m", "date": "$appointment_date"}},
                "total": {"$sum": 1},
                "completed": {"$sum": {"$cond": [{"$eq": ["$status", "Completed"]}, 1, 0]}},
                "cancelled": {"$sum": {"$cond": [{"$eq": ["$status", "Cancelled"]}, 1, 0]}},
                "no_show": {"$sum": {"$cond": [{"$eq": ["$status", "No-Show"]}, 1, 0]}},
                "scheduled": {"$sum": {"$cond": [{"$eq": ["$status", "Scheduled"]}, 1, 0]}}}},
    {"$sort": {"_id": 1}},
    {"$project": {"_id": 0, "month": "$_id", "total": 1, "completed": 1, "cancelled": 1,
                  "no_show": 1, "scheduled": 1}},
]

# -----------------------------------------------------------------------------
# 3. Top-5 prescribed medicines    ($unwind on embedded array)
# -----------------------------------------------------------------------------
TOP_MEDICINES = [
    {"$match": {"status": "Completed"}},
    {"$unwind": "$prescription"},
    {"$group": {"_id": "$prescription.medicine_name",
                "times_prescribed": {"$sum": 1},
                "units_dispensed": {"$sum": "$prescription.quantity"},
                "sales_value": {"$sum": {"$multiply": ["$prescription.quantity", "$prescription.unit_price"]}}}},
    {"$sort": {"times_prescribed": -1, "units_dispensed": -1}},
    {"$limit": 5},
    {"$project": {"_id": 0, "medicine": "$_id", "times_prescribed": 1, "units_dispensed": 1,
                  "sales_value": {"$round": ["$sales_value", 2]}}},
]

# -----------------------------------------------------------------------------
# 4. Patient age-group distribution    ($addFields + $bucket)
# -----------------------------------------------------------------------------
AGE_GROUPS = [
    {"$match": {"is_active": True}},
    {"$addFields": {"age": {"$floor": {"$divide": [{"$subtract": [NOW, "$date_of_birth"]}, MS_PER_YEAR]}},
                    "condition_count": {"$size": {"$ifNull": ["$chronic_conditions", []]}}}},
    {"$bucket": {"groupBy": "$age",
                 "boundaries": [0, 13, 19, 36, 51, 66, 120],
                 "default": "Other",
                 "output": {"patients": {"$sum": 1},
                            "avg_chronic_conditions": {"$avg": "$condition_count"},
                            "youngest": {"$min": "$age"}, "oldest": {"$max": "$age"}}}},
    {"$project": {"age_from": "$_id", "patients": 1, "youngest": 1, "oldest": 1,
                  "avg_chronic_conditions": {"$round": ["$avg_chronic_conditions", 2]}, "_id": 0}},
]

# -----------------------------------------------------------------------------
# 5. Top-3 diagnoses per specialization    (two-stage $group + $slice)
# -----------------------------------------------------------------------------
TOP_DIAGNOSES = [
    {"$match": {"status": "Completed"}},
    {"$lookup": {"from": "doctors", "localField": "doctor_id", "foreignField": "_id", "as": "doc"}},
    {"$unwind": "$doc"},
    {"$group": {"_id": {"spec": "$doc.specialization", "diagnosis": "$diagnosis"}, "cases": {"$sum": 1}}},
    {"$sort": {"cases": -1}},
    {"$group": {"_id": "$_id.spec",
                "total_cases": {"$sum": "$cases"},
                "diagnoses": {"$push": {"diagnosis": "$_id.diagnosis", "cases": "$cases"}}}},
    {"$project": {"_id": 0, "specialization": "$_id", "total_cases": 1,
                  "top_diagnoses": {"$slice": ["$diagnoses", 3]}}},
    {"$sort": {"total_cases": -1}},
]

# -----------------------------------------------------------------------------
# 6. Cancellation / no-show rate per doctor    ($cond, $divide, $multiply)
# -----------------------------------------------------------------------------
CANCELLATION_RATE = [
    {"$match": {"status": {"$in": ["Completed", "Cancelled", "No-Show"]}}},
    {"$group": {"_id": "$doctor_id", "booked": {"$sum": 1},
                "lost": {"$sum": {"$cond": [{"$in": ["$status", ["Cancelled", "No-Show"]]}, 1, 0]}}}},
    {"$lookup": {"from": "doctors", "localField": "_id", "foreignField": "_id", "as": "d"}},
    {"$unwind": "$d"},
    {"$project": {"_id": 0, "doctor": "$d.name", "booked": 1, "lost": 1,
                  "loss_rate_pct": {"$round": [{"$multiply": [{"$divide": ["$lost", "$booked"]}, 100]}, 1]}}},
    {"$sort": {"loss_rate_pct": -1}},
]

# -----------------------------------------------------------------------------
# 7. Top-5 patients by spending    (group -> lookup patients)
# -----------------------------------------------------------------------------
TOP_PATIENTS = [
    {"$match": {"status": "Completed"}},
    {"$group": {"_id": "$patient_id", "visits": {"$sum": 1}, "total_spent": {"$sum": "$payment.amount"},
                "last_visit": {"$max": "$appointment_date"}}},
    {"$sort": {"total_spent": -1}},
    {"$limit": 5},
    {"$lookup": {"from": "patients", "localField": "_id", "foreignField": "_id", "as": "p"}},
    {"$unwind": "$p"},
    {"$project": {"_id": 0, "patient": "$p.name", "city": "$p.address.city", "visits": 1,
                  "total_spent": {"$round": ["$total_spent", 2]}, "last_visit": 1}},
]

# -----------------------------------------------------------------------------
# 8. Busiest weekday    ($dayOfWeek + $arrayElemAt)
# -----------------------------------------------------------------------------
BUSIEST_WEEKDAY = [
    {"$match": {"status": {"$in": ["Completed", "No-Show", "Cancelled"]}}},
    {"$group": {"_id": {"$dayOfWeek": "$appointment_date"}, "appointments": {"$sum": 1}}},
    {"$project": {"_id": 0, "appointments": 1,
                  "weekday": {"$arrayElemAt": [["Sunday", "Monday", "Tuesday", "Wednesday",
                                                "Thursday", "Friday", "Saturday"],
                                               {"$subtract": ["$_id", 1]}]}}},
    {"$sort": {"appointments": -1}},
]

# -----------------------------------------------------------------------------
# 9. Allergy frequency    ($unwind on patient array + percentage of total)
# -----------------------------------------------------------------------------
ALLERGY_FREQUENCY = [
    {"$match": {"is_active": True}},
    {"$unwind": "$allergies"},
    {"$group": {"_id": "$allergies", "patients": {"$sum": 1}, "cities": {"$addToSet": "$address.city"}}},
    {"$project": {"_id": 0, "allergy": "$_id", "patients": 1, "city_count": {"$size": "$cities"}}},
    {"$sort": {"patients": -1}},
]

# -----------------------------------------------------------------------------
# 10. Management dashboard in ONE round trip    ($facet)
# -----------------------------------------------------------------------------
DASHBOARD = [
    {"$facet": {
        "by_status": [{"$sortByCount": "$status"}],
        "payment_modes": [{"$match": {"status": "Completed"}},
                          {"$group": {"_id": "$payment.mode", "bills": {"$sum": 1},
                                      "amount": {"$sum": "$payment.amount"}}},
                          {"$sort": {"amount": -1}}],
        "revenue_summary": [{"$match": {"status": "Completed"}},
                            {"$group": {"_id": None,
                                        "consultation_revenue": {"$sum": "$consultation_fee"},
                                        "pharmacy_revenue": {"$sum": "$medicine_charges"},
                                        "total_revenue": {"$sum": "$payment.amount"},
                                        "pending_amount": {"$sum": {"$cond": [{"$eq": ["$payment.status", "Pending"]}, "$payment.amount", 0]}}}},
                            {"$project": {"_id": 0}}],
    }},
]

# -----------------------------------------------------------------------------
# 11. Cumulative monthly revenue    ($setWindowFields - running total)  MongoDB 5.0+
# -----------------------------------------------------------------------------
CUMULATIVE_REVENUE = [
    {"$match": {"status": "Completed"}},
    {"$group": {"_id": {"$dateToString": {"format": "%Y-%m", "date": "$appointment_date"}},
                "revenue": {"$sum": "$payment.amount"}}},
    {"$setWindowFields": {"sortBy": {"_id": 1},
                          "output": {"cumulative_revenue": {"$sum": "$revenue",
                                                            "window": {"documents": ["unbounded", "current"]}}}}},
    {"$project": {"_id": 0, "month": "$_id", "revenue": {"$round": ["$revenue", 2]},
                  "cumulative_revenue": {"$round": ["$cumulative_revenue", 2]}}},
]

# -----------------------------------------------------------------------------
# 12. Materialised report with $merge  (writes results into a new collection)
# -----------------------------------------------------------------------------
MATERIALISE_MONTHLY_REVENUE = [
    {"$match": {"status": "Completed"}},
    {"$group": {"_id": {"$dateToString": {"format": "%Y-%m", "date": "$appointment_date"}},
                "revenue": {"$sum": "$payment.amount"}, "visits": {"$sum": 1}}},
    {"$merge": {"into": "monthly_revenue_report", "whenMatched": "replace", "whenNotMatched": "insert"}},
]

# key, title, question, collection, pipeline
REPORTS = [
    ("revenue", "Revenue per doctor", "Which doctors generate the most revenue?", "appointments", DOCTOR_REVENUE),
    ("trend", "Monthly appointment trend", "How does demand and cancellation vary month by month?", "appointments", MONTHLY_TREND),
    ("meds", "Top-5 prescribed medicines", "Which medicines should the pharmacy stock most?", "appointments", TOP_MEDICINES),
    ("age", "Patient age-group distribution", "Which age groups do we serve and how sick are they?", "patients", AGE_GROUPS),
    ("diagnoses", "Top-3 diagnoses per specialization", "What conditions dominate each department?", "appointments", TOP_DIAGNOSES),
    ("cancel", "Cancellation / no-show rate per doctor", "Whose schedule loses the most slots?", "appointments", CANCELLATION_RATE),
    ("patients", "Top-5 patients by spending", "Who are our highest-value patients?", "appointments", TOP_PATIENTS),
    ("weekday", "Busiest weekday", "Which weekdays need the most staff?", "appointments", BUSIEST_WEEKDAY),
    ("allergy", "Allergy frequency", "Which allergies are most common among patients?", "patients", ALLERGY_FREQUENCY),
    ("dashboard", "Management dashboard ($facet)", "One-call summary: status, payment modes, revenue", "appointments", DASHBOARD),
    ("cumulative", "Cumulative monthly revenue ($setWindowFields)", "How is revenue accumulating through the year?", "appointments", CUMULATIVE_REVENUE),
]


def run_report(db, key):
    for k, title, question, coll, pipeline in REPORTS:
        if k == key:
            return title, question, list(db[coll].aggregate(pipeline))
    raise KeyError(key)


def materialise_monthly_revenue(db):
    """Runs the $merge pipeline and returns the saved documents."""
    list(db.appointments.aggregate(MATERIALISE_MONTHLY_REVENUE))   # consume cursor so $merge runs
    return list(db.monthly_revenue_report.find().sort("_id", 1))
