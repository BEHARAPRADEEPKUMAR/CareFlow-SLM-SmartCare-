import json
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model


MODEL_NAME = "HuggingFaceTB/SmolLM2-360M-Instruct"

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "datasets" / "careflow_intents.jsonl"
OUTPUT_DIR = BASE_DIR / "careflow-slm-lora"


def format_example(example):
    text = (
        "### Instruction:\n"
        f"{example['instruction']}\n\n"
        "### Input:\n"
        f"{example['input']}\n\n"
        "### Output:\n"
        f"{example['output']}"
    )

    return {"text": text}


def main():
    print("=" * 60)
    print("CareFlow-SLM LoRA Training")
    print("=" * 60)

    print("\nLoading dataset...")

    dataset = load_dataset(
        "json",
        data_files=str(DATA_FILE),
    )

    dataset = dataset["train"]

    print(f"Total examples: {len(dataset)}")

    dataset = dataset.map(
        format_example
    )

    split = dataset.train_test_split(
        test_size=0.15,
        seed=42,
    )

    train_dataset = split["train"]
    eval_dataset = split["test"]

    print(f"Training examples: {len(train_dataset)}")
    print(f"Validation examples: {len(eval_dataset)}")

    print("\nLoading tokenizer...")

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print("Loading base SLM...")

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME
    )

    print("\nConfiguring LoRA...")

    lora_config = LoraConfig(
        r=8,
        lora_alpha=16,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
        ],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(
        model,
        lora_config,
    )

    model.print_trainable_parameters()

    def tokenize_function(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=384,
            padding=False,
        )

    print("\nTokenizing dataset...")

    tokenized_train = train_dataset.map(
        tokenize_function,
        batched=True,
        remove_columns=train_dataset.column_names,
    )

    tokenized_eval = eval_dataset.map(
        tokenize_function,
        batched=True,
        remove_columns=eval_dataset.column_names,
    )

    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,
    )

    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),

        num_train_epochs=3,

        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,

        gradient_accumulation_steps=4,

        learning_rate=2e-4,

        logging_steps=5,

        eval_strategy="epoch",
        save_strategy="epoch",

        save_total_limit=2,

        report_to="none",

        fp16=False,
        bf16=False,

        remove_unused_columns=False,
    )

    trainer = Trainer(
        model=model,
        args=training_args,

        train_dataset=tokenized_train,
        eval_dataset=tokenized_eval,

        data_collator=data_collator,
    )

    print("\nStarting LoRA training...")
    print("This may take some time on CPU.\n")

    trainer.train()

    print("\nSaving LoRA adapter...")

    model.save_pretrained(
        OUTPUT_DIR
    )

    tokenizer.save_pretrained(
        OUTPUT_DIR
    )

    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)

    print(f"\nAdapter saved to:")
    print(OUTPUT_DIR)


if __name__ == "__main__":
    main()