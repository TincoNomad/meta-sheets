# Meta Ads → Google Sheets Sync

Script diario que extrae insights de Meta Ads y los escribe en un Google Sheet.

## Secrets requeridos en GitHub

| Secret | Descripción |
|---|---|
| `META_ACCESS_TOKEN` | Token de acceso de Meta (system user, larga duración) con permiso `ads_read` |
| `META_AD_ACCOUNT_ID` | ID de la ad account, formato `act_XXXXXXXXX` |
| `GOOGLE_SHEET_ID` | ID del Google Sheet (parte de la URL: `docs.google.com/spreadsheets/d/<ID>/edit`) |
| `GOOGLE_CREDENTIALS_JSON` | JSON completo del Service Account de Google |

## Cómo conseguir cada secret

### Meta Access Token

1. Crear un System User en **Business Settings → Users → System Users**
2. Asignarle rol **Admin**
3. Generar access token con permiso **ads_read**
4. El token no expira — guárdalo inmediatamente.

### Meta Ad Account ID

1. En **Business Settings → Accounts → Ad Accounts**
2. El ID aparece al lado del nombre (formato `act_XXXXXXXXX`).

### Google Service Account

1. Ir a [Google Cloud Console](https://console.cloud.google.com/) → **IAM & Admin → Service Accounts**
2. Crear service account (nombre: `meta-ads-sync`)
3. Ir a **Keys** → **Add Key → JSON** → se descarga un archivo
4. Copiar el contenido JSON completo → ese es `GOOGLE_CREDENTIALS_JSON`
5. Abrir el Google Sheet → **Compartir** → invitar al email del service account (ej: `meta-ads-sync@<project>.iam.gserviceaccount.com`) como **Editor**

## Cómo probar localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# editar .env con tus valores reales
python main.py
```

## Columnas del Sheet

`Date | Campaign | Ad Set | Spend | Impressions | Clicks | CTR | Reach | Conversions`

Cada ejecución agrega una fila por cada ad set activo del día anterior.

## Workflow

El cron corre a las 12:00 UTC (7:00 AM Perú). También se puede ejecutar manualmente desde la pestaña **Actions** del repositorio (botón **Run workflow**).
