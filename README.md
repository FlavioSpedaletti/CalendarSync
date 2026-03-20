# CalendarSync — Instruções de Setup e Execução

## Pré-requisitos

- **Python 3.11+** instalado
- **Azure Functions Core Tools v4** — [Instalar](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local#install-the-azure-functions-core-tools)
- **Azurite** (emulador de Azure Storage para rodar local) — [Instalar](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azurite)
  ```bash
  npm install -g azurite
  ```
- **Conta Google Cloud** com projeto criado e Calendar API habilitada
- **Service Account** do Google Cloud com chave JSON gerada

---

## 1. Setup do Google Cloud

1. Acesse [console.cloud.google.com](https://console.cloud.google.com)
2. Crie um novo projeto (ex: `CalendarSync`)
3. No menu lateral: **APIs & Services → Library** → busque **Google Calendar API** → **Enable**
4. Vá em **APIs & Services → Credentials** → **+ Create Credentials → Service account**
   - Nome: `calendar-sync`
   - Pule as etapas de permissões
5. Clique na Service Account criada → aba **Keys** → **Add Key → Create new key → JSON**
6. **Guarde o arquivo JSON** baixado — ele contém as credenciais

### Compartilhar calendário com a Service Account

1. Abra [calendar.google.com](https://calendar.google.com) (conta pessoal Gmail)
2. No calendário desejado → **⋮** → **Settings and sharing**
3. Em **Share with specific people** → **+ Add people and groups**
4. Cole o e-mail da Service Account (ex: `calendar-sync@calendarsync-xxxxx.iam.gserviceaccount.com`)
5. Permissão: **Make changes to events**
6. Copie o **Calendar ID** na seção **Integrate calendar** (geralmente é seu e-mail Gmail)

---

## 2. Configuração Local

Edite o arquivo `local.settings.json`:

```json
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "ICS_URL": "<URL_DO_SEU_CALENDARIO_ICS>",
    "GOOGLE_CALENDAR_ID": "<SEU_EMAIL_GMAIL_OU_CALENDAR_ID>",
    "GOOGLE_CREDENTIALS_JSON": "<CONTEUDO_DO_JSON_DA_SERVICE_ACCOUNT>"
  }
}
```

> **Nota sobre `GOOGLE_CREDENTIALS_JSON`**: cole o conteúdo inteiro do arquivo JSON da Service Account em uma única linha. Exemplo:
> ```
> {"type":"service_account","project_id":"calendarsync","private_key_id":"abc...","private_key":"-----BEGIN PRIVATE KEY-----\n...","client_email":"calendar-sync@calendarsync.iam.gserviceaccount.com",...}
> ```

---

## 3. Executar Localmente

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Iniciar o Azurite (emulador de storage) em outro terminal
azurite --silent

# 3. Iniciar a Function
func start
```

A função será disparada automaticamente a cada 3 minutos. Para testar imediatamente, você pode usar a URL de admin:

```bash
curl -X POST http://localhost:7071/admin/functions/calendar_sync
```

---

## 4. Deploy no Azure

### Criar a Function App (uma vez)

```bash
# Criar resource group
az group create --name CalendarSync-rg --location brazilsouth

# Criar storage account
az storage account create --name calendarsyncstore --location brazilsouth --resource-group CalendarSync-rg --sku Standard_LRS

# Criar function app (Consumption Plan)
az functionapp create \
  --resource-group CalendarSync-rg \
  --consumption-plan-location brazilsouth \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --name CalendarSyncApp \
  --os-type linux \
  --storage-account calendarsyncstore
```

### Configurar variáveis de ambiente

```bash
az functionapp config appsettings set \
  --name CalendarSyncApp \
  --resource-group CalendarSync-rg \
  --settings \
    "ICS_URL=<URL_DO_SEU_CALENDARIO_ICS>" \
    "GOOGLE_CALENDAR_ID=<SEU_CALENDAR_ID>" \
    "GOOGLE_CREDENTIALS_JSON=<CONTEUDO_JSON_ESCAPADO>"
```

### Fazer deploy

```bash
func azure functionapp publish CalendarSyncApp
```

Ou via **VS Code**: instale a extensão **Azure Functions**, clique com botão direito na Function App → **Deploy to Function App**.

---

## 5. Monitoramento

- **Logs em tempo real**:
  ```bash
  func azure functionapp logstream CalendarSyncApp
  ```
- **Application Insights**: incluso automaticamente na Function App. Acesse no portal Azure → Function App → Monitor

---

## Verificação

1. Crie um evento de teste no Outlook → aguarde até 5 min → verifique que aparece no Google Calendar com título `BS2 - {título}`
2. Altere o horário de um evento → verifique que atualiza no Google Calendar
3. Delete um evento no Outlook → verifique que é removido do Google Calendar
