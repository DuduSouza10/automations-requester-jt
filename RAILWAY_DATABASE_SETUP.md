# Banco persistente no Railway

## 1. Adicione PostgreSQL
No projeto Railway, clique em **+ New > Database > PostgreSQL**.

## 2. Ligue o PostgreSQL ao servico do site
Abra o servico web do site > **Variables** > **New Variable** e crie:

```text
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

Se o servico do banco tiver outro nome, troque `Postgres` pelo nome dele.

## 3. Arquivos persistentes
As solicitacoes, status, progresso, notificacoes e historico ficam no PostgreSQL.
Para documentos anexados e arquivos finais, adicione um **Volume** ao servico web com mount path:

```text
/data
```

E mantenha:

```text
UPLOAD_DIR=/data/uploads
```

## 4. Outras variaveis

```text
ADMIN_PASSWORD=142723
SECRET_KEY=uma-chave-grande-e-aleatoria
MAX_UPLOAD_MB=100
```

## 5. Como confirmar
Depois do deploy, abra `/health` no dominio do site. O retorno correto em producao deve conter:

```json
{
  "status": "ok",
  "database": "postgresql",
  "persistent_database": true
}
```

Se o PostgreSQL nao estiver conectado, esta versao do app se recusa a iniciar no Railway. Isso e proposital para impedir que novos dados sejam gravados em SQLite temporario e desaparecam no proximo deploy.
