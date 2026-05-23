# Quickstart

This guide shows the minimum steps to install dependencies and prepare the project before running `main.py`.

## 1. Prerequisites

- Python 3.10 or newer
- PowerShell on Windows
- OpenAI API key

Check Python version:

```powershell
python --version
```

## 2. Create and activate virtual environment

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 3. Install required libraries

Install all required packages from `requirements.txt`:

```powershell
pip install -r requirements.txt
```

Core libraries included:

- `langchain`
- `langchain-openai`
- `python-dotenv`
- `pydantic`

## 4. Prepare environment variables

Create `.env` from `.env.example`:

```powershell
Copy-Item .env.example .env
```

Open `.env` and set at least:

```env
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4.1-mini
OPENAI_TEMPERATURE=0
HYPERPARAMS_PATH=./config/hyperparams.json
SKILL_PATH=./skills
INPUT_PATH=./input
OUTPUT_PATH=./output
POLICY_PATH=./policy
```

## 5. Prepare runtime policy (selection + access)

Selection and access control are configured in one file:

- `policy/storage/runtime_policy.json`

Update these fields before running:

- `active_profile`: policy profile to apply
- Batch execution uses `routes.<route>` to choose skillset and ordered skills.
- `selection` is retained for non-batch/manual compatibility.
- `profiles.<name>.excluded_skills`: skills to skip before execution is scheduled.

Short schema:

```json
{
	"active_profile": "default",
	"selection": {
		"mode": "skill_file",
		"skill_file": "skills/python_quality/code_review.json",
		"skillset": ""
	},
	"routes": {
		"route_a": {
			"profile": "route_a_formio",
			"skillset": "form_quality",
			"skills": [
				"component_quality",
				{ "skill_name": "field_logic_quality", "criterion": "field_logic_quality" }
			]
		}
	},
	"profiles": {
		"route_a_formio": {
			"allowed_skillsets": ["form_quality"],
			"allowed_skills": ["component_quality", "field_logic_quality"],
			"excluded_skills": [],
			"allowed_tools": ["*"]
		}
	}
}
```

Mode behavior:

- Route A runs the ordered skills in `routes.route_a.skills`.
- Route B remains `not_implemented` in this version.

## 6. Prepare input files

Put files to review into `input/`.

Example:

```powershell
Copy-Item .\some_file.py .\input\
```

## 7. Run main.py

Run:

```powershell
python main.py
```

To use skillset mode but skip one skill:

1. Set `selection.mode` to `skillset`
2. Set `selection.skillset` to your skillset name
3. Add that skill name to `profiles.<active_profile>.excluded_skills`

## 8. Check outputs

- Review results are written to `output/<input_filename>.json`
- In-progress markers are created in `input/proceed/` and cleaned after run
- Policy denials are logged to `policy/storage/policy_denials.jsonl`
