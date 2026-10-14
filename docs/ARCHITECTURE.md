# CareFlow-SLM Architecture

```text
React / Streamlit
       |
   Django REST
       |
+------+------+------+
|      |      |      |
DB   SLM    RAG   Safety
|      |      |      |
+------+------+- Workflow
              |
           Response
```

SLM understands the request. RAG supplies approved knowledge. PostgreSQL supplies live state. Workflow performs actions. Safety prevents autonomous medical decisions.
