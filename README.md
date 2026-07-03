# Meta Ads → Google Sheets Sync

Script diario que extrae insights de Meta Ads y los escribe en un Google Sheet.

## Secrets requeridos en GitHub

| Secret | Descripción |
|---|---|
| `META_ACCESS_TOKEN` | Token de acceso de Meta (system user, larga duración) con permiso `ads_read` |
| `META_AD_ACCOUNT_ID` | ID de la ad account (solo números, sin `act_`) |
| `GOOGLE_SHEET_ID` | ID del Google Sheet (`docs.google.com/spreadsheets/d/<ID>/edit`) |
| `GOOGLE_CREDENTIALS_JSON` | JSON del Service Account codificado en base64 |

Para generar el valor del secret:
```bash
# desde la raíz del proyecto
base64 -i meta-sheet-test-d9d0197a6fdf.json | pbcopy
# o con Python (más universal):
python3 -c "import base64; print(base64.b64encode(open('meta-sheet-test-d9d0197a6fdf.json','rb').read()).decode())" | pbcopy
```

## Cómo conseguir cada secret

### Meta Access Token

1. Crear un System User en **Business Settings → Users → System Users**
2. Asignarle rol **Admin**
3. Generar access token con permiso **ads_read**
4. El token no expira — guárdalo inmediatamente.

### Meta Ad Account ID

1. En **Business Settings → Accounts → Ad Accounts**
2. El ID aparece al lado del nombre (solo números).

### Google Service Account

1. Ir a [Google Cloud Console](https://console.cloud.google.com/) → **IAM & Admin → Service Accounts**
2. Crear service account (nombre: `meta-ads-sync`)
3. Ir a **Keys** → **Add Key → JSON** → se descarga un archivo
4. Renombrar el archivo a `google-creds.json` y ponerlo en la raíz del proyecto
5. Abrir el Google Sheet → **Share** → invitar al email del service account (ej: `meta-ads-sync@<project>.iam.gserviceaccount.com`) como **Editor**
6. Activar Google Sheets API en: https://console.developers.google.com/apis/api/sheets.googleapis.com

## Cómo probar localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# editar .env con tus valores reales
# copiar el JSON descargado como google-creds.json
python main.py
```

### Probar escritura al Sheet

```bash
python main.py --test-sheet
```

Escribe una fila de prueba con valores dummy y sale. Úsalo para verificar que la autenticación de Google y los permisos de escritura funcionan.

## Columnas del Sheet

`Date | Campaign | Ad Set | Spend | Impressions | Clicks | CTR | Reach | Conversions`

Cada ejecución agrega una fila por cada ad set activo del día anterior.

## Workflow

El cron corre a las 12:00 UTC (7:00 AM Perú). Para correrlo manualmente:

1. GitHub → pestaña **Actions**
2. Click en **Meta Ads → Google Sheets Sync**
3. Botón **Run workflow** → **Run workflow**

En GitHub Actions, `GOOGLE_CREDENTIALS_JSON` se escribe a `google-creds.json` automáticamente. No necesitas configuración extra.
