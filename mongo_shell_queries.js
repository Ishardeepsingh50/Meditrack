// =============================================================================
// MediTrack - MongoDB Shell (mongosh) queries
// Run:  mongosh < mongo_shell_queries.js     (or paste section by section)
// Prerequisite: run `python main.py seed` once so the data exists.
// =============================================================================
use("meditrack_db");

// -----------------------------------------------------------------------------
// 1. VALIDATION  (same rules the Python code installs with collMod)
// -----------------------------------------------------------------------------
db.runCommand({
  collMod: "medicines",
  validator: { $jsonSchema: {
    bsonType: "object",
    required: ["name", "category", "unit_price", "stock_quantity", "reorder_level"],
    properties: {
      name: { bsonType: "string", minLength: 2 },
      unit_price: { bsonType: ["int", "long", "double"], minimum: 0 },
      stock_quantity: { bsonType: ["int", "long"], minimum: 0 }
    }
  }},
  validationLevel: "strict", validationAction: "error"
});
// Expected: "Document failed validation"
db.medicines.insertOne({ name: "Bad Tablet", category: "Analgesic", unit_price: 5, stock_quantity: -10, reorder_level: 5 });
db.getCollectionInfos({ name: "appointments" })[0].options.validator;   // inspect validator

// -----------------------------------------------------------------------------
// 2. CREATE
// -----------------------------------------------------------------------------
db.patients.insertOne({
  patient_code: "PAT0200", name: "Harleen Kaur", gender: "Female",
  date_of_birth: new Date("1999-07-21"), blood_group: "O+", phone: "9876512345",
  address: { city: "Amritsar", state: "Punjab", pincode: "143001" },
  allergies: [], chronic_conditions: [], is_active: true, registered_on: new Date()
});
db.medicines.insertMany([
  { name: "Vitamin B12 1500mcg", category: "Supplement", unit_price: 12.5, stock_quantity: 100, reorder_level: 20 },
  { name: "Cough Syrup 100ml",   category: "Respiratory", unit_price: 65,  stock_quantity: 40,  reorder_level: 15 }
]);

// -----------------------------------------------------------------------------
// 3. READ
// -----------------------------------------------------------------------------
db.patients.findOne({ patient_code: "PAT0100" }, { _id: 0, name: 1, phone: 1, "address.city": 1 });
db.patients.find({ name: /singh/i }, { _id: 0, patient_code: 1, name: 1 });
db.doctors.find({ specialization: "General Medicine", is_active: true }).sort({ experience_years: -1 });
db.patients.find({ allergies: "Penicillin" });
db.patients.find({ "address.city": { $in: ["Amritsar", "Jalandhar"] } }).limit(5);
db.appointments.find({ appointment_date: { $gte: ISODate("2026-10-01"), $lt: ISODate("2026-11-01") }, status: "Scheduled" })
               .sort({ appointment_date: 1, time_slot: 1 });
db.appointments.find({ prescription: { $elemMatch: { medicine_name: "Metformin 500mg", quantity: { $gte: 30 } } } });
db.medicines.find({ $expr: { $lte: ["$stock_quantity", "$reorder_level"] } });      // low stock
db.patients.find().sort({ patient_code: 1 }).skip(5).limit(5);                       // pagination
db.patients.find({ $text: { $search: "Kaur" } });                                    // text index

// -----------------------------------------------------------------------------
// 4. UPDATE
// -----------------------------------------------------------------------------
db.patients.updateOne({ patient_code: "PAT0200" }, { $set: { phone: "9876599999", "address.city": "Jalandhar" }, $currentDate: { updated_at: true } });
db.patients.updateOne({ patient_code: "PAT0200" }, { $addToSet: { allergies: "Dust" } });
db.patients.updateOne({ patient_code: "PAT0200" }, { $pull: { allergies: "Dust" } });
db.medicines.updateOne({ name: "Losartan 50mg" }, { $inc: { stock_quantity: 200 } });
db.medicines.updateOne({ name: "Zinc Tablet 20mg" },
  { $inc: { stock_quantity: 50 }, $setOnInsert: { category: "Supplement", unit_price: 6, reorder_level: 20 } }, { upsert: true });
db.doctors.updateMany({ specialization: "Pediatrics" },
  [{ $set: { consultation_fee: { $round: [{ $multiply: ["$consultation_fee", 1.10] }, 0] } } }]);   // pipeline update
db.appointments.updateMany({ status: "Scheduled", appointment_date: { $lt: ISODate("2026-10-18") } }, { $set: { status: "No-Show" } });

// -----------------------------------------------------------------------------
// 5. DELETE
// -----------------------------------------------------------------------------
db.patients.updateOne({ patient_code: "PAT0200" }, { $set: { is_active: false } });                // soft delete
db.medicines.deleteOne({ name: "Cough Syrup 100ml" });
db.appointments.deleteMany({ status: "Cancelled", appointment_date: { $lt: ISODate("2026-03-01") } });
db.medicines.findOneAndDelete({ name: "Vitamin B12 1500mcg" });

// -----------------------------------------------------------------------------
// 6. AGGREGATION
// -----------------------------------------------------------------------------
// A1 Revenue per doctor
db.appointments.aggregate([
  { $match: { status: "Completed", "payment.status": "Paid" } },
  { $group: { _id: "$doctor_id", total_revenue: { $sum: "$payment.amount" }, consultations: { $sum: 1 }, avg_bill: { $avg: "$payment.amount" } } },
  { $lookup: { from: "doctors", localField: "_id", foreignField: "_id", as: "doctor" } },
  { $unwind: "$doctor" },
  { $project: { _id: 0, doctor: "$doctor.name", specialization: "$doctor.specialization", consultations: 1,
                total_revenue: { $round: ["$total_revenue", 2] }, avg_bill: { $round: ["$avg_bill", 2] } } },
  { $sort: { total_revenue: -1 } }
]);

// A2 Monthly trend
db.appointments.aggregate([
  { $group: { _id: { $dateToString: { format: "%Y-%m", date: "$appointment_date" } }, total: { $sum: 1 },
              completed: { $sum: { $cond: [{ $eq: ["$status", "Completed"] }, 1, 0] } },
              cancelled: { $sum: { $cond: [{ $eq: ["$status", "Cancelled"] }, 1, 0] } } } },
  { $sort: { _id: 1 } }
]);

// A3 Top-5 medicines
db.appointments.aggregate([
  { $match: { status: "Completed" } }, { $unwind: "$prescription" },
  { $group: { _id: "$prescription.medicine_name", times_prescribed: { $sum: 1 }, units: { $sum: "$prescription.quantity" } } },
  { $sort: { times_prescribed: -1 } }, { $limit: 5 }
]);

// A4 Age groups ($bucket)
db.patients.aggregate([
  { $addFields: { age: { $floor: { $divide: [{ $subtract: ["$$NOW", "$date_of_birth"] }, 31557600000] } } } },
  { $bucket: { groupBy: "$age", boundaries: [0, 13, 19, 36, 51, 66, 120], default: "Other",
               output: { patients: { $sum: 1 } } } }
]);

// A5 Top diagnoses per specialization
db.appointments.aggregate([
  { $match: { status: "Completed" } },
  { $lookup: { from: "doctors", localField: "doctor_id", foreignField: "_id", as: "doc" } }, { $unwind: "$doc" },
  { $group: { _id: { spec: "$doc.specialization", diagnosis: "$diagnosis" }, cases: { $sum: 1 } } },
  { $sort: { cases: -1 } },
  { $group: { _id: "$_id.spec", diagnoses: { $push: { diagnosis: "$_id.diagnosis", cases: "$cases" } } } },
  { $project: { top_diagnoses: { $slice: ["$diagnoses", 3] } } }
]);

// A6 Cancellation rate
db.appointments.aggregate([
  { $match: { status: { $in: ["Completed", "Cancelled", "No-Show"] } } },
  { $group: { _id: "$doctor_id", booked: { $sum: 1 }, lost: { $sum: { $cond: [{ $in: ["$status", ["Cancelled", "No-Show"]] }, 1, 0] } } } },
  { $project: { booked: 1, lost: 1, loss_rate_pct: { $round: [{ $multiply: [{ $divide: ["$lost", "$booked"] }, 100] }, 1] } } },
  { $sort: { loss_rate_pct: -1 } }
]);

// A10 $facet dashboard
db.appointments.aggregate([{ $facet: {
  by_status: [{ $sortByCount: "$status" }],
  revenue: [{ $match: { status: "Completed" } }, { $group: { _id: null, total: { $sum: "$payment.amount" } } }]
}}]);

// A11 Running total ($setWindowFields, MongoDB 5.0+)
db.appointments.aggregate([
  { $match: { status: "Completed" } },
  { $group: { _id: { $dateToString: { format: "%Y-%m", date: "$appointment_date" } }, revenue: { $sum: "$payment.amount" } } },
  { $setWindowFields: { sortBy: { _id: 1 }, output: { cumulative: { $sum: "$revenue", window: { documents: ["unbounded", "current"] } } } } }
]);

// A12 Materialise to a report collection
db.appointments.aggregate([
  { $match: { status: "Completed" } },
  { $group: { _id: { $dateToString: { format: "%Y-%m", date: "$appointment_date" } }, revenue: { $sum: "$payment.amount" }, visits: { $sum: 1 } } },
  { $merge: { into: "monthly_revenue_report", whenMatched: "replace", whenNotMatched: "insert" } }
]);

// -----------------------------------------------------------------------------
// 7. INDEXES & EXPLAIN
// -----------------------------------------------------------------------------
db.appointments.getIndexes();
const d = db.doctors.findOne({ doctor_code: "DOC003" });
db.appointments.find({ doctor_id: d._id, appointment_date: { $gte: ISODate("2026-01-01") } }).explain("executionStats");
// look for: winningPlan.inputStage.stage == "IXSCAN", indexName == "ix_doctor_schedule"
