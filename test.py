
from openai import OpenAI
import os

API_KEY = os.getenv("OPENAI_API_KEY")

try:
    client = OpenAI(api_key=API_KEY)
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "user",
                "content": "Explain Python in 2 simple sentences."
            }
        ],
        max_tokens=100
    )

    print("AI Response:")
    print(response.choices[0].message.content)

except Exception as e:
    print("Error:", str(e))
