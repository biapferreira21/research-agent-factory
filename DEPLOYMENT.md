# Publicação no GitHub e num domínio

O código integral da interface e do servidor está nesta pasta. A aplicação pode
ser publicada como um único contentor; não precisa de um frontend separado nem de
CDNs.

## 1. Preparar a configuração

As chaves podem ser ligadas no painel **I/O** depois do primeiro arranque; ficam
no volume `data` e nunca entram na imagem. O `.env` continua disponível para
configuração de servidor. Para um domínio, define:

```dotenv
ALLOWED_HOSTS=research.example.com,localhost,127.0.0.1
```

O `.env`, a base de dados e os documentos de investigação estão excluídos do Git.
Nunca publiques esses ficheiros.

## 2. Testar o contentor

```powershell
docker compose build
docker compose up -d
Invoke-RestMethod http://127.0.0.1:8765/api/health
```

O volume `factory-data` preserva projetos, documentos, chats, wikis e agentes
quando o contentor é substituído. Faz backups regulares desse volume.

## 3. Guardar no GitHub

Executa estes comandos apenas quando tiveres criado o repositório vazio na tua
conta GitHub:

```powershell
git init
git add .
git commit -m "Initial research agent factory"
git branch -M main
git remote add origin https://github.com/UTILIZADOR/REPOSITORIO.git
git push -u origin main
```

Confirma com `git status` que `.env`, `data/` e `generated_agents/` não entram no
commit.

## 4. Ligar um domínio

Num VPS, mantém a porta do contentor ligada a `127.0.0.1`, como está em
`compose.yaml`, e coloca um proxy HTTPS à frente. Um exemplo mínimo para Caddy é:

```caddyfile
research.example.com {
    reverse_proxy 127.0.0.1:8765
}
```

Aponta o registo DNS do domínio para o servidor, inicia o proxy e testa
`https://research.example.com/api/health`. Se o proxy estiver noutro contentor,
liga ambos à mesma rede Docker e encaminha para
`research-agent-factory:8765`.

## 5. Proteção necessária antes de exposição pública

O harness tem proteção de sessão e origem, mas ainda não tem contas de utilizador.
Coloca autenticação no proxy (por exemplo, autenticação básica restrita ou um
serviço de acesso com identidade) antes de expor a aplicação na Internet. Isto é
necessário porque os projetos podem conter documentos privados e porque a factory
pode executar testes Python gerados. Para uma instalação pública multiutilizador,
é necessário acrescentar autenticação por utilizador, autorização por projeto e
isolamento de execução.

## Estrutura usada no deploy

- `Dockerfile`: imagem da aplicação e health check.
- `compose.yaml`: serviço local, reinício automático e volume persistente.
- `.dockerignore`: retira segredos, dados e ficheiros de desenvolvimento da imagem.
- `.env.example`: opções seguras que podem ser copiadas para `.env`.
- `docs/INTERFACE_FILES.md`: mapa do código da interface.
