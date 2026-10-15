"""OpenAI-compatible local model transport. No silent model substitution."""

import requests
import config


class LocalModelClient:
    def available_models(self):
        response = requests.get(config.LM_MODELS_URL, timeout=(2, 5))
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", [])
        if not isinstance(rows, list):
            raise RuntimeError("LM Studio вернула некорректный список моделей.")
        return [row["id"] for row in rows if isinstance(row, dict) and row.get("id")]

    def select_model(self):
        models = self.available_models()
        if config.LM_MODEL not in models:
            raise RuntimeError(
                f"Загрузите модель {config.LM_MODEL} в LM Studio. Доступны: {', '.join(models) or 'нет моделей'}."
            )
        return config.LM_MODEL

    def complete(self, model, system_prompt, prompt):
        if not model:
            raise RuntimeError("Модель не выбрана. Сначала проверьте LM Studio.")
        response = requests.post(
            config.LM_STUDIO_URL,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 1500,
            },
            timeout=(5, 300),
        )
        response.raise_for_status()
        choices = response.json().get("choices")
        if not choices:
            raise RuntimeError("LM Studio не вернула choices.")
        content = choices[0].get("message", {}).get("content", "")
        if isinstance(content, list):
            content = "".join(
                str(part.get("text", ""))
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
        return str(content)
