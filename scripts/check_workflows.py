"""
check_workflows.py - valida os workflows do GitHub Actions antes que quebrem o bot (D-043, 2026-10-21).

P-05: um YAML invalido no main.yml ja parou o bot. Este script:
  1. le cada .github/workflows/*.yml como YAML (falha se nao for YAML valido);
  2. extrai cada bloco `run:` dos passos, troca as expressoes `${{ ... }}` por um valor fixo
     e roda `bash -n` (so checa a sintaxe do shell; nao executa nada).

COMO RODAR (precisa de PyYAML; o workflow `checks` instala):
    python scripts/check_workflows.py      # sai com codigo 0 se tudo ok
"""
import glob
import os
import re
import subprocess
import sys
import tempfile

import yaml

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_EXPR = re.compile(r"\$\{\{.*?\}\}", re.S)


def blocos_run(doc):
    """(job, passo, script) de cada passo com `run:`."""
    for job_id, job in ((doc or {}).get("jobs") or {}).items():
        for i, passo in enumerate((job or {}).get("steps") or []):
            if isinstance(passo, dict) and isinstance(passo.get("run"), str):
                yield job_id, passo.get("name") or "passo %d" % (i + 1), passo["run"]


def bash_ok(script):
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
        fh.write(_EXPR.sub("X", script))
        caminho = fh.name
    try:
        r = subprocess.run(["bash", "-n", caminho], capture_output=True, text=True)
        return r.returncode == 0, r.stderr.strip()
    finally:
        os.remove(caminho)


def main():
    falhas = 0
    arquivos = sorted(glob.glob(os.path.join(_ROOT, ".github", "workflows", "*.yml")))
    for arq in arquivos:
        nome = os.path.basename(arq)
        try:
            with open(arq, encoding="utf-8") as fh:
                doc = yaml.safe_load(fh)
        except yaml.YAMLError as e:
            falhas += 1
            print("FAIL  %s: YAML invalido -> %s" % (nome, str(e).splitlines()[0]))
            continue
        n, ruins = 0, 0
        for job, passo, script in blocos_run(doc):
            ok, err = bash_ok(script)
            n += 1
            if not ok:
                ruins += 1
                print("FAIL  %s / %s / %s: bash -n -> %s" % (nome, job, passo, err))
        falhas += ruins
        if not ruins:
            print("PASS  %s (YAML ok, %d blocos run com sintaxe ok)" % (nome, n))
    if not arquivos:
        print("FAIL  nenhum workflow encontrado")
        falhas += 1
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
