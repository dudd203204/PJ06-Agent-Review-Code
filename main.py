from __future__ import annotations

import argparse
import sys
from pathlib import Path

from policy.errors import PolicyError
from processor.batch_context import build_batch_context
from processor.batch_orchestrator import process_input_file
from tools.file_tools import clear_directory, collect_input_files, write_output_file
from utils.config_loader import HyperParamLoadError, load_hyperparams
from utils.env_loader import get_env, load_environment, resolve_project_path
from utils.logger import get_logger

logger = get_logger()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LangChain agent-skill batch reviewer")
    parser.add_argument("--env-file", default=".env", help="Path to dotenv file")
    parser.add_argument(
        "--appkey",
        default=None,
        help="Specific appkey to process (from input/<appkey>/). If not specified, processes all appkeys."
    )
    return parser.parse_args()


def run() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parent
    proceed_root: Path | None = None

    try:
        load_environment(project_root / args.env_file)
        hyperparams_path = resolve_project_path(
            project_root=project_root,
            raw_path=get_env("HYPERPARAMS_PATH", default=None),
            fallback="config/hyperparams.json",
        )
        hyperparams = load_hyperparams(hyperparams_path)
        batch_context = build_batch_context(
            project_root=project_root,
            hyperparams_path=hyperparams_path,
            hyperparams=hyperparams,
        )
        proceed_root = batch_context.proceed_root
        input_files = collect_input_files(
            project_root, 
            batch_context.input_root, 
            batch_context.proceed_root,
            appkey_filter=args.appkey
        )
        
        if args.appkey:
            logger.info("Batch run initialized files=%s appkey=%s", len(input_files), args.appkey)
        else:
            logger.info("Batch run initialized files=%s", len(input_files))

        if not input_files:
            if args.appkey:
                logger.info("No input files found in %s for appkey=%s", batch_context.input_root, args.appkey)
            else:
                logger.info("No input files found in %s", batch_context.input_root)
            return 0

        for input_file in input_files:
            result_payload = process_input_file(
                input_file=input_file,
                project_root=project_root,
                proceed_root=batch_context.proceed_root,
                policy_root=batch_context.policy_root,
                registry=batch_context.registry,
                execution_context=batch_context.execution_context,
            )
            output_path = write_output_file(
                batch_context.output_root, 
                input_file, 
                result_payload,
                project_root=project_root,
                input_root=batch_context.input_root,
                skills_root=batch_context.skills_root,
                template_path=project_root / "output_template.xlsx"
            )
            logger.info(
                "Processed file=%s output=%s route=%s workflow=%s overall_status=%s",
                input_file.name,
                output_path.name,
                result_payload.get("route", "unknown"),
                result_payload.get("workflow", "unknown"),
                result_payload.get("overall_status", "unknown"),
            )

        return 0

    except (ValueError, FileNotFoundError, HyperParamLoadError, PolicyError) as exc:
        logger.error(str(exc))
        return 1
    except KeyboardInterrupt:
        logger.warning("Processing interrupted by user")
        return 130
    except Exception as exc:  # pragma: no cover - runtime safety path
        logger.exception("Unexpected runtime error: %s", exc)
        return 1
    finally:
        if proceed_root is not None:
            clear_directory(proceed_root)


if __name__ == "__main__":
    sys.exit(run())
