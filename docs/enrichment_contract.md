City Air Tracker: Enrichment Contract
Status: Proposed
LLM Provider: OpenAI
Text-generation model: gpt-4o-mini
Initial prompt version: v1

1. Purpose

The enrichment step adds a plain-language explanation to existing Gold air-quality records.
The LLM will generate two text fields that help users understand an air-quality observation without requiring them to interpret numerical measurements themselves.
Enrichment is a separate pipeline step. It does not modify the existing Gold records or recalculate AQI values.

2. Proposed Data Flow

Air_pollution_gold
↓
Select eligible records
↓
Check existing enrichment records
↓
Skip records already successfully enriched
using the current prompt version
↓
Process all remaining eligible historical records
↓
LLM enrichment
↓
Validate model response
↓
Store enrichment results and metadata

3. Gold Records Eligible for Enrichment

A Gold record is eligible for enrichment when it meets all the following conditions:

city is a non-empty string.
latitude is a valid finite numeric value between -90 and 90.
longitude is a valid finite numeric value between -180 and 180.
timestamp is valid.
aqi is an integer between 1 and 5.
At least one pollutant measurement is available and contains a finite numeric value.
The pollutant measurements considered are:
co
no
no2
o3
so2
pm2_5
pm10
nh3
Records to skip
A record will be skipped when:
Required identification or AQI information is missing or invalid.
Coordinates or timestamp are invalid.
All pollutant measurements are missing or unusable.
The record has already been successfully enriched using the current prompt version.
Missing individual pollutant measurements do not disqualify an otherwise eligible record.
Failed enrichment records remain eligible for retry.

4. Enrichment Output Fields

The LLM will generate exactly two fields.

| Field              | Data type | Requirements                                                                       |
| ------------------ | --------- | ---------------------------------------------------------------------------------- |
| `summary`          | String    | A concise plain-language explanation of the air-quality observation.               |
| `data_observation` | String    | One concise factual observation supported by the available pollutant measurements. |

Both fields must contain nonempty strings.

The application will add the following metadata:

| Field            | Data type       | Allowed values or description                              |
| ---------------- | --------------- | ---------------------------------------------------------- |
| `model_name`     | String          | `gpt-4o-mini`                                              |
| `prompt_version` | String          | Version identifier, initially `v1`                         |
| `status`         | String          | `success` or `failed`                                      |
| `enriched_at`    | Timestamp       | Time the enrichment attempt was processed                  |
| `error_message`  | Nullable string | Error description when enrichment fails; `null` on success |

The LLM is responsible only for generating summary and data_observation. The application is responsible for setting metadata and validating the response.

5. LLM Provider and Configuration

Provider: OpenAI
Text-generation model: gpt-4o-mini
Python package: openai
Client: OpenAI()
API method: client.chat.completions.create()
Temperature: 0 for more consistent output
Number of responses: n=1
Maximum completion tokens: 300
Response extraction: response.choices[0].message.content
Each Gold record will be sent as an independent request. Previous records and conversation history will not be included.

API key management:

The API key will be read from the OPENAI_API_KEY environment variable.
A local .env file may be used: OPENAI_API_KEY=our_api_key_here
Load the environment variable using load_dotenv() from python-dotenv.
The .env file must be included in .gitignore and must never be committed to the repository.
The text-embedding-3-small model demonstrated in Python200 is an embedding model and is not required for this text-generation feature.

6. Prompt Instructions and Storage

The prompt will be maintained as a separate text file:

services/pipeline/src/pipeline/enrichment/prompts/air_quality_summary_v1.txt

Initial prompt:

Instructions: 1. Explain the recorded AQI category in clear, concise language. 2. Describe one factual observation supported by the available
pollutant measurements. 3. Use only the values provided in the input. Do not invent
missing measurements or external environmental information. 4. Do not compare different pollutant types by their raw
numerical values because they have different units and
measurement scales. 5. Do not recalculate or modify the AQI or any measurements. 6. Do not provide medical advice, diagnoses, or unsupported
health claims. 7. If a measurement is missing, do not assume its value. 8. Keep the language neutral and understandable to a general
audience.
The Gold record is provided between the delimiters below:

<gold_record>
{gold_record}
</gold_record>

Return only valid JSON with exactly these two keys:

- summary: a concise explanation of the recorded air-quality
  observation.
- data_observation: one concise factual observation based
  on the available measurements.

Both values must be non-empty strings.
Do not include Markdown, code fences, or additional fields.
The prompt will be versioned. When the instructions change, the prompt version must be updated so that records can be enriched again using the new version.

7. Expected LLM Response Format

The LLM must return valid JSON containing exactly two keys:
{
"summary": "The recorded air quality falls in the Moderate category according to the supplied AQI classification.",
"data_observation": "A PM2.5 measurement is available for this observation."
}
This is an illustrative example. Actual output must be based on the values in the Gold record being processed.
The application must parse and validate the response before saving it.

Validation requirements:

Response must be valid JSON.
Both required keys must be present.
No additional keys are allowed.
Both values must be strings.
Neither value may be empty or contain only whitespace.

8. Error Handling and Failure Behavior

The enrichment process must handle unusable model responses and API errors without stopping the entire batch.

| Situation                                       | Expected behavior                                 |
| ----------------------------------------------- | ------------------------------------------------- |
| Valid JSON with both required non-empty strings | Save enrichment with success status.              |
| Empty response                                  | Reject and record failure.                        |
| Invalid JSON                                    | Reject and record validation error.               |
| Missing or unexpected fields                    | Reject and record validation error.               |
| Incorrect field types                           | Reject and record validation error.               |
| Empty required strings                          | Reject and record validation error.               |
| Temporary API error or timeout                  | Retry according to the configured retry policy.   |
| Permanent API or validation error               | Record failure and continue with the next record. |

Only records with status = "success" count as successfully enriched and are skipped during subsequent pipeline runs.
Records with status = "failed" do not count as completed enrichment and remain eligible for retry during a subsequent pipeline run.
When a failed record is retried, the application must ensure that a successful result can be stored without creating duplicate successful enrichment records for the same observation and prompt version.
Failed attempts must never be treated as successful enrichment results.

9. Enrichment Storage and Idempotency

Enrichment results will be stored in a separate database table:
public.air_pollution_enrichment
The existing public.air_pollution_gold table will remain unchanged.

Record identity:

Each enrichment will be associated with its Gold observation using:
latitude
longitude
timestamp
prompt_version
This combination identifies an observation and the prompt version used to enrich it.
A new prompt version can produce a new enrichment for the same observation without overwriting the previous version.

Idempotency rules:

Successfully enriched records must not be processed again for the same prompt version.
Failed records may be retried.
Repeated pipeline runs must not create duplicate successful enrichment records for the same observation and prompt version.
A new prompt version allows the observation to be enriched again.

The database implementation must enforce the agreed uniqueness constraint for this combination.

10. Scope and Limitations

The enrichment feature will:

Read eligible records from the Gold table.
Generate plain-language explanations using the OpenAI API.
Validate the model response.
Store successful results and processing metadata in the separate enrichment table.
Record failures and allow retries.

The enrichment feature will not:

Modify existing Gold records.
Recalculate AQI values.
Change pollutant measurements or their units.
Invent missing measurements.
Retrieve additional environmental data.
Provide medical advice or diagnoses.
Compare pollutant values as if they shared the same measurement scale.

11. Acceptance Criteria

The enrichment contract is considered implemented when:

Only eligible Gold records are sent to the LLM.
Ineligible records are skipped.
The OpenAI provider and gpt-4o-mini model are used.
The prompt is stored separately and has a version identifier.
The LLM returns the required summary and data_observation fields.
Invalid, empty, or malformed responses are rejected.
Successful results and metadata are stored in the separate enrichment table.
Failed attempts are recorded and can be retried.
One failed record does not stop processing of other records.
Repeated runs do not create duplicate successful enrichments for the same observation and prompt version.
The existing Gold table remains unchanged.
