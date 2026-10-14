# SLM Layer

Do not train a language model from scratch.

Recommended path:
1. Select a small instruct model.
2. Create synthetic intent/entity examples.
3. Fine-tune with LoRA/PEFT.
4. Evaluate intent and entity extraction.
5. Connect inference to Django.
6. Keep changing hospital facts in RAG rather than model weights.
