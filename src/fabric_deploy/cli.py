"""Linha de comando da esteira.

fabric-deploy validate
fabric-deploy render  --env prd --out build/prd
fabric-deploy plan    --env dev --base-ref origin/develop
fabric-deploy deploy  --env prd --base-ref <sha anterior>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fabric_deploy import summary
from fabric_deploy.config import DEFAULT_ENVIRONMENTS, DEFAULT_PARAMETERS, ConfigError, load_environments
from fabric_deploy.deploy import DeploymentBlocked, DeployRequest, build, run
from fabric_deploy.parameters import ParameterError, Parameters
from fabric_deploy.validate import validate


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fabric-deploy", description="CI/CD para Microsoft Fabric")
    parser.add_argument("--workspace-dir", type=Path, default=Path("workspace"), help="pasta dos itens")
    parser.add_argument("--environments-file", type=Path, default=DEFAULT_ENVIRONMENTS)
    parser.add_argument("--parameters-file", type=Path, default=DEFAULT_PARAMETERS)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="valida itens e configuração, sem acessar o Fabric")

    render = sub.add_parser("render", help="gera a cópia parametrizada de um ambiente para inspeção")
    render.add_argument("--env", required=True)
    render.add_argument("--out", type=Path, required=True)

    for name, help_ in [("plan", "mostra o que seria feito (dry-run)"), ("deploy", "implanta no workspace")]:
        cmd = sub.add_parser(name, help=help_)
        cmd.add_argument("--env", required=True)
        cmd.add_argument("--mode", choices=["selective", "full"], default="selective")
        cmd.add_argument("--base-ref", help="commit de referência do modo seletivo")
        cmd.add_argument("--item-types", help="restringe a tipos, ex.: Notebook,Report")
        cmd.add_argument("--allow-deletions", action="store_true", help="exclui itens removidos do Git")
        cmd.add_argument("--force-full", action="store_true", help="libera deploy completo em ambiente protegido")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        envs = load_environments(args.environments_file)
        params = Parameters.load(args.parameters_file)
    except (ConfigError, ParameterError) as exc:
        print(f"Configuração inválida: {exc}", file=sys.stderr)
        return 2

    if args.command == "validate":
        issues = validate(args.workspace_dir, params, list(envs))
        rows = [[i.level, i.where, i.message] for i in issues]
        summary.publish(
            summary.markdown(
                "Validação do workspace",
                ["Nível", "Onde", "Problema"],
                rows,
                [],
                empty="✅ Nenhum problema encontrado.",
            )
        )
        return 1 if any(i.level == "erro" for i in issues) else 0

    if args.env not in envs:
        print(f"Ambiente '{args.env}' não existe em {args.environments_file}", file=sys.stderr)
        return 2

    request = DeployRequest(
        environment=envs[args.env],
        repo_root=Path.cwd(),
        workspace_dir=args.workspace_dir,
        parameters=params,
        environments=list(envs),
    )

    if args.command == "render":
        _, counts = build(request, args.out.resolve())
        for label, n in counts.items():
            print(f"{n:>4} substituição(ões)  {label}")
        print(f"Cópia parametrizada para '{args.env}' em {args.out}")
        return 0

    request.mode = args.mode
    request.base_ref = args.base_ref
    request.item_types = args.item_types.split(",") if args.item_types else None
    request.allow_deletions = args.allow_deletions
    request.force_full = args.force_full
    request.plan_only = args.command == "plan"

    try:
        outcome = run(request)
    except (DeploymentBlocked, ConfigError, ParameterError) as exc:
        summary.publish(f"### Deploy recusado\n\n{exc}\n")
        return 1

    notes = request.notes + [f"Ambiente: **{args.env}** · modo: **{outcome.mode}**"]
    if request.plan_only:
        text = summary.markdown(
            "Plano de deploy", ["Ação", "Item", "Motivo", "Detalhe"], summary.plan_rows(outcome.result), notes
        )
        summary.publish(text)
        blocked = [a for a in getattr(outcome.result, "actions", []) if getattr(a, "action", None) == "BLOCKED"]
        return 1 if blocked else 0

    text = summary.markdown(
        "Resultado do deploy", ["Resultado", "Item", "Duração", "Erro"], summary.report_rows(outcome.result), notes
    )
    summary.publish(text)
    return 0 if getattr(outcome.result, "ok", False) else 1


def entrypoint() -> None:
    sys.exit(main())


if __name__ == "__main__":
    entrypoint()
