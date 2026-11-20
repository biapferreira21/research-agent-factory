# Etapa 8C — verificador de aceitação em processo separado

O adaptador `PythonAcceptance` implementa a interface `workspace -> list[str]`
já usada pelo harness. Executa um script Python de confiança fora do workspace,
com timeout, e valida a resposta JSON. Não executa o agente por si próprio.

## Ordem de estudo

1. Lê `app/tools/acceptance.py`. O construtor fixa o caminho absoluto do script,
   o timeout (30 segundos por omissão, máximo 120) e o hash do seu conteúdo.
2. `__call__` recusa um script dentro do workspace e um conteúdo alterado desde
   a configuração. Esta verificação não é uma assinatura nem elimina corridas
   entre verificação e execução; o hash só cobre o script, não dependências.
3. Segue `subprocess.run`: usa o Python atual com `-I`, sem shell e sem stdin,
   com cwd na pasta do script. O argumento seguinte é o caminho do workspace.
   `-I` reduz a influência do ambiente de imports Python; não é isolamento do SO.
4. O script deve terminar com exit code 0 e imprimir apenas um objeto JSON
   `{"errors": []}` para aprovação ou `{"errors": ["mensagem"]}` para reprovação.
   Não uses exit code 1 para representar um requisito incumprido: códigos não
   zero são tratados como falha de infraestrutura.
5. Timeout, crash, JSON inválido ou contrato incorreto levantam
   `AcceptanceExecutionError`. O harness não pede reparação nesses casos.
   Mensagens brutas de stderr não são copiadas para os erros apresentados.
6. Lê `examples/acceptance/check_readme.py`: exemplo externo de requisito de
   entrega que não importa nem executa o agente. Depois lê os testes.

```python
from pathlib import Path
from app.builder.harness import BuilderHarness
from app.tools.acceptance import PythonAcceptance

validator = PythonAcceptance(Path("examples/acceptance/check_readme.py"), timeout_seconds=10)
harness = BuilderHarness(acceptance_validator=validator, max_repair_attempts=2)
# harness.build("O teu pedido")  # modelos reais por omissão
```

```powershell
.venv\Scripts\python.exe -m pytest tests/test_acceptance_process.py tests/test_acceptance.py -q
```

## Limites importantes da implementação

O verificador tem as permissões do utilizador, acesso ao filesystem, rede e
variáveis de ambiente herdadas. Só executar scripts de confiança. Isto separa
o processo Python, mas não torna seguro executar código gerado não fiável.

O timeout termina o processo direto; não garante terminar descendentes criados
pelo script. O adaptador captura stdout/stderr em memória. O limite de 64000 bytes
da resposta é verificado depois da execução, não limita memória durante a captura.
Não há limites de CPU/memória, orçamento de chamadas externas ou sandbox.

A cobertura funcional depende do script escolhido. O exemplo de README valida
apenas presença de um ficheiro, não qualidade do agente. O hash não é ainda
persistido nos registos do build; falta versionamento completo dos verificadores.
