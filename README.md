# LangChain Agent-Skill Batch Reviewer

This project processes source files placed in input/, applies a selected skillset folder or a specific skill file, and writes one JSON result per input file into output/.

## What changed

- Skill definitions are JSON only and grouped by skillset folder.
- skill_registry.json and skillset description.json files are rebuilt automatically on every run.
- Input files are tracked transiently in input/proceed/ while the run is active.
- Output files are written as output/<input_file_name>.json.
- Agent input trace files are written as output/agent_inputs/<input_file_name>.agent-input.json while each routed file is processed.
- config/hyperparams.json is recreated automatically if it is deleted.
- policy/PAP, PDP, and PEP folders provide enforcement functions for skill and tool access.
- Policy selection and access are configured in one runtime policy file.

## Project structure

~~~text
project_root/
├─ .env.example
├─ .gitignore
├─ requirements.txt
├─ README.md
├─ main.py
├─ agents/
│  ├─ review_prompt.py
│  └─ __init__.py
├─ config/
│  ├─ hyperparams.json
│  └─ settings.py
├─ input/
│  └─ proceed/
├─ output/
├─ skills/
│  ├─ python_quality/
│  │  ├─ description.json
│  │  ├─ code_review.json
│  │  └─ bug_fix.json
│  └─ skill_registry.json
├─ policy/
│  ├─ __init__.py
│  ├─ errors.py
│  ├─ utils.py
│  ├─ PAP/
│  │  ├─ __init__.py
│  │  └─ controller.py
│  ├─ PDP/
│  │  ├─ __init__.py
│  │  └─ controller.py
│  ├─ PEP/
│  │  ├─ __init__.py
│  │  ├─ controller.py
│  │  └─ enforcement.py
│  ├─ shared/
│  │  ├─ __init__.py
│  │  ├─ identity.py
│  │  └─ models.py
│  └─ storage/
│     ├─ base.json
│     ├─ runtime_policy.json
│     └─ policy_denials.jsonl
├─ tools/
│  ├─ __init__.py
│  ├─ file_tools.py
│  ├─ hyperparam_tools.py
│  └─ skill_loader.py
└─ utils/
	 ├─ config_loader.py
	 ├─ env_loader.py
	 └─ logger.py
~~~

## Setup

### 1. Create and activate a virtual environment

~~~powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
~~~

### 2. Install dependencies

~~~powershell
pip install -r requirements.txt
~~~

### 3. Configure environment variables

Copy .env.example to .env and set your API key.

~~~env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
OPENAI_TEMPERATURE=0
HYPERPARAMS_PATH=./config/hyperparams.json
SKILL_PATH=./skills
INPUT_PATH=./input
OUTPUT_PATH=./output
POLICY_PATH=./policy
~~~

## How to run

1. Put source files to review into input/.
2. Configure `policy/storage/runtime_policy.json`:

- Set `active_profile`
- Set `selection.mode` to `skill_file` or `skillset`
- Set selected `skill_file` or `skillset`
- Optionally set `excluded_skills` in the active profile

3. Run the reviewer.

~~~powershell
python main.py
~~~

4. Read the generated JSON files in output/.

During routed execution, inspect `output/agent_inputs/` to see the exact prompt messages sent to the agent for each allowed skill. Each trace file is JSON and is updated as the workflow moves from one skill to the next.

## Runtime policy schema (short)

`policy/storage/runtime_policy.json`

~~~json
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
~~~

Notes:

- Batch execution uses `routes.<route>`, not `selection`.
- `selection` is kept for non-batch/manual compatibility.
- `routes.<route>.skills` controls the ordered skills run for that route.
- `profiles.<name>.excluded_skills` removes skills before execution is scheduled.
- `output/agent_inputs/<input_file_name>.agent-input.json` records each agent message as `prompt_template`, `template_values`, and rendered `prompt_text`.

## Output schema

Each output file is written to `output/<input_file_name>.json`.

~~~json
{
  "file_name": "input_formio_sample.json",
  "route": "route_a",
  "route_match": {
    "route": "route_a",
    "pattern": "^input_formio.*\\.json$"
  },
  "workflow": "generic_review",
  "overall_status": "passed",
  "checks": [
    {
      "skill_id": "component_quality",
      "criterion": "component_quality",
      "status": "passed",
      "reason": "No failed checks found",
      "locations": [],
      "evidence": {
        "A1": {
          "Status": "PASSED",
          "Note / Feedback": ""
        }
      }
    }
  ],
  "policy_events": [],
  "errors": []
}
~~~

The agent response is stored under `checks[].evidence`. The workflow converts failed check IDs to `status`, `reason`, and `locations`.

## Skill file format

Skill files live under `skills/<skillset_name>/<skill_name>.json`. The file name without `.json` becomes the skill name used by registry and policy. For example, `skills/form_quality/component_quality.json` becomes `component_quality`.

Every skill JSON must contain these top-level fields:

- `description`: short summary used in `description.json` and `skill_registry.json`.
- `goal`: what the reviewer must decide.
- `procedure`: ordered instructions for the reviewer.
- `output_style`: output rules and a required structured `format` object.
- `skill`: the detailed rule set. This can be a list or an object, depending on the skill.

Recommended format:

~~~json
{
  "description": "Review component naming quality in a Form.io JSON file.",
  "goal": "Determine PASSED or FAILED for each component naming check.",
  "output_style": {
    "type": "structured_review",
    "rules": [
      "Review each check independently.",
      "Return PASSED or FAILED for every check.",
      "If failed, point to the exact component or location."
    ],
    "format": {
      "A1": {
        "Status": "PASSED or FAILED",
        "Note / Feedback": "If failed, specify the exact component position and invalid value."
      },
      "A2": {
        "Status": "PASSED or FAILED",
        "Note / Feedback": "If failed, specify the exact label and key that violate the rule."
      }
    }
  },
  "procedure": [
    "Open the input JSON file.",
    "Traverse all relevant top-level and nested components.",
    "Apply each check independently.",
    "Return evidence using the exact keys declared in output_style.format."
  ],
  "skill": [
    {
      "id": "A1",
      "description": "Check whether every component key follows camelCase naming.",
      "goal": "Make sure component keys are written in camelCase.",
      "output_style": "Return PASSED or FAILED. If failed, identify the component and invalid key.",
      "procedure": [
        "Traverse all components recursively.",
        "Read the key field when present.",
        "Fail if any checked key contains spaces, hyphens, underscores, or invalid casing."
      ],
      "skill": []
    },
    {
      "id": "A2",
      "description": "Check whether each key is meaningful and aligned with its label.",
      "goal": "Make sure keys clearly represent business meaning.",
      "output_style": "Return PASSED or FAILED. If failed, identify the label and key.",
      "procedure": [
        "Compare each label with its key.",
        "Fail vague, random, temporary, or auto-generated duplicate-style keys."
      ],
      "skill": []
    }
  ]
}
~~~

Important rules:

- `output_style.format` drives the structured response schema passed to the agent.
- Every check key in `output_style.format` should match a rule ID in `skill`.
- Each field under a check format becomes a required string field in the agent output.
- Use `Status` with values `PASSED` or `FAILED` so the workflow can calculate check status.

## Skillset description file

Each skillset folder has a derived metadata file:

`skills/<skillset_name>/description.json`

Example:

~~~json
{
  "skillset": "form_quality",
  "description": "Skillset form_quality",
  "skills": [
    {
      "skill_name": "component_quality",
      "description": "Review component naming quality in a Form.io JSON file.",
      "skill_file": "skills/form_quality/component_quality.json"
    },
    {
      "skill_name": "field_logic_quality",
      "description": "Review field logic safety and correctness in a Form.io JSON file.",
      "skill_file": "skills/form_quality/field_logic_quality.json"
    }
  ]
}
~~~

You normally do not need to edit `description.json` by hand. `tools/skill_loader.py` rebuilds it from the skill JSON files whenever `python main.py` starts or the skill tools refresh the registry. If you create it manually before the first run, keep the same shape shown above.

`skills/skill_registry.json` is also generated automatically and stores a flat list:

~~~json
{
  "skills": [
    {
      "name": "component_quality",
      "description": "Review component naming quality in a Form.io JSON file.",
      "skill_file": "skills/form_quality/component_quality.json"
    }
  ]
}
~~~

## Policy control

- PAP folder: `policy/PAP` manages storage access, registry loading, and skill/tool inventory refresh.
- PDP folder: `policy/PDP` evaluates policy decisions for skillset selection, skill use, and tool invocation.
- PEP folder: `policy/PEP` enforces PDP decisions at runtime and records denied decisions in `policy/storage/policy_denials.jsonl`.
- `policy/storage/base.json` defines the schema and registered resources. Skillsets, skills, and tools are refreshed automatically from the registry on startup.
- `policy/storage/runtime_policy.json` is the canonical file to edit when deciding which routes, profiles, and skills are allowed to run.
- `policy/storage/policy.json` is a legacy migration source. Do not use it for active runtime changes when `base.json` and `runtime_policy.json` exist.

## Runtime policy update format

Batch execution uses `policy/storage/runtime_policy.json`.

For each route, set:

- `profile`: the profile that controls permissions.
- `skillset`: the folder under `skills/`.
- `skills`: ordered list of skill names to execute.

Example route config:

~~~json
{
  "routes": {
    "route_a": {
      "label": "FormIO",
      "profile": "route_a_formio",
      "skillset": "form_quality",
      "skills": [
        "component_quality",
        "field_logic_quality",
        {
          "skill_name": "new_quality_check",
          "criterion": "custom_output_criterion_name"
        }
      ]
    }
  }
}
~~~

The `skills` list can contain either:

- A string, where `criterion` defaults to the same value as the skill name.
- An object with `skill_name` and optional `criterion`.

For each profile, set:

- `allowed_skillsets`: skillsets this profile can select, or `["*"]`.
- `allowed_skills`: skills this profile can execute, or `["*"]`.
- `excluded_skills`: skills to skip even if allowed.
- `allowed_tools`: tools this profile can use, or `["*"]`.

Example profile config:

~~~json
{
  "profiles": {
    "route_a_formio": {
      "layer": "application",
      "allowed_skillsets": [
        "form_quality"
      ],
      "allowed_skills": [
        "component_quality",
        "field_logic_quality",
        "new_quality_check"
      ],
      "excluded_skills": [],
      "allowed_tools": [
        "read_project_file",
        "list_project_files",
        "list_skills",
        "load_skill",
        "get_hyperparameters"
      ]
    }
  }
}
~~~

## Proceed folder behavior

- During a run, each file being processed is copied into input/proceed/.
- When the run finishes or is interrupted, input/proceed/ is cleared automatically.

## Hyperparameter behavior

- config/hyperparams.json is the standard runtime configuration.
- If it is missing, config/settings.py recreates it automatically with default values.

## Adding a new skill

1. Choose or create a skillset folder, for example `skills/form_quality/` or `skills/back_office_quality/`.
2. Add a new skill JSON file named after the skill, for example `skills/form_quality/new_quality_check.json`.
3. Use the required skill format above. Make sure `output_style.format` contains all check IDs and required output fields.
4. Run `python main.py` once, or call the skill list/load tools, to regenerate `skills/<skillset>/description.json`, `skills/skill_registry.json`, and the registered resources in `policy/storage/base.json`.
5. Edit `policy/storage/runtime_policy.json`.
6. Add the skill name to the target route's ordered `skills` list.
7. Add the skill name to that route profile's `allowed_skills`, unless the profile already uses `["*"]`.
8. Make sure the skill is not listed in `excluded_skills`.
9. Put an input file in `input/` whose name matches the route pattern, such as `input_formio_sample.json` for `route_a`.
10. Run `python main.py` and inspect the result in `output/`.

Minimal example for adding `new_quality_check` to `route_a`:

~~~json
{
  "routes": {
    "route_a": {
      "label": "FormIO",
      "profile": "route_a_formio",
      "skillset": "form_quality",
      "skills": [
        "component_quality",
        "field_logic_quality",
        "new_quality_check"
      ]
    }
  },
  "profiles": {
    "route_a_formio": {
      "layer": "application",
      "allowed_skillsets": [
        "form_quality"
      ],
      "allowed_skills": [
        "component_quality",
        "field_logic_quality",
        "new_quality_check"
      ],
      "excluded_skills": [],
      "allowed_tools": [
        "read_project_file",
        "list_project_files",
        "list_skills",
        "load_skill",
        "get_hyperparameters"
      ]
    }
  }
}
~~~
