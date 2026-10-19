# MediTrack - Clinic Appointment & Prescription Management (MongoDB + PyMongo)

Course: CSE494 Intelligent NoSQL Databases | Academic Task 2 (Project)

MediTrack manages doctors, patients, appointments, prescriptions, billing and
pharmacy stock for a multi-specialty clinic. It demonstrates document modelling
(embedding vs referencing), server-side `$jsonSchema` validation, CRUD, indexes
and 11 aggregation pipelines, all driven from Python through PyMongo.

## 1. Requirements
* Python 3.9+
* MongoDB 5.0 or newer (Community Server, or a free MongoDB Atlas cluster)
* `pip install -r requirements.txt`   (installs `pymongo`)

## 2. Run
```bash
# make sure mongod is running  (default: mongodb://localhost:27017)
# Atlas users:  export MONGO_URI="mongodb+srv://<user>:<pass>@<cluster>/"

python main.py all          # seed + validation + CRUD + aggregation + index demo
                            # also saves outputs/execution_log.txt  (use for screenshots)

python main.py menu         # interactive menu for the viva
python main.py seed         # or run a single stage: setup | seed | validate | crud | aggregate | index
```
Optional: `mongosh < mongo_shell_queries.js` runs the same operations as plain shell queries.

## 3. Files
| File | Purpose |
|---|---|
| `config.py` | connection string / database name |
| `database.py` | PyMongo connection, `$jsonSchema` validators, indexes |
| `seed_data.py` | reproducible dataset (8 doctors, 21 medicines, 45 patients, 200 appointments) |
| `crud_operations.py` | all Create / Read / Update / Delete functions + validation & index demos |
| `aggregations.py` | 11 analytic pipelines + `$merge` report |
| `main.py` | CLI runner / menu |
| `mongo_shell_queries.js` | the same queries in mongosh syntax |

## 4. Data model (summary)
* `doctors`, `patients`, `medicines` - independent entities (patient address and emergency contact are **embedded**).
* `appointments` - references `patient_id` and `doctor_id`; **embeds** `prescription[]` and `payment{}`
  because they are always read together with the visit and never shared.
* Prescription lines snapshot `unit_price`, so later price changes never rewrite history.
* `counters` - atomic sequence for appointment codes.
