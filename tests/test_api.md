# Smoke test

```bash
curl http://127.0.0.1:8000/api/health/
curl http://127.0.0.1:8000/api/doctors/
```

Chat:

```bash
curl -X POST http://127.0.0.1:8000/api/chat/ -H "Content-Type: application/json" -d "{"message":"I want to book a cardiology appointment tomorrow at 15:00"}"
```
