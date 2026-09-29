"""
Script de Treinamento LoRA para o Modelo Laia com Dados dos Pares Cripto.
Pronto para execução no Google Colab com GPU T4 gratuita (ou máquina local com CUDA).

Metodologia:
- Carrega o modelo base Laia / Llama-3.2-1B-Instruct via Unsloth (4-bit QLoRA)
- Aplica adaptadores LoRA (r=16, lora_alpha=16) nas camadas de projeção
- Treina com o dataset data/laia_pairs_training_dataset.jsonl
- Salva o adaptador LoRA e exporta para formato GGUF / Ollama
"""

import os
import json
from datasets import Dataset
from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments

# 1. Configurações de Treinamento
MAX_SEQ_LENGTH = 1024
DTYPE = None  # Detecção automática (Float16 para T4, Bfloat16 para Ampere)
LOAD_IN_4BIT = True
MODEL_NAME = "unsloth/Llama-3.2-1B-Instruct"  # Base do modelo Laia

print(f"[*] Carregando modelo base: {MODEL_NAME}")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_NAME,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=DTYPE,
    load_in_4bit=LOAD_IN_4BIT,
)

# 2. Configurar Adaptador LoRA
print("[*] Injetando adaptadores LoRA PEFT...")
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ],
    lora_alpha=16,
    lora_dropout=0.0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
)

# 3. Preparar Dataset
DATASET_PATH = "laia_pairs_training_dataset.jsonl"
if not os.path.exists(DATASET_PATH):
    # Fallback para o caminho local do projeto se executado no computador
    DATASET_PATH = os.path.join("data", "laia_pairs_training_dataset.jsonl")

print(f"[*] Carregando dataset: {DATASET_PATH}")
raw_samples = []
with open(DATASET_PATH, "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            raw_samples.append(json.loads(line))

# Formatação no padrão Instruct da Laia / Llama-3.2
alpaca_prompt = """<|begin_of_text|><|start_header_id|>system<|end_header_id|>
{}<|eot_id|><|start_header_id|>user<|end_header_id|>
{}<|eot_id|><|start_header_id|>assistant<|end_header_id|>
{}<|eot_id|>"""

formatted_texts = []
for s in raw_samples:
    text = alpaca_prompt.format(s["instruction"], s["input"], s["output"])
    formatted_texts.append(text)

train_dataset = Dataset.from_dict({"text": formatted_texts})
print(f"[*] Total de amostras carregadas: {len(train_dataset)}")

# 4. Configurar Treinamento com SFTTrainer
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=train_dataset,
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LENGTH,
    dataset_num_proc=2,
    packing=False,
    args=TrainingArguments(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=10,
        max_steps=120,  # Treina em ~3 a 5 minutos na GPU T4
        learning_rate=2e-4,
        fp16=not FastLanguageModel.is_bfloat16_supported(),
        bf16=FastLanguageModel.is_bfloat16_supported(),
        logging_steps=10,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=3407,
        output_dir="outputs_laia_lora",
    ),
)

# 5. Executar o Treinamento
print("[*] Iniciando treinamento do LoRA na Laia...")
trainer_stats = trainer.train()
print("[OK] Treinamento concluído com sucesso!")

# 6. Salvar os Pesos do LoRA
SAVE_DIR = "laia_daytrade_lora_model"
print(f"[*] Salvando adaptador LoRA em: {SAVE_DIR}")
model.save_pretrained(SAVE_DIR)
tokenizer.save_pretrained(SAVE_DIR)

# 7. Teste Rápido de Inferência
print("\n=== TESTE DE INFERÊNCIA COM O MODELO ADAPTADO ===")
FastLanguageModel.for_inference(model)
test_prompt = alpaca_prompt.format(
    "Você é a Laia, supervisora de inteligência quantitativa para day trade cripto. Analise o estado dos pares e determine o melhor sinal operacional e viés de risco.",
    "Pares 15m: BTCUSDT variação +1.85%, ETHUSDT variação -0.15%. Volatilidade: Alta. Funding 8h: +0.020%.",
    ""
)
inputs = tokenizer([test_prompt], return_tensors="pt").to("cuda")
outputs = model.generate(**inputs, max_new_tokens=150, use_cache=True)
result_text = tokenizer.batch_decode(outputs)
print(result_text[0].split("<|start_header_id|>assistant<|end_header_id|>")[-1].replace("<|eot_id|>", "").strip())
print("===================================================\n")

# 8. Exportação Opcional para Ollama (GGUF q4_k_m)
# model.save_pretrained_gguf("laia_daytrade_gguf", tokenizer, quantization_method="q4_k_m")
