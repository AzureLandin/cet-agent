from openai import OpenAI


class ModelClient:
    def __init__(self, config: dict):
        self.base_url = config["base_url"]
        self.api_key = config["api_key"]
        self.model = config["model"]
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    def chat_completion_stream(self, messages: list[dict]):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
        )
        for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
