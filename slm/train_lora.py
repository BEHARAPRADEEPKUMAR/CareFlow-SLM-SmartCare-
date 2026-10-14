import json
from pathlib import Path

import torch
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model


MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "train.jsonl"
OUTPUT_DIR = BASE_DIR / "careflow-lora"


def load_jsonl():
    records = []

    with DATA_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if not line:
                continue

            records.append(json.loads(line))

    return records


def format_messages(example):
    messages = example["messages"]

    formatted = ""

    for message in messages:
        role = message["role"]
        content = message["content"]

        formatted += f"<|im_start|>{role}\n"
        formatted += content
        formatted += "<|im_end|>\n"

    return formatted


def main():
    print("=" * 60)
    print("CareFlow-SLM LoRA Fine-Tuning")
    print("=" * 60)

    print(f"Model: {MODEL_NAME}")
    print(f"Dataset: {DATA_FILE}")
    print(f"Output: {OUTPUT_DIR}")

    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Training dataset not found: {DATA_FILE}\n"
            "Run: python slm/create_dataset.py"
        )

    # ---------------------------------------------------------
    # Load dataset
    # ---------------------------------------------------------

    records = load_jsonl()

    print(f"Training examples: {len(records)}")

    dataset = Dataset.from_list(records)

    dataset = dataset.map(
        lambda item: {
            "text": format_messages(item)
        }
    )

    # ---------------------------------------------------------
    # Load tokenizer
    # ---------------------------------------------------------

    print("Loading tokenizer...")

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        trust_remote_code=True,
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # ---------------------------------------------------------
    # Load base model
    # ---------------------------------------------------------

    print("Loading base model...")

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        dtype=torch.float32,
        trust_remote_code=True,
    )

    model.config.use_cache = False

    # ---------------------------------------------------------
    # LoRA configuration
    # ---------------------------------------------------------

    print("Configuring LoRA...")

    lora_config = LoraConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
        ],
    )

    model = get_peft_model(
        model,
        lora_config,
    )

    model.print_trainable_parameters()

    # ---------------------------------------------------------
    # Tokenization
    # ---------------------------------------------------------

    print("Tokenizing dataset...")

    def tokenize(example):
        return tokenizer(
            example["text"],
            truncation=True,
            max_length=512,
        )

    tokenized_dataset = dataset.map(
        tokenize,
        batched=False,
        remove_columns=dataset.column_names,
    )

    # ---------------------------------------------------------
    # Data collator
    # ---------------------------------------------------------

    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,
    )

    # ---------------------------------------------------------
    # Training configuration
    # ---------------------------------------------------------

    print("Preparing training configuration...")

    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),

        num_train_epochs=5,

        per_device_train_batch_size=1,

        gradient_accumulation_steps=4,

        learning_rate=2e-4,

        logging_steps=1,

        save_strategy="epoch",

        report_to="none",

        fp16=False,

        bf16=False,

        remove_unused_columns=False,
    )

    # ---------------------------------------------------------
    # Trainer
    # ---------------------------------------------------------

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=data_collator,
    )

    print("=" * 60)
    print("Starting LoRA training...")
    print("=" * 60)

    trainer.train()

    # ---------------------------------------------------------
    # Save LoRA adapter
    # ---------------------------------------------------------

    print("=" * 60)
    print("Saving CareFlow-SLM LoRA adapter...")
    print("=" * 60)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    model.save_pretrained(
        OUTPUT_DIR
    )

    tokenizer.save_pretrained(
        OUTPUT_DIR
    )

    print()
    print("=" * 60)
    print("LoRA training completed successfully!")
    print("=" * 60)
    print(f"Adapter saved to:")
    print(OUTPUT_DIR)


if __name__ == "__main__":
    main()