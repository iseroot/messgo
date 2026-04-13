from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class MutationCase:
    """Описание одного мутационного сценария."""

    name: str
    file_path: str
    original: str
    replacement: str
    test_command: str


MUTATION_CASES: list[MutationCase] = [
    MutationCase(
        name="rate_limit_gte_to_gt",
        file_path="app/core/rate_limit.py",
        original="if len(bucket) >= limit:",
        replacement="if len(bucket) > limit:",
        test_command="python -m pytest -q --no-cov tests/unit/test_rate_limit.py",
    ),
    MutationCase(
        name="rate_limit_window_sign",
        file_path="app/core/rate_limit.py",
        original="while bucket and now - bucket[0] > window_seconds:",
        replacement="while bucket and now - bucket[0] < window_seconds:",
        test_command="python -m pytest -q --no-cov tests/unit/test_rate_limit.py",
    ),
    MutationCase(
        name="security_scope_check_invert",
        file_path="app/core/security.py",
        original="if payload.get(\"scope\") != expected_scope:",
        replacement="if payload.get(\"scope\") == expected_scope:",
        test_command="python -m pytest -q --no-cov tests/unit/test_security.py",
    ),
    MutationCase(
        name="auth_username_min_length",
        file_path="app/application/services/auth_service.py",
        original="if len(prepared_username) < 3:",
        replacement="if len(prepared_username) < 2:",
        test_command="python -m pytest -q --no-cov tests/unit/test_auth_service.py",
    ),
    MutationCase(
        name="auth_invite_validation_or_to_and",
        file_path="app/application/services/auth_service.py",
        original="if invite is None or not invite.is_active:",
        replacement="if invite is None and not invite.is_active:",
        test_command="python -m pytest -q --no-cov tests/unit/test_auth_service.py",
    ),
    MutationCase(
        name="chat_direct_self_check",
        file_path="app/application/services/chat_service.py",
        original="if owner_id == peer_id:",
        replacement="if owner_id != peer_id:",
        test_command="python -m pytest -q --no-cov tests/unit/test_chat_service.py",
    ),
    MutationCase(
        name="message_empty_check",
        file_path="app/application/services/message_service.py",
        original="if not prepared_text:",
        replacement="if prepared_text:",
        test_command="python -m pytest -q --no-cov tests/unit/test_message_service.py",
    ),
    MutationCase(
        name="call_self_call_check",
        file_path="app/application/services/call_service.py",
        original="if initiator_id == to_user_id:",
        replacement="if initiator_id != to_user_id:",
        test_command="python -m pytest -q --no-cov tests/unit/test_call_service.py",
    ),
]


def run_command(command: str, project_root: Path, verbose: bool) -> int:
    """Запускает тестовую команду и возвращает код завершения."""

    output_target = None if verbose else subprocess.DEVNULL
    process = subprocess.run(
        command,
        cwd=project_root,
        shell=True,
        check=False,
        stdout=output_target,
        stderr=output_target,
    )
    return process.returncode


def execute_mutation(case: MutationCase, project_root: Path, verbose: bool) -> tuple[bool, str]:
    """Применяет мутацию, запускает тесты и откатывает изменения."""

    target = project_root / case.file_path
    original_content = target.read_text(encoding="utf-8")

    if case.original not in original_content:
        return False, "шаблон не найден"

    mutated_content = original_content.replace(case.original, case.replacement, 1)
    target.write_text(mutated_content, encoding="utf-8")

    try:
        return_code = run_command(case.test_command, project_root, verbose=verbose)
    finally:
        target.write_text(original_content, encoding="utf-8")
        target.touch()
        pycache_dir = target.parent / "__pycache__"
        if pycache_dir.exists():
            for file_path in pycache_dir.glob(f"{target.stem}*.pyc"):
                file_path.unlink(missing_ok=True)

    killed = return_code != 0
    return killed, "killed" if killed else "survived"


def parse_args() -> argparse.Namespace:
    """Разбирает аргументы CLI."""

    parser = argparse.ArgumentParser(description="Лёгкий раннер мутационных тестов")
    parser.add_argument(
        "--fail-on-survivor",
        action="store_true",
        help="Завершать выполнение с кодом 1, если есть выжившие мутации",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Показывать вывод тестовых команд для каждой мутации",
    )
    return parser.parse_args()


def main() -> int:
    """Точка входа мутационного прогона."""

    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]

    print("Запуск мутационных тестов...")
    killed = 0
    survived = 0
    skipped = 0

    for case in MUTATION_CASES:
        print(f"[MUTATION] {case.name} -> {case.file_path}")
        result, status = execute_mutation(case, project_root, verbose=args.verbose)
        if status == "шаблон не найден":
            skipped += 1
            print(f"  - SKIPPED: {status}")
            continue

        if result:
            killed += 1
            print("  - KILLED")
        else:
            survived += 1
            print("  - SURVIVED")

    print("\nИтог мутационного прогона")
    print(f"  killed:   {killed}")
    print(f"  survived: {survived}")
    print(f"  skipped:  {skipped}")

    if args.fail_on_survivor and survived > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
