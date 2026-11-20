# Etapa 8D — auditoria dos verificadores

Cada linha de `acceptance.jsonl` inclui agora a configuração do verificador e
o resultado ou tipo de falha da tentativa. O registo fica fora do workspace.

## Ordem de estudo

1. Em `app/tools/acceptance.py`, lê `audit_metadata`: para PythonAcceptance,
   devolve caminho absoluto do script, hash esperado, timeout, executável e
   versão do Python e versão do adaptador.
2. Em `app/builder/harness.py`, segue o bloco ACCEPTANCE. Captura a configuração
   antes de chamar o verificador. `completed` significa que este devolveu uma
   resposta válida; `passed` diz se não houve erros nem contratos alterados.
3. Exceções produzem `execution_error` e `error_type`. O registo não guarda a
   mensagem da exceção, que pode conter dados sensíveis. A exceção continua a
   propagar-se, como antes; não desencadeia reparação automática.
4. O `finally` escreve o registo mesmo quando o verificador falha. Uma falha de
   escrita no filesystem continua a poder impedir a gravação; não há garantia
   transacional. Interrupções abruptas do processo também podem deixar lacunas.
5. Funções Python genéricas continuam suportadas, mas são identificadas apenas
   como `callable`, com `version_verified=false`. Não inventamos um hash para
   closures, estado externo ou dependências desconhecidas.
6. Lê `tests/test_acceptance_audit.py`: verifica metadados, falha sem exposição da
   mensagem e registo do hash esperado quando o script foi alterado.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_acceptance_audit.py -q
```

## Como interpretar

`script_sha256` é o hash esperado desde a criação do adaptador. Quando a execução
falha porque o script mudou, não significa que esse conteúdo foi executado.
O hash é verificado pelo adaptador antes de iniciar o processo; ainda existe
uma janela entre essa verificação e a leitura pelo interpretador.

O caminho e versão de Python são metadados locais, não segredos de autenticação,
mas podem revelar a estrutura das pastas. Os diagnósticos de reprovação continuam
a ser registados e podem seguir para o modelo durante reparações.

Esta etapa não guarda o código do verificador, não fixa dependências, não assina
logs nem permite reproduzir todo o ambiente. A separação de processo da etapa 8C
continua sem ser uma sandbox de segurança.
