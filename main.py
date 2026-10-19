"""
main.py - Command-line runner for the MediTrack project.

Usage
-----
    python main.py setup        # create collections, validators, indexes
    python main.py seed         # load sample data (drops & recreates everything)
    python main.py validate     # prove validation rules reject bad data
    python main.py crud         # run the full CRUD demonstration
    python main.py aggregate    # run all aggregation pipelines
    python main.py index        # show index usage with explain()
    python main.py all          # everything above in order + saves outputs/execution_log.txt
    python main.py menu         # interactive menu (nice for the viva)
"""
import argparse
import os
import sys
from datetime import datetime

import aggregations as agg
import crud_operations as crud
import database
import seed_data
from utils import banner, show, table


# ----------------------------------------------------------------------------
# Section runners
# ----------------------------------------------------------------------------
def do_setup(db, drop=False):
    banner("1. DATABASE SETUP - collections, $jsonSchema validators, indexes")
    names = database.setup_database(db, drop_existing=drop)
    print("Collections:", ", ".join(names))
    for coll in ("doctors", "patients", "medicines", "appointments"):
        print(f"  {coll:<13} indexes -> {', '.join(sorted(db[coll].index_information()))}")


def do_seed(db):
    banner("2. SEEDING SAMPLE DATA")
    database.setup_database(db, drop_existing=True)
    print("Inserted:", seed_data.seed(db))


def do_validate(db):
    banner("3. VALIDATION RULES - invalid inserts must be rejected")
    for coll, label, result in crud.demo_validation(db):
        print(f"[{coll}] {label}\n      -> {result}")


def do_crud(db):
    banner("4. CRUD OPERATIONS")

    banner("CREATE", "-")
    new_doc = {"doctor_code": "DOC009", "name": "Dr. Tanvi Anand", "specialization": "Neurology",
               "qualifications": ["MBBS", "DM (Neurology)"], "experience_years": 8,
               "consultation_fee": 1100, "phone": "9876501234", "email": "tanvi.anand@meditrack.in",
               "available_days": ["Tue", "Fri"]}
    print("add_doctor ->", crud.add_doctor(db, new_doc))
    pid = crud.register_patient(db, {
        "patient_code": "PAT0100", "name": "Mandeep Brar", "gender": "Male",
        "date_of_birth": datetime(1994, 3, 12), "blood_group": "B+", "phone": "9815012345",
        "email": "mandeep.brar@example.com",
        "address": {"street": "12 Model Town", "city": "Amritsar", "state": "Punjab", "pincode": "143001"},
        "emergency_contact": {"name": "Gurmeet Brar", "phone": "9815099999", "relation": "Father"},
        "allergies": ["Dust"]})
    print("register_patient ->", pid)
    print("book_appointment ->", crud.book_appointment(db, "PAT0100", "DOC009", "2026-10-20", "10:00", "Recurring migraine", ["headache", "nausea"]))
    print("double booking   ->", crud.book_appointment(db, "PAT0020", "DOC009", "2026-10-20", "10:00", "Dizziness"))
    print("wrong weekday    ->", crud.book_appointment(db, "PAT0020", "DOC009", "2026-10-21", "11:00", "Dizziness"))

    banner("READ", "-")
    show("find_patient_by_code('PAT0100')", crud.find_patient_by_code(db, "PAT0100"))
    show("search_patients_by_name('singh')", crud.search_patients_by_name(db, "singh"), 3)
    show("doctors_by_specialization('General Medicine')", crud.doctors_by_specialization(db, "General Medicine"))
    show("patients_with_allergy('Penicillin')", crud.patients_with_allergy(db, "Penicillin"), 3)
    show("appointments_in_range(Oct 2026, Completed)", crud.appointments_in_range(db, "2026-10-01", "2026-10-18", "Completed"), 3)
    show("upcoming_schedule_for_doctor('DOC003')", crud.upcoming_schedule_for_doctor(db, "DOC003", "2026-10-19", 3))
    show("low_stock_medicines()  [$expr]", crud.low_stock_medicines(db))
    show("paginate_patients(page=2, size=5)", crud.paginate_patients(db, 2, 5))
    sample = db.appointments.find_one({"status": "Completed"}, {"patient_id": 1})
    code = db.patients.find_one({"_id": sample["patient_id"]})["patient_code"]
    show(f"patient_history('{code}')", crud.patient_history(db, code), 3)

    banner("UPDATE", "-")
    new_code = db.appointments.find_one({"patient_id": pid})["appointment_code"]
    ok, msg = crud.reschedule_appointment(db, new_code, "2026-10-27", "11:30")
    print("reschedule       ->", ok, msg)
    print("add_allergy      ->", crud.add_allergy(db, "PAT0100", "Penicillin"), "modified (added)")
    print("add_allergy again->", crud.add_allergy(db, "PAT0100", "Penicillin"), "modified (duplicate ignored by $addToSet)")
    print("remove_allergy   ->", crud.remove_allergy(db, "PAT0100", "Dust"), "modified")
    print("update contact   ->", crud.update_patient_contact(db, "PAT0100", "9815054321", "Jalandhar"), "modified")
    print("fee +10% Pediatrics ->", crud.raise_fees_for_specialization(db, "Pediatrics", 10), "doctor(s) modified")
    print("restock existing ->", crud.restock_medicine(db, "Losartan 50mg", 200))
    print("restock new item ->", crud.restock_medicine(db, "Vitamin B12 1500mcg", 100, 12.5))
    ok = crud.complete_appointment(db, new_code, "Migraine without aura",
                                   [{"medicine_name": "Paracetamol 500mg", "dosage": "1 tablet", "frequency": "As needed",
                                     "duration_days": 5, "quantity": 10, "unit_price": 2.0}], "UPI")
    print("complete_appointment ->", ok)
    show("completed visit", db.appointments.find_one({"patient_id": pid}, {"_id": 0, "patient_id": 0, "doctor_id": 0}))
    print("no-show clean-up ->", crud.mark_past_scheduled_as_noshow(db, "2026-10-18"), "appointment(s) updated (0 = every past visit is already resolved)")

    banner("DELETE", "-")
    print("cancel_appointment        ->", crud.cancel_appointment(db, db.appointments.find_one({"status": "Scheduled"})["appointment_code"], "Patient unavailable"))
    print("delete w/ history (guard) ->", crud.delete_patient_if_no_history(db, "PAT0100"))
    print("soft delete (deactivate)  ->", crud.deactivate_patient(db, "PAT0100"))
    show("find_one_and_delete -> removed medicine", crud.remove_and_return_medicine(db, "Vitamin B12 1500mcg"))
    print("purge cancelled < Mar-2026->", crud.purge_cancelled_before(db, "2026-03-01"), "deleted")
    print("delete_appointment        ->", crud.delete_appointment(db, "APT00001"), "deleted")


def do_aggregate(db):
    banner("5. AGGREGATION PIPELINES")
    for i, (key, title, question, coll, pipeline) in enumerate(agg.REPORTS, 1):
        _, _, rows = agg.run_report(db, key)
        banner(f"A{i}. {title}", "-")
        print("Question:", question, f"  [collection: {coll}, stages: {len(pipeline)}]")
        if key == "dashboard":
            show("dashboard", rows[0], 1)
        elif key == "diagnoses":
            for r in rows:
                print(f"  {r['specialization']:<17} cases={r['total_cases']:<3}",
                      "; ".join(f"{d['diagnosis']} ({d['cases']})" for d in r["top_diagnoses"]))
        elif rows:
            cols = [c for c in rows[0].keys()]
            table(rows[:12], cols)
    banner("A12. $merge - materialised monthly revenue report", "-")
    table(agg.materialise_monthly_revenue(db), ["_id", "revenue", "visits"])


def do_index(db):
    banner("6. INDEX USAGE (explain)")
    print("Winning plan stages for doctor schedule query:", " -> ".join(map(str, crud.demo_index_usage(db))))


SECTIONS = {"setup": lambda db: do_setup(db), "seed": do_seed, "validate": do_validate,
            "crud": do_crud, "aggregate": do_aggregate, "index": do_index}


class Tee:
    """Copies everything printed to the console into a log file (for screenshots / report)."""
    def __init__(self, path):
        self.file, self.stdout = open(path, "w", encoding="utf-8"), sys.stdout

    def write(self, s):
        self.stdout.write(s); self.file.write(s)

    def flush(self):
        self.stdout.flush(); self.file.flush()


def menu(db):
    options = {"1": ("Setup collections & indexes", "setup"), "2": ("Seed sample data", "seed"),
               "3": ("Validation demo", "validate"), "4": ("CRUD demo", "crud"),
               "5": ("Aggregation reports", "aggregate"), "6": ("Index usage (explain)", "index")}
    while True:
        banner("MEDITRACK - Clinic Management (MongoDB + PyMongo)")
        for k, (label, _) in options.items():
            print(f"  {k}. {label}")
        print("  0. Exit")
        c = input("Choose: ").strip()
        if c == "0":
            break
        if c in options:
            SECTIONS[options[c][1]](db)


def main():
    ap = argparse.ArgumentParser(description="MediTrack - MongoDB clinic management")
    ap.add_argument("command", choices=list(SECTIONS) + ["all", "menu"])
    args = ap.parse_args()
    db = database.get_db()

    if args.command == "all":
        os.makedirs("outputs", exist_ok=True)
        sys.stdout = Tee(os.path.join("outputs", "execution_log.txt"))
        for name in ("seed", "validate", "crud", "aggregate", "index"):
            SECTIONS[name](db)
        sys.stdout = sys.stdout.stdout
        print("\nLog saved to outputs/execution_log.txt")
    elif args.command == "menu":
        menu(db)
    else:
        SECTIONS[args.command](db)


if __name__ == "__main__":
    main()
