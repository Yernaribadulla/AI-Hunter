from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio"
)

response = client.chat.completions.create(
    model="qwen/qwen3-vl-8b",
    messages=[
        {
            "role": "system",
            "content": "Ты помощник по анализу вакансий для поиска работы."
        },
        {
            "role": "user",
            "content": "Коротко оцени вакансию Python Junior Developer для Junior+ AI Automation Developer."
        }
    ],
    temperature=0.2,
)

print(response.choices[0].message.content)