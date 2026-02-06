# HomeWizard P1 Exporter

Een Docker-gebaseerde applicatie die data exporteert van een HomeWizard P1 meter (HWE-P1-G1), deze opslaat in een PostgreSQL database en rapporten genereert voor elektriciteits- en gasverbruik.

## Functionaliteiten

- ✅ Data exporteren van HomeWizard P1 meter via lokale API
- ✅ Opslaan van metingen in PostgreSQL database op je NAS
- ✅ Automatische data-verzameling (standaard elke 30 seconden)
- ✅ Automatische dagelijkse rapporten (elke dag om middernacht)
- ✅ Genereren van jaar- en maandoverzichten op verzoek
- ✅ Export van rapporten naar JSON en CSV
- ✅ Docker & Docker Compose support voor eenvoudige installatie
- ✅ Persistente data opslag met volumes

## Vereisten

- Docker en Docker Compose geïnstalleerd op je NAS
- HomeWizard P1 meter (HWE-P1-G1) aangesloten op je netwerk
- IP-adres van je HomeWizard P1 meter

## Snelstart

### 1. Clone de repository

```bash
git clone https://github.com/Mikebeem/HomeWizardExporter.git
cd HomeWizardExporter
```

### 2. Configuratie

**Belangrijk**: Je **moet** een `.env` bestand aanmaken met je eigen instellingen voordat je de applicatie kunt starten.

Kopieer het voorbeeld configuratie bestand:

```bash
cp .env.example .env
```

Pas de `.env` aan met je eigen instellingen:

```env
# VERPLICHT: Wijzig dit naar het IP-adres van je HomeWizard P1 meter
HOMEWIZARD_HOST=192.168.1.100

# VERPLICHT: Stel een sterk wachtwoord in voor de database
POSTGRES_PASSWORD=jouw_veilig_wachtwoord_hier

# Optioneel: Database naam en gebruiker (standaard waarden zijn prima)
POSTGRES_DB=homewizard
POSTGRES_USER=postgres

# Optioneel: Poll interval in seconden (standaard: 30)
POLL_INTERVAL=30
```

**Let op**: De applicatie zal niet starten zonder een correct geconfigureerd `.env` bestand!

### 3. Start de applicatie

```bash
docker-compose up -d
```

Dit start twee containers:
- `homewizard_db`: PostgreSQL database
- `homewizard_exporter`: De export applicatie

De applicatie zal automatisch:
- Elke 30 seconden (configureerbaar) data ophalen van je meter
- Elke dag om middernacht een rapport genereren (te zien in de logs)

### 4. Controleer de logs

```bash
docker-compose logs -f exporter
```

Je zou berichten moeten zien zoals:

```
homewizard_exporter | 2024-01-15 10:30:00 - INFO - Starting HomeWizard Exporter
homewizard_exporter | 2024-01-15 10:30:00 - INFO - Database connection established
homewizard_exporter | 2024-01-15 10:30:01 - INFO - Polling HomeWizard meter...
homewizard_exporter | 2024-01-15 10:30:01 - INFO - Received data: Power=1250W, Gas=1234.5m³
```

## Rapporten Genereren

### Console Output

Bekijk het jaarverbruik in de console:

```bash
docker-compose exec exporter python generate_report.py --year 2024
```

Output:
```
=== Yearly Report 2024 ===
Electricity Consumed: 3450.75 kWh
Electricity Produced: 1234.50 kWh
Gas Consumed: 1567.25 m³
Measurements: 1051200
========================
```

### Maandoverzicht

```bash
docker-compose exec exporter python generate_report.py --year 2024 --monthly
```

### Export naar JSON

```bash
docker-compose exec exporter python generate_report.py --year 2024 --format json --output /app/report_2024.json
```

### Export naar CSV

```bash
docker-compose exec exporter python generate_report.py --year 2024 --monthly --format csv --output /app/report_2024_monthly.csv
```

## Database Toegang

De database is alleen toegankelijk binnen het Docker netwerk voor extra beveiliging. Er is geen externe poort geopend.

### Via psql
```bash
docker-compose exec db psql -U postgres -d homewizard
```

Handige queries:

```sql
-- Bekijk laatste 10 metingen
SELECT timestamp, power_consumed, gas_total_m3 
FROM measurements 
ORDER BY timestamp DESC 
LIMIT 10;

-- Dagelijks verbruik
SELECT 
    DATE(timestamp) as date,
    MAX(total_imported) - MIN(total_imported) as daily_kwh,
    MAX(gas_total_m3) - MIN(gas_total_m3) as daily_gas_m3
FROM measurements
GROUP BY DATE(timestamp)
ORDER BY date DESC
LIMIT 7;
```

## Architectuur

```
┌─────────────────┐         ┌──────────────────┐
│  HomeWizard P1  │◄────────│  Exporter App    │
│  Meter          │  HTTP   │  (Python)        │
│  (HWE-P1-G1)    │  API    │                  │
└─────────────────┘         └──────────────────┘
                                      │
                                      │ SQL
                                      ▼
                            ┌──────────────────┐
                            │  PostgreSQL DB   │
                            │  (Persistent)    │
                            └──────────────────┘
```

## Datamodel

De applicatie slaat de volgende gegevens op in de `measurements` tabel:

```sql
CREATE TABLE measurements (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL UNIQUE,
    power_consumed REAL,
    power_produced REAL,
    total_imported REAL,  -- Cumulatief kWh
    total_exported REAL,  -- Cumulatief kWh
    gas_timestamp TIMESTAMP,
    gas_total_m3 REAL,    -- Cumulatief m³
    voltage_l1/l2/l3 REAL,
    current_l1/l2/l3 REAL
);
```

- **Timestamp**: Tijdstip van de meting (unieke index)
- **Elektriciteit**:
  - Huidig verbruik/productie (W)
  - Totaal geïmporteerd/geëxporteerd (kWh, cumulatief)
  - Spanning per fase (V)
  - Stroom per fase (A)
- **Gas**:
  - Totaal verbruik (m³, cumulatief)
  - Timestamp van gasmeting

**Belangrijk**: Verbruiksrapporten worden berekend door positieve delta's tussen opeenvolgende metingen op te tellen. Dit handelt counter resets en data gaps correct af.

## Onderhoud

### Backup maken

```bash
docker-compose exec db pg_dump -U postgres homewizard > backup_$(date +%Y%m%d).sql
```

### Restore van backup

```bash
cat backup_20240115.sql | docker-compose exec -T db psql -U postgres homewizard
```

### Logs bekijken

```bash
docker-compose logs -f
```

### Stoppen

```bash
docker-compose down
```

### Stoppen en data verwijderen

⚠️ **Let op**: Dit verwijdert alle opgeslagen data!

```bash
docker-compose down -v
```

## Troubleshooting

### Kan geen verbinding maken met HomeWizard meter

1. Controleer of het IP-adres correct is in `.env` of `docker-compose.yml`
2. Test de API handmatig:
   ```bash
   curl http://192.168.1.100/api/v1/data
   ```
3. Zorg dat de meter en je NAS op hetzelfde netwerk zitten

### Database connectie problemen

1. Controleer of de database container draait:
   ```bash
   docker-compose ps
   ```
2. Bekijk database logs:
   ```bash
   docker-compose logs db
   ```

### Geen data in rapporten

Dit is normaal als je de applicatie net hebt gestart. Wacht tot er data is verzameld. Je kunt de database controleren:

```bash
docker-compose exec db psql -U postgres homewizard -c "SELECT COUNT(*) FROM measurements;"
```

## Ontwikkeling

### Lokaal draaien zonder Docker

```bash
# Installeer dependencies
pip install -r requirements.txt

# Configureer environment variables
export HOMEWIZARD_HOST=192.168.1.100
export DB_HOST=localhost
export DB_PASSWORD=postgres

# Start de applicatie
python app.py
```

## Licentie

MIT

## Bijdragen

Bijdragen zijn welkom! Open een issue of pull request.

## Auteur

Mike Beem