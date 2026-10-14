# CareFlow-SLM

**Vertical AI Healthcare Appointment & Patient Communication System**

> Understand. Automate. Communicate. Faster.

## What this project does

CareFlow-SLM uses a Small Language Model architecture to understand natural-language patient requests and connect them to healthcare appointment workflows.

Core capabilities:
- Appointment booking
- Rescheduling and cancellation
- Doctor availability
- Hospital FAQ / document retrieval
- Appointment reminders
- Safety routing for emergency and medical-diagnosis requests
- AI testing dashboard

## Architecture

Patient → React → Django REST
                    ├── PostgreSQL
                    ├── Safety Layer
                    ├── Workflow Engine
                    └── SLM
                         └── RAG Knowledge Base

Design principle:
- SLM = Understand
- RAG = Knowledge
- PostgreSQL = Live information
- Workflow = Action
- Safety = Guardrail

## Stack

Django + Django REST Framework + PostgreSQL
React + Vite
Transformers + PEFT/LoRA interface
RAG interface
Streamlit
Docker

## Local setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
cp ../.env.example ../.env
```

For the first smoke test, you can set `USE_SQLITE=True` in `.env`.
For the intended project setup, use PostgreSQL and create `careflow_db`.

Then:

```bash
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Backend: http://127.0.0.1:8000

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173

### Streamlit

```bash
cd streamlit
pip install -r requirements.txt
streamlit run app.py
```

Dashboard: http://localhost:8501

## API

- GET `/api/health/`
- GET `/api/doctors/`
- GET `/api/departments/`
- GET `/api/appointments/`
- POST `/api/appointments/`
- POST `/api/chat/`
- POST `/api/safety/check/`

## Example

```json
{
  "message": "I want to book a cardiology appointment tomorrow at 15:00."
}
```

The starter uses a lightweight deterministic parser so the complete app can run before downloading an SLM. Replace it with the LoRA/PEFT inference adapter during the AI phase.

## Safety

This is an appointment and communication system, not a diagnostic or prescribing system. Use synthetic data only. Emergency and medical-treatment requests are routed away from autonomous AI.

## UI

The interface uses a teal + deep-blue palette inspired by the visual direction of the current Veltris website. It does not use Veltris logos, trademarks or proprietary assets. Veltris-inspired styling should be treated as a design reference, not as a claim of affiliation.

## Development roadmap

1. PostgreSQL
2. Authentication/JWT
3. Appointment transactions
4. Real SLM inference
5. Synthetic training dataset
6. LoRA fine-tuning
7. RAG embeddings/vector database
8. Evaluation metrics
9. Docker
10. Free-tier deployment
