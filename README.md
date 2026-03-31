# CalendarSync

Sincronização unidirecional de calendário **Outlook → Google Calendar**, hospedada como Azure Function (Timer Trigger).

A cada 3 minutos, a função baixa o calendário do Outlook no formato `.ics`, compara com o estado salvo no Blob Storage e aplica as diferenças (criação, atualização e exclusão de eventos) no Google Calendar.

---

## Arquitetura

```
Timer Trigger (3 min)
  └─ Fetch .ics (Outlook URL)
       └─ Parse eventos
            └─ Diff com estado salvo (Blob Storage)
                 ├─ Criar no Google Calendar
                 ├─ Atualizar no Google Calendar
                 ├─ Deletar no Google Calendar
                 └─ Salvar novo estado (Blob Storage)
```

**Estrutura de pastas:**

```
CalendarSync/
├── function_app.py          # Entry point — Timer Trigger
├── host.json                # Configuração do Azure Functions runtime
├── requirements.txt         # Dependências Python
├── local.settings.json      # Variáveis de ambiente locais (não vai para produção)
├── .funcignore              # Arquivos excluídos do deploy
└── sync/
    ├── ics_parser.py        # Download e parse do .ics
    ├── diff.py              # Lógica de diff (novo / atualizado / deletado)
    ├── google_calendar.py   # Wrapper da Google Calendar API
    └── state.py             # Estado persistido no Azure Blob Storage
```

---

## Pré-requisitos

- **Python 3.11+**
- **Azure Functions Core Tools v4** — [Instalar](https://learn.microsoft.com/azure/azure-functions/functions-run-local)
- **Azurite** (emulador de Azure Storage para desenvolvimento local):
  ```bash
  npm install -g azurite
  ```
- **Conta Google Cloud** com Calendar API habilitada e uma Service Account configurada

---

## 1. Configuração do Google Cloud

1. Acesse [console.cloud.google.com](https://console.cloud.google.com) e crie (ou selecione) um projeto
2. Em **APIs & Services → Library**, busque **Google Calendar API** e clique em **Enable**
3. Em **APIs & Services → Credentials → + Create Credentials → Service account**:
   - Nome: `calendar-sync` (ou qualquer nome)
   - Pule as etapas de permissões opcionais
4. Clique na Service Account recém-criada → aba **Keys** → **Add Key → Create new key → JSON**
5. **Salve o arquivo `.json` gerado** — ele contém as credenciais que serão usadas na variável `GOOGLE_CREDENTIALS_JSON`

### Compartilhar o calendário com a Service Account

1. Abra [calendar.google.com](https://calendar.google.com)
2. No calendário desejado → **⋮ → Settings and sharing**
3. Em **Share with specific people** → **+ Add people**
4. Cole o e-mail da Service Account (ex: `calendar-sync@seu-projeto.iam.gserviceaccount.com`)
5. Permissão: **Make changes to events** → **Send**
6. Na seção **Integrate calendar**, copie o **Calendar ID** (será usado em `GOOGLE_CALENDAR_ID`)

---

## 2. Variáveis de Ambiente

A aplicação depende das seguintes variáveis de ambiente:

| Variável | Descrição |
|---|---|
| `FUNCTIONS_WORKER_RUNTIME` | Deve ser `python` |
| `AzureWebJobsStorage` | Connection string do Azure Blob Storage (estado da sync) |
| `ICS_URL` | URL pública do calendário Outlook no formato `.ics` |
| `GOOGLE_CALENDAR_ID` | ID do calendário Google de destino |
| `GOOGLE_CREDENTIALS_JSON` | Conteúdo completo do JSON da Service Account (em uma linha) |
| `RUN_ON_STARTUP` | `true` para executar imediatamente ao iniciar (opcional, padrão `false`) |

> **Sobre `GOOGLE_CREDENTIALS_JSON`:** cole o conteúdo **completo** do arquivo `.json` da Service Account, compactado em uma única linha. Exemplo:
> ```
> {"type":"service_account","project_id":"meu-projeto","private_key_id":"abc123","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"calendar-sync@meu-projeto.iam.gserviceaccount.com",...}
> ```

> **Sobre `AzureWebJobsStorage`:** localmente use `UseDevelopmentStorage=true` (Azurite). Em produção, a connection string é gerada automaticamente pela Azure ao criar a Function App (ver seção Deploy).

---

## 3. Desenvolvimento Local

### 3.1 — Configurar `local.settings.json`

```json
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "RUN_ON_STARTUP": "true",
    "ICS_URL": "<URL_DO_SEU_CALENDARIO_ICS>",
    "GOOGLE_CALENDAR_ID": "<SEU_CALENDAR_ID>",
    "GOOGLE_CREDENTIALS_JSON": "<CONTEUDO_DO_JSON_DA_SERVICE_ACCOUNT>"
  }
}
```

> **Atenção:** `local.settings.json` está no `.gitignore` e no `.funcignore` — ele **nunca** é enviado para o repositório nem para o Azure. É exclusivo do ambiente local.

### 3.2 — Executar

```bash
# Instalar dependências
pip install -r requirements.txt

# Em um terminal separado: iniciar o emulador de Storage
azurite --silent

# Iniciar a Function
func start
```

A função dispara automaticamente a cada 3 minutos. Para forçar uma execução imediata:

```bash
curl -X POST http://localhost:7071/admin/functions/calendar_sync
```

### 3.3 — Executar testes

```bash
pytest tests/
```

---

## 4. Deploy no Azure

### 4.1 — Criar a infraestrutura (uma vez)

```bash
# Login no Azure
az login

# Criar resource group
az group create \
  --name CalendarSync-rg \
  --location brazilsouth

# Criar storage account (usada tanto pela Function App quanto pelo estado da sync)
az storage account create \
  --name calendarsyncstore \
  --location brazilsouth \
  --resource-group CalendarSync-rg \
  --sku Standard_LRS

# Criar a Function App
az functionapp create \
  --resource-group CalendarSync-rg \
  --consumption-plan-location brazilsouth \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --name CalendarSyncAppFlavio \
  --os-type linux \
  --storage-account calendarsyncstore
```

### 4.2 — Configurar variáveis de ambiente em produção

Ao criar a Function App, o Azure já define `AzureWebJobsStorage` automaticamente com a connection string da Storage Account criada. Você só precisa adicionar as variáveis específicas da aplicação.

**Via Azure CLI:**

```bash
az functionapp config appsettings set \
  --name CalendarSyncAppFlavio \
  --resource-group CalendarSync-rg \
  --settings \
    "ICS_URL=<URL_DO_SEU_CALENDARIO_ICS>" \
    "GOOGLE_CALENDAR_ID=<SEU_CALENDAR_ID>" \
    "GOOGLE_CREDENTIALS_JSON=<CONTEUDO_JSON_DA_SERVICE_ACCOUNT_EM_UMA_LINHA>"
```

**Via Portal do Azure:**

1. Acesse a **Function App** no [portal.azure.com](https://portal.azure.com)
2. No menu lateral: **Settings → Environment variables**
3. Clique em **+ Add** para cada variável abaixo:

   | Nome | Valor |
   |---|---|
   | `ICS_URL` | URL `.ics` do Outlook |
   | `GOOGLE_CALENDAR_ID` | ID do calendário Google |
   | `GOOGLE_CREDENTIALS_JSON` | JSON da Service Account (em uma linha) |

4. Clique em **Apply** e depois em **Confirm** para salvar

> **Sobre `AzureWebJobsStorage` em produção:** esta variável já é preenchida automaticamente pelo Azure com a connection string da Storage Account. O container `calendar-sync` e o blob `state.json` são criados automaticamente pela aplicação na primeira execução — nenhuma configuração manual é necessária.

### 4.3 — Fazer o deploy do código

**Via Azure Functions Core Tools:**

```bash
func azure functionapp publish CalendarSyncAppFlavio
```

**Via VS Code:**

Instale a extensão **Azure Functions**, clique com o botão direito na Function App no painel do Azure → **Deploy to Function App**.

---

## 5. Notificações (Push)

Os eventos são criados no Google Calendar por uma *Service Account, não por um usuário real. Por isso, o campo reminders definido via API fica associado à conta da Service Account — que não possui app nem dispositivo — e as notificações push **nunca são entregues* por esse mecanismo.

### Solução adotada — lembrete padrão no app

Configure o lembrete diretamente no Google Calendar app para o calendário compartilhado:

1. Abra [calendar.google.com](https://calendar.google.com) (ou o app mobile)
2. Localize o calendário compartilhado na lista lateral → clique nos *três pontos* → *Configurações*
3. Em *Notificações de eventos, clique em **Adicionar notificação*
4. Escolha *Notificação* (popup) e defina o tempo desejado (ex: "No momento do evento")
5. Salve

A partir daí, o app dispara a push para todos os eventos desse calendário, incluindo os sincronizados pelo CalendarSync.

> **Por que não Domain-wide delegation?** Seria possível configurar a Service Account para agir em nome de um usuário real (o que permitiria reminders funcionando via API), mas isso exige acesso ao *Google Workspace Admin Console* e é uma configuração administrativa mais complexa. A abordagem acima resolve o problema sem nenhuma dependência adicional.

---

## 6. Monitoramento

**Logs em tempo real (streaming):**
```bash
func azure functionapp logstream CalendarSyncAppFlavio
```

**Via Portal do Azure:**

- Function App → **Functions → calendar_sync → Monitor**: histórico de execuções com status e duração
- Function App → **Application Insights**: logs detalhados, falhas e métricas

---

## Verificação após deploy

1. Aguarde a primeira execução automática (~3 min) ou force via portal (Function → **Test/Run**)
2. Crie um evento de teste no Outlook → aguarde até 3 min → verifique que aparece no Google Calendar
3. Altere o horário do evento → verifique que é atualizado
4. Delete o evento → verifique que é removido
