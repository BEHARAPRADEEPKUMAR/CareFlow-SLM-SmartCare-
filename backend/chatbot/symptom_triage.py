"""
CareFlow symptom triage helper.

This is a lightweight symptom-pattern lookup over the supplied CSV files.
It is NOT a clinically validated diagnostic model and must not prescribe treatment.
"""
import csv
import re
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "medical_symptoms"

DATASET_FILE = DATA_DIR / "dataset.csv"
DESCRIPTION_FILE = DATA_DIR / "symptom_Description.csv"
SEVERITY_FILE = DATA_DIR / "Symptom-severity.csv"

# Map known dataset labels to a clinician specialty. This is only a routing suggestion.
SPECIALTY_MAP = {
    "fungal infection": ("Dermatology", ["rash", "itching", "skin irritation"]),
    "acne": ("Dermatology", ["skin concerns"]),
    "psoriasis": ("Dermatology", ["skin concerns"]),
    "impetigo": ("Dermatology", ["skin concerns"]),
    "allergy": ("General Medicine", ["allergy symptoms"]),
    "drug reaction": ("General Medicine", ["possible medication reaction"]),
    "common cold": ("General Medicine", ["cold symptoms"]),
    "pneumonia": ("Pulmonology", ["respiratory symptoms"]),
    "bronchial asthma": ("Pulmonology", ["breathing or asthma symptoms"]),
    "tuberculosis": ("Pulmonology", ["persistent respiratory symptoms"]),
    "migraine": ("Neurology", ["headache symptoms"]),
    "paralysis (brain hemorrhage)": ("Neurology", ["neurological symptoms"]),
    "hypertension": ("Cardiology", ["blood pressure concerns"]),
    "heart attack": ("Cardiology", ["heart-related symptoms"]),
    "heart disease": ("Cardiology", ["heart-related symptoms"]),
    "diabetes": ("Endocrinology", ["blood sugar concerns"]),
    "hypothyroidism": ("Endocrinology", ["thyroid-related symptoms"]),
    "hyperthyroidism": ("Endocrinology", ["thyroid-related symptoms"]),
    "gastroesophageal reflux disease": ("Gastroenterology", ["digestive symptoms"]),
    "peptic ulcer diseae": ("Gastroenterology", ["digestive symptoms"]),
    "chronic cholestasis": ("Gastroenterology", ["digestive or liver-related symptoms"]),
    "hepatitis a": ("Gastroenterology", ["liver-related symptoms"]),
    "hepatitis b": ("Gastroenterology", ["liver-related symptoms"]),
    "hepatitis c": ("Gastroenterology", ["liver-related symptoms"]),
    "hepatitis d": ("Gastroenterology", ["liver-related symptoms"]),
    "hepatitis e": ("Gastroenterology", ["liver-related symptoms"]),
    "jaundice": ("Gastroenterology", ["liver-related symptoms"]),
    "urinary tract infection": ("Urology", ["urinary symptoms"]),
    "kidney stones": ("Urology", ["urinary or flank symptoms"]),
    "urinary tract infection": ("Urology", ["urinary symptoms"]),
    "arthritis": ("Orthopedics", ["joint symptoms"]),
    "cervical spondylosis": ("Orthopedics", ["neck or spine symptoms"]),
    "osteoarthristis": ("Orthopedics", ["joint symptoms"]),
    "varicose veins": ("Vascular Surgery", ["vein-related symptoms"]),
    "dengue": ("General Medicine", ["fever-related symptoms"]),
    "malaria": ("General Medicine", ["fever-related symptoms"]),
    "typhoid": ("General Medicine", ["fever-related symptoms"]),
    "chicken pox": ("General Medicine", ["rash and fever"]),
    "measles": ("General Medicine", ["rash and fever"]),
    "gastroenteritis": ("Gastroenterology", ["digestive symptoms"]),
}

# Common everyday phrases -> labels used in the supplied dataset.
ALIASES = {
    "itchy": "itching",
    "itchy skin": "itching",
    "skin rash": "skin_rash",
    "rash": "skin_rash",
    "stomach ache": "stomach_pain",
    "stomach pain": "stomach_pain",
    "belly pain": "stomach_pain",
    "throwing up": "vomiting",
    "vomit": "vomiting",
    "feeling sick": "nausea",
    "high temperature": "high_fever",
    "fever": "high_fever",
    "headache": "headache",
    "runny nose": "runny_nose",
    "sneezing": "continuous_sneezing",
    "shortness of breath": "breathlessness",
    "difficulty breathing": "breathlessness",
    "can't breathe": "breathlessness",
    "cannot breathe": "breathlessness",
    "joint pain": "joint_pain",
    "muscle pain": "muscle_pain",
    "back pain": "back_pain",
    "chest tightness": "chest_pain",
    "burning urination": "burning_micturition",
    "painful urination": "burning_micturition",
}

EMERGENCY_TERMS = (
    "chest pain", "heart attack", "difficulty breathing", "shortness of breath",
    "can't breathe", "cannot breathe", "stroke", "unconscious",
    "severe bleeding", "blue lips", "severe allergic reaction",
)


def normalize_name(value):
    value = str(value or "").lower().strip()
    value = value.replace("_", " ")
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def canonical_symptom(value):
    cleaned = normalize_name(value)
    alias = ALIASES.get(cleaned)
    if alias:
        return normalize_name(alias)
    return cleaned


def _read_csv(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Required symptom data file not found: {path}. "
            "Place the supplied CSV files in backend/data/medical_symptoms/."
        )
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _load_data():
    rows = _read_csv(DATASET_FILE)
    description_rows = _read_csv(DESCRIPTION_FILE)
    severity_rows = _read_csv(SEVERITY_FILE)

    symptom_columns = [c for c in rows[0].keys() if c.lower().startswith("symptom_")]
    severity = {
        canonical_symptom(row.get("Symptom")): max(1, int(float(row.get("weight") or 1)))
        for row in severity_rows
        if row.get("Symptom")
    }
    descriptions = {
        normalize_name(row.get("Disease")): (row.get("Description") or "").strip()
        for row in description_rows
        if row.get("Disease")
    }
    diseases = []
    for row in rows:
        disease = (row.get("Disease") or "").strip()
        symptoms = {
            canonical_symptom(row.get(column))
            for column in symptom_columns
            if row.get(column) and str(row.get(column)).strip()
            and str(row.get(column)).strip().lower() != "nan"
        }
        if disease and symptoms:
            diseases.append((disease, symptoms))

    all_symptoms = set()
    for _, symptoms in diseases:
        all_symptoms.update(symptoms)

    return diseases, descriptions, severity, all_symptoms


def _find_symptoms(message, all_symptoms):
    text = normalize_name(message)
    found = set()

    # Match common aliases first. Use phrase boundaries to avoid substring errors.
    for phrase, label in ALIASES.items():
        if re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text):
            normalized_label = canonical_symptom(label)
            if normalized_label in all_symptoms:
                found.add(normalized_label)

    # Then match the dataset's own symptom labels.
    for symptom in all_symptoms:
        if len(symptom) < 3:
            continue
        if re.search(r"(?<!\w)" + re.escape(symptom) + r"(?!\w)", text):
            found.add(symptom)

    return found


def _specialty_for(disease):
    key = normalize_name(disease)
    return SPECIALTY_MAP.get(key, ("General Medicine", ["symptom assessment"]))


def analyze_symptoms(message):
    """
    Return a triage dictionary, or None when there are not enough matching symptoms.
    Emergency language is deliberately left to CareFlow's existing safety layer.
    """
    text = normalize_name(message)
    if any(normalize_name(term) in text for term in EMERGENCY_TERMS):
        return {
            "emergency": True,
            "matched_symptoms": [],
            "possible_conditions": [],
            "recommended_specialty": None,
            "response": (
                "Your message may describe an emergency. Please contact your local "
                "emergency service or seek urgent medical care now. Do not wait for "
                "a chatbot assessment or appointment."
            ),
        }

    diseases, descriptions, severity, all_symptoms = _load_data()
    matched = _find_symptoms(message, all_symptoms)

    # Do not guess from a single generic symptom.
    if len(matched) < 2:
        return None

    total_weight = sum(severity.get(s, 1) for s in matched) or len(matched)
    scores = defaultdict(float)
    for disease, row_symptoms in diseases:
        overlap = matched & row_symptoms
        if not overlap:
            continue
        weighted_overlap = sum(severity.get(s, 1) for s in overlap)
        # A conservative overlap score; not a probability.
        score = weighted_overlap / total_weight
        if len(overlap) >= 2:
            scores[disease] = max(scores[disease], score)

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    # If the dataset does not support a reasonable overlap, ask the patient for details.
    if not ranked or len(matched) < 2 or ranked[0][1] < 0.35:
        return {
            "emergency": False,
            "matched_symptoms": sorted(matched),
            "possible_conditions": [],
            "recommended_specialty": "General Medicine",
            "response": (
                "I recognized these symptoms: "
                + ", ".join(sorted(matched))
                + ". I can't find a sufficiently strong match in the supplied reference "
                "dataset, and I can't diagnose you. A General Medicine clinician can "
                "assess your symptoms. Would you like help finding an appointment?"
            ),
        }

    top_diseases = ranked[:3]
    primary_disease, primary_score = top_diseases[0]
    specialty, rationale = _specialty_for(primary_disease)
    description = descriptions.get(normalize_name(primary_disease), "")

    # Do not expose a numeric score as a medical probability.
    condition_text = ", ".join(name for name, _ in top_diseases)
    description_text = f" Dataset description: {description}" if description else ""
    response = (
        f"I recognized these symptoms: {', '.join(sorted(matched))}. "
        f"Your symptoms overlap with patterns associated with {condition_text} in the "
        f"supplied reference dataset.{description_text} This is not a diagnosis, and "
        "the dataset match is not a probability or a measure of how likely you have "
        "a condition. A qualified clinician should assess your symptoms. "
        f"A reasonable specialty to start with is {specialty}. "
        "Would you like me to look for available appointments?"
    )

    return {
        "emergency": False,
        "matched_symptoms": sorted(matched),
        "possible_conditions": [name for name, _ in top_diseases],
        "recommended_specialty": specialty,
        "response": response,
    }
