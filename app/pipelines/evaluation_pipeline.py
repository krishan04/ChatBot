from transformers import AutoModelForCausalLM, AutoTokenizer
import torch


def evaluate_model(model_path, base_model):

    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForCausalLM.from_pretrained(model_path)

    sample_prompts = [
        "Explain machine learning",
        "What is AI?",
        "Define neural networks"
    ]

    responses = []

    for prompt in sample_prompts:
        inputs = tokenizer(prompt, return_tensors="pt")
        with torch.no_grad():
            outputs = model.generate(**inputs, max_length=50)

        text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        responses.append(text)

    # simple proxy metrics
    avg_length = sum(len(r) for r in responses) / len(responses)

    metrics = {
        "avg_response_length": avg_length,
        "num_samples": len(sample_prompts)
    }

    return metrics
