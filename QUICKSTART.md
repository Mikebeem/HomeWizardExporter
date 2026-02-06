# HomeWizard P1 Exporter - Quick Reference

## Eerste Installatie

```bash
# 1. Clone repository
git clone https://github.com/Mikebeem/HomeWizardExporter.git
cd HomeWizardExporter

# 2. Configureer (VERPLICHT: wijzig IP-adres en wachtwoord!)
cp .env.example .env
nano .env  # of vi, vim, etc.
# Stel minimaal HOMEWIZARD_HOST en POSTGRES_PASSWORD in!

# 3. Start de applicatie
docker-compose up -d
```

## Dagelijks Gebruik

### Status Controleren
```bash
docker-compose ps
docker-compose logs -f exporter
```

### Jaarrapport Bekijken
```bash
docker-compose exec exporter python generate_report.py --year 2024
```

### Maandrapport Bekijken
```bash
docker-compose exec exporter python generate_report.py --year 2024 --monthly
```

### Export naar JSON
```bash
docker-compose exec exporter python generate_report.py --year 2024 --format json --output /app/report.json
```

### Export naar CSV
```bash
docker-compose exec exporter python generate_report.py --year 2024 --format csv --output /app/report.csv
```

## Database Toegang

### Via psql
```bash
docker-compose exec db psql -U postgres -d homewizard
```

### Handige Queries

Laatste 10 metingen:
```sql
SELECT timestamp, power_consumed, gas_total_m3 
FROM measurements 
ORDER BY timestamp DESC 
LIMIT 10;
```

Dagelijks verbruik (laatste week):
```sql
SELECT 
    DATE(timestamp) as date,
    MAX(total_imported) - MIN(total_imported) as daily_kwh,
    MAX(gas_total_m3) - MIN(gas_total_m3) as daily_gas_m3
FROM measurements
GROUP BY DATE(timestamp)
ORDER BY date DESC
LIMIT 7;
```

Gemiddeld vermogen per dag:
```sql
SELECT 
    DATE(timestamp) as date,
    ROUND(AVG(power_consumed)::numeric, 2) as avg_watt
FROM measurements
GROUP BY DATE(timestamp)
ORDER BY date DESC
LIMIT 7;
```

## Onderhoud

### Backup Maken
```bash
# Volledige backup
docker-compose exec db pg_dump -U postgres homewizard > backup_$(date +%Y%m%d).sql

# Alleen data (geen schema)
docker-compose exec db pg_dump -U postgres --data-only homewizard > backup_data_$(date +%Y%m%d).sql
```

### Restore
```bash
cat backup_20240115.sql | docker-compose exec -T db psql -U postgres homewizard
```

### Update Applicatie
```bash
git pull
docker-compose down
docker-compose build
docker-compose up -d
```

### Logs Opruimen
```bash
docker-compose logs --tail=1000 exporter > exporter.log
docker-compose restart exporter
```

## Troubleshooting

### Geen Verbinding met Meter
```bash
# Test API handmatig
curl http://192.168.1.100/api/v1/data

# Check logs
docker-compose logs exporter | grep -i error
```

### Database Problemen
```bash
# Check database status
docker-compose exec db pg_isready -U postgres

# Check database size
docker-compose exec db psql -U postgres -d homewizard -c "
SELECT pg_size_pretty(pg_database_size('homewizard'));"

# Check aantal metingen
docker-compose exec db psql -U postgres -d homewizard -c "
SELECT COUNT(*) FROM measurements;"
```

### Container Herstarten
```bash
docker-compose restart exporter
docker-compose restart db
```

### Volledig Opnieuw Starten
```bash
docker-compose down
docker-compose up -d
```

### Data Verwijderen (LET OP!)
```bash
# Verwijdert ALLE data!
docker-compose down -v
```

## Performance Tips

### Query Optimalisatie
Als queries traag worden bij veel data:

```sql
-- Check index status
SELECT schemaname, tablename, indexname 
FROM pg_indexes 
WHERE tablename = 'measurements';

-- Vacuum database
VACUUM ANALYZE measurements;
```

### Data Retentie
Om oude data te verwijderen (bijvoorbeeld ouder dan 2 jaar):

```sql
DELETE FROM measurements 
WHERE timestamp < NOW() - INTERVAL '2 years';

VACUUM FULL measurements;
```

## Geavanceerde Configuratie

### Custom Poll Interval
In `docker-compose.yml`:
```yaml
environment:
  POLL_INTERVAL: 60  # Elke minuut in plaats van elke 30 seconden
```

### Database Tuning
Voor betere prestaties op een NAS, voeg toe aan `docker-compose.yml` onder `db`:
```yaml
command: >
  postgres
  -c shared_buffers=256MB
  -c effective_cache_size=1GB
  -c maintenance_work_mem=64MB
```

### Netwerk Isolatie
Als je de database niet extern wilt blootstellen:
```yaml
# Verwijder de ports sectie onder db:
# ports:
#   - "5432:5432"
```

## API Endpoints HomeWizard

Beschikbare endpoints op je meter:

```bash
# Huidige metingen
curl http://192.168.1.100/api/v1/data

# Systeem informatie
curl http://192.168.1.100/api

# Test verbinding
curl http://192.168.1.100/api/v1/state
```
