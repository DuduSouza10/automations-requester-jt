# J&T — Central de Controle de Automações

Aplicação web pronta para Railway, criada para controlar o ciclo completo de solicitações de automações.

## O que está incluído

- Página pública com 3 áreas:
  - **Solicitações**: nome, solicitante/setor, objetivo/informações e tipo (Robô, Dashboard, Automação).
  - **Em andamento**: etapa atual, progresso e atualizações do desenvolvimento.
  - **Automações criadas**: arquivo final, procedimento de uso, data de conclusão e versão.
- Solicitações entram automaticamente como **Pendentes**.
- Painel administrativo protegido por senha.
- Aprovação e recusa de solicitações.
- Atualização manual de estágio, percentual e observações.
- Conclusão com upload do arquivo final e passo a passo.
- Solicitação de alteração por janela modal.
- Pedidos de alteração retornam para a fila de solicitações e geram uma notificação no admin.
- Alterações concluídas atualizam a automação original e incrementam a versão (v2, v3...).
- Central de notificações com contador de não lidas.
- Edição de entregas e substituição de arquivos.
- Banco PostgreSQL no Railway, com SQLite como fallback local.
- Suporte a Railway Volume para persistência dos arquivos anexados.
- Healthcheck em `/health`.

## Acesso administrativo

A senha padrão solicitada é `142723`.

No Railway, configure a variável `ADMIN_PASSWORD=142723`. Também configure uma `SECRET_KEY` forte. A senha não precisa ficar exposta no código depois que a variável de ambiente for criada.

## Deploy no Railway

1. Crie um repositório GitHub com os arquivos deste projeto.
2. No Railway, crie um **New Project > Deploy from GitHub Repo** e selecione o repositório.
3. Dentro do projeto Railway, adicione um serviço **PostgreSQL**.
4. No serviço web, abra **Variables** e confirme que `DATABASE_URL` está disponível a partir do PostgreSQL.
5. Adicione estas variáveis no serviço web:

```env
ADMIN_PASSWORD=142723
SECRET_KEY=coloque-uma-chave-grande-e-aleatoria-aqui
UPLOAD_DIR=/data/uploads
MAX_UPLOAD_MB=100
```

6. Crie um **Volume** no serviço web e monte em:

```text
/data
```

7. Faça o deploy. O `railway.toml` já configura o Gunicorn e o healthcheck.
8. Em **Settings > Networking**, gere o domínio público do serviço.

## Por que usar PostgreSQL + Volume

O PostgreSQL guarda as solicitações, progresso, manuais, versões e notificações. O Volume guarda os arquivos enviados (ZIP, EXE, XLSX etc.). Assim, um redeploy da aplicação não apaga seus dados nem os anexos.

## Teste local

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
set ADMIN_PASSWORD=142723
python app.py
```

Abra `http://localhost:5000`.

O painel administrativo fica em `http://localhost:5000/admin`.

## Estrutura

```text
app.py
requirements.txt
Procfile
railway.toml
.env.example
static/
  app.js
  style.css
templates/
  base.html
  index.html
  admin.html
  admin_login.html
uploads/
```

## Observações de segurança

- Antes de colocar o site em produção para muitas pessoas, altere a `SECRET_KEY`.
- Caso queira trocar a senha administrativa, altere somente `ADMIN_PASSWORD` nas variáveis do Railway.
- O upload aceita até 100 MB por padrão. Altere `MAX_UPLOAD_MB` caso necessário.
- O site foi pensado como uma central interna. Se ele ficar exposto publicamente na internet, vale adicionar autenticação também para os usuários comuns em uma etapa futura.
