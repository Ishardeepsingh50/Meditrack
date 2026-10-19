# Viva preparation - MediTrack

## 5-minute demo script
1. `python main.py seed`      -> collections, validators, indexes, 200 appointments created
2. `python main.py validate`  -> 5 invalid inserts rejected (error code 121)
3. `python main.py crud`      -> Create / Read / Update / Delete sections (point at `book_appointment` double-booking message)
4. `python main.py aggregate` -> walk through A1 (lookup), A3 (unwind), A11 (window function)
5. `python main.py index`     -> explain() shows IXSCAN on `ix_doctor_schedule`
6. Open MongoDB Compass: show an appointment document and the Validation tab.

## Likely questions and short answers
**Why did you embed prescription and payment?** They are read with the visit, belong to exactly one visit, and are small and bounded. It avoids joins and lets `$unwind` give medicine statistics.

**Why reference doctors and patients?** They are shared by many appointments and change independently (fee, phone). Embedding would duplicate data and create stale copies.

**Why store `unit_price` inside the prescription?** Snapshot pattern - a later price change must not change old bills.

**How do you stop double booking?** Unique *partial* index on `(doctor_id, appointment_date, time_slot)` with `partialFilterExpression: {status: "Scheduled"}`. Cancelled slots can be reused. The insert raises `DuplicateKeyError`.

**What happens if the data is invalid?** `$jsonSchema` validator (strict, action error) -> `WriteError` code 121. Validation is on the server, so it holds for every client.

**Why `$and` + `$or` in the appointment validator?** `$jsonSchema` has no if/then. "Completed => diagnosis" is written as `status != Completed OR diagnosis is a string`.

**Difference between `$set`, `$inc`, `$addToSet`, `$pull`, `$setOnInsert`?** Replace a field / add a number / add to array if absent / remove from array / only applied when an upsert inserts.

**What does `upsert=True` do?** Updates the matching document or inserts a new one if none matches (`restock_medicine`).

**`$lookup` vs embedding?** `$lookup` is a left outer join between collections; use it when data is referenced. Embedded data needs no join.

**`$match` first - why?** It reduces documents early and can use indexes.

**`$group` vs `$bucket` vs `$facet`?** Group by value / group into ranges / run several sub-pipelines on the same input.

**What is `$unwind`?** Turns each array element into its own document (A3, A9).

**Why a soft delete for patients?** Medical history must be kept; `is_active=false` hides the patient without losing records. Hard delete is allowed only when there is no history.

**Does MongoDB have foreign keys?** No. Integrity is handled in application code (`delete_patient_if_no_history`) and by design.

**Is `complete_appointment` atomic?** Each write is atomic, the two collections together are not. On a replica set/Atlas, wrap them in a transaction (`start_session` + `with_transaction`).

**What does `explain()` show?** The winning plan. `IXSCAN` = index used; `COLLSCAN` = full scan.

**Why `ordered=False` in `insert_many`?** Continues inserting after a failed document (e.g. a duplicate).

## Be ready to write on the spot
```javascript
// patients older than 60 in Amritsar
db.patients.find({ "address.city": "Amritsar", date_of_birth: { $lte: new Date("1966-10-19") } })

// average consultation fee per specialization
db.doctors.aggregate([{ $group: { _id: "$specialization", avg_fee: { $avg: "$consultation_fee" } } }])

// number of appointments per patient, top 3
db.appointments.aggregate([{ $group: { _id: "$patient_id", n: { $sum: 1 } } }, { $sort: { n: -1 } }, { $limit: 3 }])

// UPI revenue only
db.appointments.aggregate([{ $match: { "payment.mode": "UPI" } }, { $group: { _id: null, total: { $sum: "$payment.amount" } } }])
```
