"""
Generate synthetic medical Q&A and device manual CSV datasets.
Produces:
  - medical_q_n_a.csv          (1000 rows)
  - medical_device_manuals_dataset.csv  (1000 rows)
"""

import csv
import random

random.seed(42)

# ---------------------------------------------------------------------------
# Medical Q&A Data
# ---------------------------------------------------------------------------

QNA_TEMPLATES = [
    # --- General / Definition ---
    ("What is {condition}?",
     "{condition} is a medical condition characterized by {description}. It affects the {system} and can lead to {complication} if untreated.",
     "General"),
    ("Define {condition}.",
     "{condition} refers to {description}. It is commonly managed with {treatment} and lifestyle modifications.",
     "General"),
    ("How is {condition} classified?",
     "{condition} is classified into {type1} and {type2} forms based on {criterion}. Each type requires different management approaches.",
     "General"),

    # --- Symptoms ---
    ("What are the symptoms of {condition}?",
     "Common symptoms of {condition} include {symptom1}, {symptom2}, and {symptom3}. Severe cases may also present with {severe_symptom}.",
     "Symptoms"),
    ("How does {condition} present clinically?",
     "Clinically, {condition} presents with {symptom1} and {symptom2}. Patients may also report {symptom3}, especially during {trigger}.",
     "Symptoms"),
    ("What are the early warning signs of {condition}?",
     "Early warning signs of {condition} include {symptom1} and {symptom2}. Recognising these signs early allows for timely intervention.",
     "Symptoms"),

    # --- Treatment ---
    ("How is {condition} treated?",
     "{condition} is treated with {treatment}. In severe cases, {advanced_treatment} may be required. Lifestyle changes including {lifestyle} are also recommended.",
     "Treatment"),
    ("What medications are used for {condition}?",
     "First-line medications for {condition} include {drug1} and {drug2}. Second-line options include {drug3} when first-line therapy is insufficient.",
     "Treatment"),
    ("What is the standard of care for {condition}?",
     "The standard of care for {condition} involves {treatment}, regular monitoring of {marker}, and patient education about {lifestyle}.",
     "Treatment"),

    # --- Diagnosis ---
    ("How is {condition} diagnosed?",
     "{condition} is diagnosed based on clinical presentation, {test1}, and {test2}. A threshold of {threshold} is used to confirm diagnosis.",
     "Diagnosis"),
    ("What tests are used to diagnose {condition}?",
     "Diagnosis of {condition} involves {test1} as the gold standard. Additional tests such as {test2} and {test3} help assess severity.",
     "Diagnosis"),

    # --- Prevention ---
    ("How can {condition} be prevented?",
     "{condition} can be prevented through {prevention1}, {prevention2}, and regular health screenings. Vaccination is available for some forms.",
     "Prevention"),
    ("What lifestyle changes reduce the risk of {condition}?",
     "Reducing risk of {condition} involves {lifestyle}, maintaining a healthy weight, avoiding {risk_factor}, and regular exercise.",
     "Prevention"),

    # --- Complications ---
    ("What complications can arise from {condition}?",
     "Untreated {condition} can lead to {complication1}, {complication2}, and in severe cases {complication3}. Early treatment minimises these risks.",
     "Complications"),

    # --- Medication ---
    ("What is {drug} used for?",
     "{drug} is used to treat {condition} by {mechanism}. It is typically administered {route} and dosage is adjusted based on {marker}.",
     "Medication"),
    ("What are the side effects of {drug}?",
     "Common side effects of {drug} include {side_effect1} and {side_effect2}. Serious but rare side effects include {serious_side_effect}.",
     "Medication"),
    ("How does {drug} work?",
     "{drug} works by {mechanism}. This results in {effect}, which helps manage {condition}.",
     "Medication"),
]

CONDITIONS = [
    ("Diabetes mellitus", "elevated blood glucose levels", "endocrine system", "organ damage",
     "Type 1", "Type 2", "insulin dependency",
     "polyuria", "polydipsia", "fatigue", "blurred vision", "hyperglycaemic crisis",
     "insulin therapy", "oral hypoglycaemics", "dietary control",
     "HbA1c measurement", "fasting glucose test", "oral glucose tolerance test", "6.5% HbA1c",
     "weight management", "low-sugar diet", "smoking", "hyperglycaemia onset",
     "diabetic nephropathy", "peripheral neuropathy", "cardiovascular disease",
     "Metformin", "blood glucose", "oral", "renal function"),

    ("Hypertension", "persistently elevated blood pressure above 130/80 mmHg", "cardiovascular system", "stroke or heart attack",
     "primary (essential)", "secondary", "cause",
     "headaches", "shortness of breath", "nosebleeds", "visual disturbances", "hypertensive crisis",
     "antihypertensive medications", "catheter-based renal denervation", "DASH diet",
     "blood pressure measurement", "ambulatory blood pressure monitoring", "echocardiogram", "140/90 mmHg",
     "reducing sodium intake", "regular aerobic exercise", "excessive alcohol", "morning hours",
     "left ventricular hypertrophy", "chronic kidney disease", "retinal damage",
     "Lisinopril", "blood pressure", "oral", "potassium levels"),

    ("Asthma", "chronic inflammation of the airways leading to reversible obstruction", "respiratory system", "respiratory failure",
     "allergic", "non-allergic", "trigger exposure",
     "wheezing", "chest tightness", "shortness of breath", "nocturnal cough", "status asthmaticus",
     "inhaled corticosteroids", "bronchial thermoplasty", "trigger avoidance",
     "spirometry", "peak flow measurement", "bronchial challenge test", "FEV1/FVC ratio below 0.7",
     "avoiding allergens", "using air purifiers", "NSAIDs", "exercise",
     "airway remodelling", "pneumonia", "respiratory failure",
     "Salbutamol", "FEV1", "inhaled", "inhaler technique"),

    ("Chronic Kidney Disease", "progressive loss of kidney function over months or years", "renal system", "end-stage renal disease",
     "diabetic", "hypertensive", "underlying cause",
     "fatigue", "swollen ankles", "decreased urine output", "nausea", "uraemic encephalopathy",
     "ACE inhibitors", "dialysis or transplantation", "fluid and protein restriction",
     "serum creatinine", "eGFR calculation", "kidney biopsy", "eGFR below 60 mL/min",
     "blood pressure control", "glycaemic control", "nephrotoxic drugs", "prolonged periods",
     "cardiovascular disease", "anaemia", "metabolic acidosis",
     "Furosemide", "eGFR", "oral", "electrolyte balance"),

    ("Myocardial Infarction", "irreversible necrosis of heart muscle due to prolonged ischaemia", "cardiovascular system", "heart failure",
     "STEMI", "NSTEMI", "ECG findings",
     "chest pain", "radiation to left arm", "diaphoresis", "nausea", "cardiogenic shock",
     "percutaneous coronary intervention", "coronary artery bypass grafting", "cardiac rehabilitation",
     "ECG", "troponin levels", "coronary angiography", "troponin elevation above 99th percentile",
     "smoking cessation", "statin therapy", "heavy exertion", "morning",
     "heart failure", "arrhythmias", "sudden cardiac death",
     "Aspirin", "troponin", "oral", "renal function"),

    ("Pneumonia", "infection causing inflammation of the air sacs in one or both lungs", "respiratory system", "sepsis",
     "community-acquired", "hospital-acquired", "acquisition setting",
     "fever", "productive cough", "pleuritic chest pain", "dyspnoea", "septic shock",
     "antibiotics", "mechanical ventilation", "oxygen supplementation",
     "chest X-ray", "sputum culture", "blood cultures", "infiltrate on chest X-ray",
     "pneumococcal vaccination", "influenza vaccination", "smoking", "immunocompromised states",
     "lung abscess", "empyema", "respiratory failure",
     "Amoxicillin", "oxygen saturation", "oral or IV", "liver function"),

    ("Stroke", "interruption of blood supply to the brain causing neurological deficits", "nervous system", "permanent disability",
     "ischaemic", "haemorrhagic", "pathophysiology",
     "sudden facial droop", "arm weakness", "speech difficulty", "vision loss", "coma",
     "thrombolysis", "mechanical thrombectomy", "neurorehabilitation",
     "CT brain scan", "MRI brain", "carotid ultrasound", "occlusion on imaging",
     "anticoagulation therapy", "blood pressure control", "atrial fibrillation", "acute onset",
     "post-stroke depression", "aspiration pneumonia", "deep vein thrombosis",
     "Alteplase", "NIH Stroke Scale", "IV", "coagulation profile"),

    ("Osteoporosis", "reduction in bone mineral density increasing fracture risk", "musculoskeletal system", "pathological fractures",
     "primary", "secondary", "bone mineral density",
     "back pain", "loss of height", "stooped posture", "bone fractures", "vertebral collapse",
     "bisphosphonates", "parathyroid hormone analogues", "calcium and vitamin D supplementation",
     "DEXA scan", "bone turnover markers", "vertebral X-ray", "T-score below -2.5",
     "weight-bearing exercise", "adequate calcium intake", "smoking", "falls",
     "hip fracture", "vertebral fracture", "chronic pain",
     "Alendronate", "bone mineral density", "oral", "renal function"),

    ("Rheumatoid Arthritis", "chronic autoimmune inflammatory disease primarily affecting synovial joints", "musculoskeletal system", "joint deformity",
     "seropositive", "seronegative", "rheumatoid factor status",
     "joint pain", "morning stiffness", "joint swelling", "fatigue", "systemic vasculitis",
     "disease-modifying antirheumatic drugs", "biologic therapy", "joint replacement",
     "rheumatoid factor", "anti-CCP antibodies", "joint X-ray", "DAS28 score above 5.1",
     "early DMARD initiation", "smoking cessation", "joint overuse", "cold weather",
     "joint erosion", "carpal tunnel syndrome", "cardiovascular disease",
     "Methotrexate", "CRP and ESR", "oral", "liver function"),

    ("Depression", "persistent low mood and loss of interest significantly impairing daily functioning", "neurological and psychiatric system", "suicide",
     "unipolar", "bipolar", "episode pattern",
     "persistent sadness", "loss of interest", "sleep disturbance", "fatigue", "suicidal ideation",
     "antidepressants", "electroconvulsive therapy", "cognitive behavioural therapy",
     "PHQ-9 questionnaire", "clinical interview", "thyroid function tests", "PHQ-9 score above 10",
     "regular exercise", "social support", "substance misuse", "chronic stress",
     "self-harm", "social isolation", "substance misuse",
     "Sertraline", "symptom severity", "oral", "liver function"),

    ("Hyperthyroidism", "excessive production of thyroid hormones causing accelerated metabolism", "endocrine system", "thyroid storm",
     "Graves disease", "toxic nodular goitre", "TSH suppression",
     "weight loss", "palpitations", "heat intolerance", "tremor", "thyroid storm",
     "antithyroid drugs", "radioactive iodine therapy", "thyroidectomy",
     "TSH level", "free T4 and T3", "thyroid ultrasound", "TSH below 0.1 mIU/L",
     "avoiding iodine excess", "regular thyroid monitoring", "iodine supplementation", "stress",
     "atrial fibrillation", "osteoporosis", "heart failure",
     "Carbimazole", "TSH", "oral", "liver function"),

    ("Epilepsy", "neurological disorder characterised by recurrent unprovoked seizures", "nervous system", "status epilepticus",
     "focal", "generalised", "seizure onset zone",
     "seizures", "transient confusion", "staring spells", "uncontrollable jerking", "prolonged seizures",
     "antiepileptic drugs", "epilepsy surgery", "vagus nerve stimulation",
     "EEG", "MRI brain", "blood glucose and electrolytes", "abnormal EEG activity",
     "medication compliance", "sleep hygiene", "flickering lights", "sleep deprivation",
     "status epilepticus", "traumatic injury during seizures", "sudden unexpected death in epilepsy",
     "Levetiracetam", "seizure frequency", "oral", "renal function"),

    ("Chronic Obstructive Pulmonary Disease", "progressive airflow limitation caused by airway and alveolar abnormalities from smoking", "respiratory system", "respiratory failure",
     "chronic bronchitis", "emphysema", "predominant pathology",
     "chronic cough", "sputum production", "dyspnoea", "wheezing", "acute exacerbation",
     "bronchodilators", "pulmonary rehabilitation", "supplemental oxygen",
     "spirometry", "chest X-ray", "arterial blood gas", "FEV1/FVC ratio below 0.7",
     "smoking cessation", "pulmonary rehabilitation", "continued smoking", "cold air",
     "pulmonary hypertension", "polycythaemia", "respiratory failure",
     "Tiotropium", "FEV1", "inhaled", "cardiovascular status"),

    ("Heart Failure", "condition where the heart cannot pump enough blood to meet body requirements", "cardiovascular system", "cardiogenic shock",
     "systolic", "diastolic", "ejection fraction",
     "breathlessness", "ankle swelling", "fatigue", "orthopnoea", "flash pulmonary oedema",
     "diuretics", "cardiac resynchronisation therapy", "heart transplantation",
     "echocardiogram", "BNP levels", "chest X-ray", "ejection fraction below 40%",
     "fluid restriction", "daily weight monitoring", "excessive salt intake", "heavy exertion",
     "atrial fibrillation", "renal impairment", "sudden cardiac death",
     "Furosemide", "BNP", "oral or IV", "renal and electrolyte function"),

    ("Anaemia", "reduction in haemoglobin concentration below normal reference range", "haematological system", "heart failure",
     "microcytic", "normocytic", "macrocytic",
     "fatigue", "pallor", "shortness of breath", "palpitations", "heart failure",
     "iron supplementation", "blood transfusion", "erythropoiesis-stimulating agents",
     "full blood count", "ferritin level", "peripheral blood film", "haemoglobin below 120 g/L in women",
     "adequate dietary iron", "treating underlying causes", "NSAIDs without gastroprotection", "heavy menstruation",
     "cardiac decompensation", "cognitive impairment", "impaired immune function",
     "Ferrous sulphate", "haemoglobin", "oral", "gastrointestinal tolerance"),

    ("Kawasaki Disease", "acute systemic vasculitis predominantly affecting medium-sized blood vessels in children", "cardiovascular and immune system", "coronary artery aneurysms",
     "complete", "incomplete", "clinical criteria fulfilment",
     "prolonged fever", "rash", "conjunctival injection", "strawberry tongue", "cervical lymphadenopathy",
     "intravenous immunoglobulin (IVIG) and high-dose aspirin", "infliximab or corticosteroids", "fever monitoring and cardiac follow-up",
     "echocardiogram", "inflammatory markers (CRP, ESR)", "complete blood count", "fever lasting more than 5 days with 4 of 5 clinical criteria",
     "early IVIG administration within 10 days of fever onset", "regular echocardiographic follow-up", "delayed diagnosis", "fever onset",
     "coronary artery aneurysms", "myocarditis", "long-term cardiovascular disease",
     "Aspirin", "CRP and platelet count", "oral or IV", "cardiac function"),

    ("Lupus", "chronic autoimmune disease causing systemic inflammation affecting multiple organs", "immune system", "organ failure",
     "systemic lupus erythematosus", "drug-induced lupus", "autoantibody profile",
     "butterfly rash", "joint pain", "fatigue", "photosensitivity", "lupus nephritis",
     "hydroxychloroquine", "high-dose corticosteroids and cyclophosphamide", "sun protection and trigger avoidance",
     "ANA test", "anti-dsDNA antibodies", "complement levels (C3/C4)", "positive ANA with clinical criteria",
     "sun protection", "regular organ function monitoring", "UV exposure", "infection",
     "lupus nephritis", "pericarditis", "neuropsychiatric lupus",
     "Hydroxychloroquine", "anti-dsDNA titres", "oral", "ophthalmological monitoring"),
]

DRUGS_STANDALONE = [
    ("Warfarin", "atrial fibrillation and venous thromboembolism", "inhibiting vitamin K-dependent clotting factors",
     "oral anticoagulation", "oral", "INR", "bleeding tendency", "bruising", "intracranial haemorrhage"),
    ("Atorvastatin", "hypercholesterolaemia and cardiovascular risk reduction", "inhibiting HMG-CoA reductase",
     "LDL reduction", "oral", "lipid profile", "myalgia", "headache", "rhabdomyolysis"),
    ("Amoxicillin", "bacterial infections including pneumonia and urinary tract infections", "inhibiting bacterial cell wall synthesis",
     "antibacterial activity", "oral or IV", "culture and sensitivity", "diarrhoea", "rash", "anaphylaxis"),
    ("Omeprazole", "peptic ulcer disease and gastro-oesophageal reflux disease", "blocking the proton pump in gastric parietal cells",
     "acid suppression", "oral", "symptom response", "headache", "diarrhoea", "hypomagnesaemia"),
    ("Salbutamol", "acute bronchospasm in asthma and COPD", "stimulating beta-2 adrenoceptors in bronchial smooth muscle",
     "bronchodilation", "inhaled", "peak flow rate", "tremor", "tachycardia", "hypokalaemia"),
]

def make_qna_rows(n=1000):
    rows = []

    # Generate all condition × template combinations (17 × 17 = 289 unique Q/A pairs)
    for cond in CONDITIONS:
        (condition, description, system, complication,
         type1, type2, criterion,
         symptom1, symptom2, symptom3, severe_symptom, crisis,
         treatment, advanced_treatment, lifestyle,
         test1, test2, test3, threshold,
         prevention1, prevention2, risk_factor, trigger,
         complication1, complication2, complication3,
         drug, marker, route, monitoring) = cond

        for q_tmpl, a_tmpl, qtype in QNA_TEMPLATES:
            q = q_tmpl.format(
                condition=condition, drug=drug, description=description,
                system=system, complication=complication,
            )
            a = a_tmpl.format(
                condition=condition, description=description, system=system,
                complication=complication, type1=type1, type2=type2, criterion=criterion,
                symptom1=symptom1, symptom2=symptom2, symptom3=symptom3,
                severe_symptom=severe_symptom, trigger=trigger,
                treatment=treatment, advanced_treatment=advanced_treatment, lifestyle=lifestyle,
                test1=test1, test2=test2, test3=test3, threshold=threshold,
                prevention1=prevention1, prevention2=prevention2, risk_factor=risk_factor,
                complication1=complication1, complication2=complication2, complication3=complication3,
                drug=drug, drug1=drug, drug2=monitoring, drug3=advanced_treatment,
                marker=marker, route=route, mechanism=f"inhibiting {system} pathways",
                effect=f"reducing {symptom1}", side_effect1=symptom1, side_effect2=symptom2,
                serious_side_effect=complication1,
            )
            rows.append({"Question": q, "Answer": a, "qtype": qtype})

    # Drug-specific rows (5 drugs × 3 templates = 15 more unique entries)
    for drug, cond_name, mech, effect, route, marker, se1, se2, serious in DRUGS_STANDALONE:
        rows.append({"Question": f"What is {drug} used for?",
                     "Answer": f"{drug} is used to treat {cond_name} by {mech}. "
                               f"It is typically administered {route} and dosage is adjusted based on {marker}.",
                     "qtype": "Medication"})
        rows.append({"Question": f"What are the side effects of {drug}?",
                     "Answer": f"Common side effects of {drug} include {se1} and {se2}. "
                               f"Serious but rare side effects include {serious}.",
                     "qtype": "Medication"})
        rows.append({"Question": f"How does {drug} work?",
                     "Answer": f"{drug} works by {mech}. This results in {effect}, "
                               f"which helps manage {cond_name}.",
                     "qtype": "Medication"})

    # Shuffle and pad/trim to n
    random.shuffle(rows)
    while len(rows) < n:
        rows.extend(rows[:n - len(rows)])
    return rows[:n]


# ---------------------------------------------------------------------------
# Medical Device Data
# ---------------------------------------------------------------------------

DEVICE_TEMPLATES = [
    # (Device_Name, Model_Number, Manufacturer, Indications_for_Use, Contraindications)
    ("Implantable Cardioverter Defibrillator", "ICD-{n}", "{mfr}",
     "Indicated for patients with ventricular tachycardia or fibrillation, survivors of sudden cardiac arrest, or those at high risk of life-threatening arrhythmias.",
     "Contraindicated in patients with reversible causes of arrhythmia, active systemic infection, or life expectancy less than one year."),

    ("Pacemaker", "PM-{n}", "{mfr}",
     "Indicated for symptomatic bradycardia, complete heart block, sick sinus syndrome, and other conditions requiring sustained cardiac pacing.",
     "Contraindicated in patients with demand-type devices exposed to strong electromagnetic fields without shielding; not recommended in active sepsis."),

    ("Continuous Positive Airway Pressure Device", "CPAP-{n}", "{mfr}",
     "Indicated for obstructive sleep apnoea, central sleep apnoea, and respiratory insufficiency requiring non-invasive ventilatory support.",
     "Contraindicated in patients with cerebrospinal fluid leaks, recent facial or skull surgery, or severe bullous lung disease."),

    ("Haemodialysis Machine", "HD-{n}", "{mfr}",
     "Indicated for patients with end-stage renal disease, acute kidney injury requiring renal replacement therapy, or severe electrolyte imbalances.",
     "Contraindicated in haemodynamically unstable patients unable to tolerate extracorporeal circulation; relative contraindication in active haemorrhage."),

    ("Infusion Pump", "IP-{n}", "{mfr}",
     "Indicated for controlled delivery of intravenous fluids, chemotherapy, antibiotics, analgesics, and other medications requiring precise dosing.",
     "Contraindicated for medications incompatible with the pump tubing material; do not use without appropriate clinical supervision."),

    ("Mechanical Ventilator", "MV-{n}", "{mfr}",
     "Indicated for respiratory failure, post-operative ventilatory support, neuromuscular disease, and patients unable to maintain adequate spontaneous ventilation.",
     "Contraindicated in patients with untreated tension pneumothorax; use with caution in severe bullous emphysema."),

    ("Automated External Defibrillator", "AED-{n}", "{mfr}",
     "Indicated for use in cardiac arrest with shockable rhythms including ventricular fibrillation and pulseless ventricular tachycardia.",
     "Do not use on patients with a detectable pulse. Avoid placement over implanted devices or transdermal medication patches."),

    ("Blood Glucose Monitor", "BGM-{n}", "{mfr}",
     "Indicated for self-monitoring of blood glucose in patients with diabetes mellitus type 1 and type 2 requiring glycaemic management.",
     "Not intended for use in critically ill patients where laboratory measurements are required. Haematocrit extremes may affect accuracy."),

    ("Pulse Oximeter", "PO-{n}", "{mfr}",
     "Indicated for continuous or spot-check monitoring of peripheral oxygen saturation and pulse rate in clinical and home settings.",
     "May be inaccurate in patients with poor peripheral perfusion, carbon monoxide poisoning, severe anaemia, or darkly pigmented skin."),

    ("Electrocardiograph", "ECG-{n}", "{mfr}",
     "Indicated for recording cardiac electrical activity to diagnose arrhythmias, myocardial infarction, conduction abnormalities, and electrolyte disturbances.",
     "No absolute contraindications. Avoid electrode placement over broken skin or wounds. Results may be affected by motion artefact."),

    ("Ultrasound Scanner", "US-{n}", "{mfr}",
     "Indicated for diagnostic imaging of abdominal organs, cardiac structures, vascular anatomy, obstetric assessment, and guided interventional procedures.",
     "No ionising radiation; generally safe in pregnancy. Avoid direct coupling gel contact with open wounds without appropriate barrier."),

    ("CT Scanner", "CT-{n}", "{mfr}",
     "Indicated for detailed cross-sectional imaging of the brain, chest, abdomen, pelvis, and musculoskeletal system for diagnosis and treatment planning.",
     "Contraindicated in pregnancy unless benefits outweigh risks. Contrast agents contraindicated in severe renal impairment or contrast allergy without premedication."),

    ("MRI Scanner", "MRI-{n}", "{mfr}",
     "Indicated for soft tissue characterisation, neurological imaging, cardiac assessment, and musculoskeletal evaluation without ionising radiation.",
     "Contraindicated in patients with ferromagnetic implants, certain pacemakers, cochlear implants, or claustrophobia without sedation."),

    ("Nebuliser", "NEB-{n}", "{mfr}",
     "Indicated for delivery of aerosolised medications including bronchodilators, corticosteroids, and mucolytics to patients with respiratory conditions.",
     "Ensure medication compatibility with nebuliser components. Not recommended as sole treatment in severe acute asthma without concurrent therapy."),

    ("Syringe Driver", "SD-{n}", "{mfr}",
     "Indicated for continuous subcutaneous infusion of medications including analgesics, antiemetics, and sedatives in palliative and acute care settings.",
     "Contraindicated for medications with known incompatibilities in the same syringe. Regular site inspection required to prevent subcutaneous reactions."),

    ("Defibrillator Monitor", "DM-{n}", "{mfr}",
     "Indicated for cardiac rhythm monitoring and emergency defibrillation in intensive care units, emergency departments, and during transport.",
     "Ensure gel pads are not placed over implanted devices. Do not use in flammable anaesthetic environments."),

    ("Insulin Pump", "INS-{n}", "{mfr}",
     "Indicated for continuous subcutaneous insulin infusion in patients with type 1 diabetes or type 2 diabetes requiring intensive insulin therapy.",
     "Contraindicated in patients unable or unwilling to perform frequent blood glucose monitoring. Risk of diabetic ketoacidosis with pump failure."),

    ("Endoscope", "ENDO-{n}", "{mfr}",
     "Indicated for diagnostic and therapeutic gastrointestinal procedures including colonoscopy, gastroscopy, and ERCP.",
     "Contraindicated in suspected bowel perforation, patient refusal, or haemodynamic instability precluding safe sedation."),

    ("Surgical Robot", "SR-{n}", "{mfr}",
     "Indicated for minimally invasive surgical procedures including prostatectomy, hysterectomy, and bariatric surgery requiring precision manipulation.",
     "Contraindicated in patients unable to tolerate general anaesthesia or Trendelenburg positioning. Operator training mandatory."),

    ("Phototherapy Unit", "PT-{n}", "{mfr}",
     "Indicated for treatment of neonatal jaundice, psoriasis, atopic eczema, and other photosensitive dermatological conditions.",
     "Contraindicated in patients with porphyria, lupus, or those taking photosensitising medications without medical supervision."),
]

MANUFACTURERS = [
    "MedTech Solutions", "BioDevice Corp", "ClinicalPro Ltd", "HeartCare Systems",
    "PulmoTech Inc", "NeuroCare Devices", "SurgicalPro Ltd", "DiagnosticPlus",
    "VitalSigns Corp", "ImplantTech Ltd", "CriticalCare Systems", "PrecisionMed Inc",
]

def make_device_rows(n=1000):
    rows = []
    idx = 0
    while len(rows) < n:
        template = DEVICE_TEMPLATES[idx % len(DEVICE_TEMPLATES)]
        device_name, model_tmpl, _, indications, contraindications = template
        num = str(1000 + idx).zfill(5)
        mfr = MANUFACTURERS[idx % len(MANUFACTURERS)]
        model = model_tmpl.format(n=num)
        rows.append({
            "Device_Name": device_name,
            "Model_Number": model,
            "Manufacturer": mfr,
            "Indications_for_Use": indications,
            "Contraindications": contraindications,
        })
        idx += 1
    return rows[:n]


# ---------------------------------------------------------------------------
# Write CSV files
# ---------------------------------------------------------------------------
def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Written {len(rows)} rows to {path}")


GUARANTEED_QNA = [
    # Kawasaki Disease
    {"Question": "What are treatments for Kawasaki disease?",
     "Answer": "Kawasaki disease is treated with high-dose aspirin and intravenous immunoglobulin (IVIG) given within 10 days of fever onset to reduce inflammation and prevent coronary artery aneurysms. Aspirin is later continued at low dose. Infliximab or corticosteroids may be used in IVIG-resistant cases. Echocardiographic follow-up is essential.",
     "qtype": "Treatment"},
    {"Question": "What is Kawasaki disease?",
     "Answer": "Kawasaki disease is an acute systemic vasculitis that primarily affects medium-sized blood vessels in children under five. It causes prolonged fever, rash, conjunctival injection, strawberry tongue, and cervical lymphadenopathy. The most serious complication is coronary artery aneurysms, which can lead to long-term cardiovascular disease if untreated.",
     "qtype": "General"},
    {"Question": "What are the symptoms of Kawasaki disease?",
     "Answer": "Kawasaki disease presents with fever lasting more than 5 days, bilateral non-exudative conjunctival injection, rash, changes to the lips and oral mucosa (strawberry tongue, cracked lips), erythema of the palms and soles with subsequent desquamation, and cervical lymphadenopathy. Cardiac involvement may cause myocarditis and coronary aneurysms.",
     "qtype": "Symptoms"},
    {"Question": "How is Kawasaki disease diagnosed?",
     "Answer": "Kawasaki disease is diagnosed clinically: fever for at least 5 days plus at least 4 of 5 criteria (conjunctival injection, oral changes, rash, extremity changes, cervical lymphadenopathy). Lab findings include elevated CRP, ESR, and platelet count. Echocardiogram is essential to assess for coronary artery aneurysms.",
     "qtype": "Diagnosis"},
    {"Question": "What complications can arise from Kawasaki disease?",
     "Answer": "The most serious complication of Kawasaki disease is coronary artery aneurysms, which occur in up to 25% of untreated cases. Other complications include myocarditis, pericarditis, arrhythmias, and long-term cardiovascular disease. Early treatment with IVIG significantly reduces the risk of coronary complications.",
     "qtype": "Complications"},
    # Lupus
    {"Question": "What are treatments for Lupus?",
     "Answer": "Lupus (SLE) is managed with hydroxychloroquine as a baseline therapy for all patients. Mild disease is treated with NSAIDs or low-dose corticosteroids. Severe organ-threatening disease requires high-dose corticosteroids with immunosuppressants such as mycophenolate mofetil, azathioprine, or cyclophosphamide. Belimumab is a targeted biologic option.",
     "qtype": "Treatment"},
]


if __name__ == "__main__":
    qna_rows = make_qna_rows(1000)
    # Prepend guaranteed rows so they are always sampled
    qna_rows = GUARANTEED_QNA + qna_rows[len(GUARANTEED_QNA):]
    write_csv("medical_q_n_a.csv", qna_rows, ["Question", "Answer", "qtype"])

    device_rows = make_device_rows(1000)
    write_csv("medical_device_manuals_dataset.csv", device_rows,
              ["Device_Name", "Model_Number", "Manufacturer", "Indications_for_Use", "Contraindications"])

    print("Done. Both CSV files are ready for ingestion.")
