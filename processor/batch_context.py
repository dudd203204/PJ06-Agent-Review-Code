from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agents.review_prompt import build_agent_review_prompt, build_review_prompt_trace_templates
from pydantic import SecretStr

from langchain_openai import ChatOpenAI

from processor.custom_llm import AiFarmLLM

from policy import (
    ensure_admin_policy_section,
    ensure_decision_policy_section,
    ensure_enforcement_policy_section,
    reload_policy_engine,
    refresh_pap_inventory,
)
from tools import list_all_tool_names
from tools.file_tools import ensure_directory
from tools.skill_loader import build_skill_registry
from utils.config_loader import HyperParams
from utils.env_loader import get_env, get_env_cast, resolve_project_path
from utils.logger import get_logger

logger = get_logger()


@dataclass(frozen=True)
class BatchContext:
    project_root: Path
    input_root: Path
    output_root: Path
    proceed_root: Path
    policy_root: Path
    skills_root: Path
    registry: dict
    execution_context: dict


def build_batch_context(*, project_root: Path, hyperparams_path: Path, hyperparams: HyperParams) -> BatchContext:
    # Determine which LLM provider to use
    llm_provider = get_env("LLM_PROVIDER", default=getattr(hyperparams.model, "provider", "openai")).lower()
    
    # Initialize appropriate LLM based on provider
    if llm_provider == "custom":
        # Use custom LLM provider (e.g., AI Farm - Azure-compatible API)
        logger.info("Initializing custom LLM provider")
        
        endpoint = get_env("CUSTOM_LLM_ENDPOINT", required=True)
        api_key = get_env("CUSTOM_LLM_API_KEY", required=True)
        deployment_id = get_env("CUSTOM_LLM_DEPLOYMENT_ID", default="gpt-5-nano-2025-08-07")
        api_version = get_env("CUSTOM_LLM_API_VERSION", default="2025-04-01-preview")
        subscription_id = get_env("CUSTOM_LLM_SUBSCRIPTION_ID", default="")
        temperature = get_env_cast("CUSTOM_LLM_TEMPERATURE", float, hyperparams.model.temperature)
        
        llm = AiFarmLLM(
            endpoint=endpoint,
            api_key=api_key,
            subscription_id=subscription_id,
            deployment_id=deployment_id,
            api_version=api_version,
            temperature=temperature,
            timeout=hyperparams.model.timeout,
        )
        logger.info("Custom LLM initialized with endpoint=%s deployment=%s api_version=%s", endpoint, deployment_id, api_version)
    else:
        # Default to OpenAI
        logger.info("Initializing OpenAI LLM provider")
        
        api_key = get_env("OPENAI_API_KEY", required=True)
        model_name = get_env("OPENAI_MODEL", default=hyperparams.model.name)
        temperature = get_env_cast("OPENAI_TEMPERATURE", float, hyperparams.model.temperature)
        
        llm = ChatOpenAI(
            api_key=SecretStr(api_key),
            model=model_name,
            temperature=temperature,
            timeout=hyperparams.model.timeout,
        )
        logger.info("OpenAI LLM initialized with model=%s", model_name)

    skill_root = resolve_project_path(
        project_root=project_root,
        raw_path=get_env("SKILL_PATH", default=None),
        fallback=hyperparams.paths.skill_root,
    )
    policy_root = resolve_project_path(
        project_root=project_root,
        raw_path=get_env("POLICY_PATH", default=None),
        fallback=hyperparams.paths.policy_root,
    )
    registry_path = (skill_root / "skill_registry.json").resolve()
    input_root = resolve_project_path(
        project_root=project_root,
        raw_path=get_env("INPUT_PATH", default=None),
        fallback=hyperparams.paths.input_root,
    )
    output_root = resolve_project_path(
        project_root=project_root,
        raw_path=get_env("OUTPUT_PATH", default=None),
        fallback=hyperparams.paths.output_root,
    )
    proceed_root = resolve_project_path(
        project_root=project_root,
        raw_path=None,
        fallback=hyperparams.paths.proceed_root,
    )

    ensure_directory(input_root)
    ensure_directory(output_root)
    ensure_directory(proceed_root)
    ensure_directory(policy_root)

    registry = build_skill_registry(project_root, skill_root, registry_path)
    ensure_admin_policy_section(policy_root)
    ensure_decision_policy_section(policy_root)
    ensure_enforcement_policy_section(policy_root)

    all_tool_names = list_all_tool_names(
        project_root=project_root,
        skill_root=skill_root,
        registry_path=registry_path,
        hyperparams_path=hyperparams_path,
    )
    refresh_pap_inventory(
        policy_path=policy_root,
        registry=registry,
        available_tools=all_tool_names,
    )

    reload_policy_engine(policy_root)

    return BatchContext(
        project_root=project_root,
        input_root=input_root,
        output_root=output_root,
        proceed_root=proceed_root,
        policy_root=policy_root,
        skills_root=skill_root,
        registry=registry,
        execution_context={
            "project_root": project_root,
            "registry_path": registry_path,
            "llm": llm,
            "prompt": build_agent_review_prompt(),
            "max_agent_iterations": hyperparams.runtime.max_agent_iterations,
            "agent_verbose": hyperparams.runtime.verbose,
            "prompt_trace_templates": build_review_prompt_trace_templates(),
            "agent_input_trace_output_root": output_root,
        },
    )
