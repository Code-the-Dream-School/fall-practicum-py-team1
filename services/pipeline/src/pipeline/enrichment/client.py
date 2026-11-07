import json

from openai import OpenAI

from pipeline.enrichment.config import OPENAI_MODEL
from pipeline.enrichment.prompts import SYSTEM_PROMPT, build_user_prompt


REQUIRED_FIELDS = {
    "summary",
    "pollutant_analysis",
    "recommendation",
}


class AirQualityEnricher:
    """Generate structured air-quality interpretations using OpenAI."""

    def __init__(self, client=None, model=OPENAI_MODEL):
        self.client = client or OpenAI()
        self.model = model

    def enrich(self, record):
        """Enrich one Gold observation and return a validated dictionary."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(record)},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=400,
        )

        content = response.choices[0].message.content

        if not content:
            raise ValueError("OpenAI returned an empty response")

        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("OpenAI returned invalid JSON") from exc

        if not isinstance(result, dict):
            raise ValueError("OpenAI response must be a JSON object")

        if set(result) != REQUIRED_FIELDS:
            raise ValueError(
                f"OpenAI response must contain exactly: {REQUIRED_FIELDS}"
            )

        for field in REQUIRED_FIELDS:
            if not isinstance(result[field], str) or not result[field].strip():
                raise ValueError(
                    f"OpenAI response field '{field}' must be a non-empty string"
                )

        return result