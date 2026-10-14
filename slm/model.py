from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel


BASE_MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LORA_ADAPTER_PATH = PROJECT_ROOT / "slm" / "careflow-lora"

_tokenizer = None
_model = None


def load_model():
    """
    Load the base Qwen model and attach the trained CareFlow-SLM
    LoRA adapter.
    """

    global _tokenizer, _model

    if _tokenizer is not None and _model is not None:
        return _tokenizer, _model

    print("=" * 60)
    print("Loading CareFlow-SLM")
    print("=" * 60)

    print(f"Base model: {BASE_MODEL_NAME}")
    print(f"LoRA adapter: {LORA_ADAPTER_PATH}")

    if not LORA_ADAPTER_PATH.exists():
        raise FileNotFoundError(
            f"LoRA adapter not found at: {LORA_ADAPTER_PATH}"
        )

    # Load tokenizer
    print("Loading tokenizer...")

    _tokenizer = AutoTokenizer.from_pretrained(
        BASE_MODEL_NAME
    )

    # Load base model
    print("Loading base model...")

    _model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_NAME,
        dtype="auto",
    )

    # Attach LoRA adapter
    print("Loading CareFlow LoRA adapter...")

    _model = PeftModel.from_pretrained(
        _model,
        str(LORA_ADAPTER_PATH),
    )

    _model.eval()

    print("CareFlow-SLM LoRA adapter loaded successfully.")
    print("=" * 60)

    return _tokenizer, _model